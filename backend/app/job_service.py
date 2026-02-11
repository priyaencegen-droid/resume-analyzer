from .resume_parser import extract_text, extract_name_from_text
from .llm_service import score_resume
from .database import SessionLocal
from .models import Candidate, Job
from .utils import timing_decorator, log_performance_metrics


import logging
import os
import time
import traceback

logger = logging.getLogger(__name__)


@timing_decorator
def process_job(job_id, jd, file_paths):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        successful_count = 0
        failed_count = 0

        for i, path in enumerate(file_paths, 1):
            file_start_time = time.time()
            try:
                logger.info(f"Processing file {i}/{len(file_paths)}: {os.path.basename(path)}")
                
                text = extract_text(path)
                
                # Extract name first using our specialized name extractor
                extracted_name = extract_name_from_text(text) if text and text.strip() else None
                
                if not text or not text.strip():
                    logger.warning(f"No text extracted from {path}")
                    candidate = Candidate(
                        job_id=job_id,
                        name="Unknown",
                        score=0,
                        classification="Weak",
                        summary="No text extracted"
                    )
                else:
                    start_time = time.time()
                    result = score_resume(jd, text)
                    llm_time = time.time() - start_time
                    log_performance_metrics(f"LLM scoring for {os.path.basename(path)}", llm_time)
                    
                    # Use our extracted name if available, otherwise use LLM's attempt
                    final_name = extracted_name if extracted_name else result.get("name", "Unknown")
                    
                    candidate = Candidate(
                        job_id=job_id,
                        name=final_name,
                        score=result.get("score", 50),
                        classification=result.get("classification", "Partial"),
                        summary=result.get("summary", "")
                    )
                
                db.add(candidate)
                successful_count += 1
                logger.info(f"Successfully processed: {os.path.basename(path)}")

            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing {path}: {e}")
                logger.error(traceback.format_exc())
                
                # Create a candidate record for the failed file
                try:
                    candidate = Candidate(
                        job_id=job_id,
                        name="Processing Error",
                        score=0,
                        classification="Weak",
                        summary=f"Failed to process file: {str(e)[:100]}"
                    )
                    db.add(candidate)
                except Exception as commit_error:
                    logger.error(f"Failed to add error record: {commit_error}")
                    db.rollback()

            # Update progress after each file
            setattr(job, 'processed_files', i)  # Use setattr to avoid type issues
            db.commit()
            
            # Log file processing time
            file_time = time.time() - file_start_time
            log_performance_metrics(f"File {i} processing", file_time)

        # Final status update
        if failed_count == 0:
            setattr(job, 'status', "completed")
            logger.info(f"Job {job_id} completed successfully. Processed {successful_count} files.")
        elif successful_count > 0:
            setattr(job, 'status', "completed_with_errors")
            logger.info(f"Job {job_id} completed with {successful_count} successful and {failed_count} failed files.")
        else:
            setattr(job, 'status', "failed")
            logger.error(f"Job {job_id} failed. All {failed_count} files failed to process.")
        
        db.commit()
        
        # Clean up uploaded files
        cleanup_uploaded_files(file_paths)
        
    except Exception as e:
        logger.error(f"Fatal error in process_job {job_id}: {e}")
        logger.error(traceback.format_exc())
        if job:
            setattr(job, 'status', "failed")
            db.commit()
    finally:
        db.close()


def cleanup_uploaded_files(file_paths):
    """Clean up uploaded files after processing"""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Cleaned up file: {path}")
        except Exception as e:
            logger.error(f"Failed to cleanup file {path}: {e}")
