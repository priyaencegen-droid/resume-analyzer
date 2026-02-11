from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import shutil, os
import time
import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .database import Base, engine, SessionLocal
from .models import Job, Candidate
from .job_service import process_job

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

logger.info("Creating database tables...")
start_time = time.time()
Base.metadata.create_all(bind=engine)
logger.info(f"Database setup completed in {time.time() - start_time:.2f}s")

# # Test Ollama connection
# from .llm_service import test_ollama_connection
# try:
#     ollama_status = test_ollama_connection()
#     if not ollama_status:
#         logger.warning("⚠️ OLLAMA NOT READY - Resume analysis will fail until Ollama is running")
#         logger.info("💡 Start Ollama with: ollama serve")
# except Exception as e:
#     logger.error(f"Failed to test Ollama connection: {e}")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/")
def home():
    logger.info("Health check endpoint accessed")
    return {"message": "HR Resume Analyzer API", "status": "running"}


@app.post("/start-job")
async def start_job(
    background_tasks: BackgroundTasks,
    jd: str = Form(...),
    files: list[UploadFile] = File(...)
):
    if not jd or not jd.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty")
    
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="At least one file must be uploaded")
    
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files allowed per job")
    
    # Validate file types
    allowed_extensions = {'.pdf', '.docx', '.doc'}
    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="All files must have names")
        
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"File {file.filename} has unsupported format. Allowed: {', '.join(allowed_extensions)}"
            )
    
    db = SessionLocal()
    try:
        job = Job(
            status="processing",
            total_files=len(files),
            processed_files=0
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        file_paths = []

        for file in files:
            try:
                path = f"{UPLOAD_DIR}/{job.id}_{int(time.time())}_{file.filename}"
                with open(path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                file_paths.append(path)
                logger.info(f"Saved file: {file.filename} -> {path}")
            except Exception as e:
                logger.error(f"Failed to save file {file.filename}: {e}")
                # Clean up any files already saved
                for saved_path in file_paths:
                    if os.path.exists(saved_path):
                        os.remove(saved_path)
                raise HTTPException(status_code=500, detail=f"Failed to save file {file.filename}")

        background_tasks.add_task(process_job, job.id, jd, file_paths)
        logger.info(f"Started job {job.id} with {len(files)} files")

        return {
            "job_id": job.id,
            "message": "Processing started",
            "total_files": len(files)
        }
    except HTTPException:
        db.close()
        raise
    except Exception as e:
        logger.error(f"Unexpected error in start_job: {e}")
        logger.error(traceback.format_exc())
        db.close()
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        db.close()


@app.get("/job-status/{job_id}")
def job_status(job_id: int):
    if job_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        candidates = db.query(Candidate).filter(
            Candidate.job_id == job_id
        ).order_by(Candidate.score.desc()).all()

        return {
            "status": job.status,
            "processed": job.processed_files,
            "total": job.total_files,
            "candidates": [
                {
                    "name": c.name,
                    "score": float(f"{c.score:.1f}"),
                    "classification": c.classification,
                    "summary": c.summary
                }
                for c in candidates
            ]
        }
    except HTTPException:
        db.close()
        raise
    except Exception as e:
        logger.error(f"Error in job_status for job {job_id}: {e}")
        db.close()
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        db.close()
