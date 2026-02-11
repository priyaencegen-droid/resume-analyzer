import os
import json
import logging
import traceback
from dotenv import load_dotenv
from ollama import Client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Ollama client
client = Client(
    host="https://ollama.com",
    headers={"Authorization": "Bearer " + os.environ.get("OLLAMA_API_KEY", "")}
)

MODEL = "gpt-oss:120b"  # Change if needed


# -----------------------------
# FALLBACK SCORING (Keyword Based)
# -----------------------------
def fallback_score_resume(jd, resume_text):
    import re

    lines = resume_text.split("\n")[:5]
    name = "Unknown"

    name_patterns = [
        r'^[A-Z][a-z]+ [A-Z][a-z]+(?: [A-Z][a-z]+)?',
        r'^[A-Z]\. [A-Z][a-z]+',
        r'^[A-Z][a-z]+, [A-Z]\.',
        r'^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+',
    ]

    for line in lines:
        line = line.strip()
        if not line or len(line) > 60:
            continue

        skip_phrases = [
            "email", "phone", "address", "objective",
            "summary", "experience", "education",
            "skills", "resume", "cv"
        ]

        if any(phrase in line.lower() for phrase in skip_phrases):
            continue

        for pattern in name_patterns:
            match = re.match(pattern, line)
            if match:
                name = match.group(0).title()
                break

        if name != "Unknown":
            break

    jd_words = set(jd.lower().split())
    resume_words = set(resume_text.lower().split())

    common_words = {
        "the", "a", "an", "and", "or", "but", "in", "on",
        "at", "to", "for", "of", "with", "by", "is",
        "are", "was", "were", "be", "been", "have",
        "has", "had"
    }

    jd_keywords = jd_words - common_words
    matches = resume_words.intersection(jd_keywords)

    if len(jd_keywords) > 0:
        match_ratio = len(matches) / len(jd_keywords)
        score = min(85, int(match_ratio * 100))
    else:
        score = 50

    if score >= 75:
        classification = "Strong"
    elif score >= 60:
        classification = "Partial"
    else:
        classification = "Weak"

    return {
        "name": name,
        "score": score,
        "classification": classification,
        "summary": f"Fallback analysis: {len(matches)} keyword matches",
        "matched_keywords": list(matches)[:10],
        "jd_keywords": list(jd_keywords)[:10],
        "match_ratio": len(matches) / len(jd_keywords) if len(jd_keywords) else 0
    }


# -----------------------------
# MAIN LLM SCORING FUNCTION
# -----------------------------
def score_resume(jd, resume_text):

    if not jd.strip():
        return {
            "name": "Unknown",
            "score": 0,
            "classification": "Partial",
            "summary": "Invalid job description"
        }

    if not resume_text.strip():
        return {
            "name": "Unknown",
            "score": 0,
            "classification": "Partial",
            "summary": "Invalid resume text"
        }

    # Truncate to avoid token overflow
    jd = jd[:1500]
    resume_text = resume_text[:3000]

    prompt = f"""
Evaluate the resume against the job description.

Return JSON only in this exact format:
{{"name": "Name", "score": 0-100, "classification": "Excellent/Strong/Partial/Weak", "summary": "Brief summary"}}

JOB DESCRIPTION:
{jd}

RESUME:
{resume_text}
"""

    try:
        response = client.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}]
        )

        output = response["message"]["content"]

        # Extract JSON safely
        start = output.find("{")
        end = output.rfind("}") + 1
        json_str = output[start:end]

        result = json.loads(json_str)

        # Validate response
        result["name"] = result.get("name", "Unknown")
        result["score"] = max(0, min(100, float(result.get("score", 50))))
        result["classification"] = result.get(
            "classification", "Partial"
        )
        result["summary"] = result.get(
            "summary", "No summary available"
        )

        # Add keyword matching info
        jd_words = set(jd.lower().split())
        resume_words = set(resume_text.lower().split())

        common_words = {
            "the", "a", "an", "and", "or", "but", "in", "on",
            "at", "to", "for", "of", "with", "by", "is",
            "are", "was", "were", "be", "been", "have",
            "has", "had"
        }

        jd_keywords = jd_words - common_words
        matches = resume_words.intersection(jd_keywords)

        result["matched_keywords"] = list(matches)[:10]
        result["jd_keywords"] = list(jd_keywords)[:10]
        result["match_ratio"] = (
            len(matches) / len(jd_keywords)
            if len(jd_keywords) > 0 else 0
        )

        return result

    except Exception as e:
        logger.error(f"LLM Error: {e}")
        logger.error(traceback.format_exc())
        return fallback_score_resume(jd, resume_text)


# -----------------------------
# TEST RUN
# -----------------------------
if __name__ == "__main__":
    jd_sample = "Looking for Python developer with FastAPI, SQL, and ML experience."
    resume_sample = """
    John Doe
    Experienced Python developer with FastAPI and SQL knowledge.
    Worked on ML models using scikit-learn.
    """

    result = score_resume(jd_sample, resume_sample)
    print(json.dumps(result, indent=2))
