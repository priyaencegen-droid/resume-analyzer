import pdfplumber
from docx import Document
import re
from typing import Optional


def extract_name_from_text(text: str) -> Optional[str]:
    """
    Extract candidate name from resume text using multiple patterns
    """
    if not text or len(text.strip()) < 10:
        return None
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Pattern 1: First line (most common for resumes)
    if lines:
        first_line = lines[0]
        
        # Skip if first line contains common header words
        header_words = ['resume', 'cv', 'curriculum', 'vitae', 'application', 'profile', 'objective', 'summary', 'professional']
        if not any(header_word.lower() in first_line.lower() for header_word in header_words):
            if len(first_line.split()) >= 2 and len(first_line) < 50:
                # Check if it looks like a name (2-4 words, mostly letters)
                words = first_line.split()
                if 2 <= len(words) <= 4:
                    name_words = []
                    for word in words:
                        # Remove common non-name characters
                        clean_word = re.sub(r'[^\w\s-]', '', word)
                        if clean_word.isalpha() or clean_word.replace('-', '').isalpha():
                            name_words.append(clean_word)
                    
                    if name_words and len(name_words) >= 2:
                        return ' '.join(name_words)
    
    # Pattern 1b: Check second line if first is a header
    if len(lines) > 1:
        first_line = lines[0]
        second_line = lines[1]
        
        # If first line is a header, check second line for name
        header_words = ['resume', 'cv', 'curriculum', 'vitae', 'application', 'profile', 'objective', 'summary', 'professional']
        if any(header_word.lower() in first_line.lower() for header_word in header_words):
            if len(second_line.split()) >= 2 and len(second_line) < 50:
                # Check if second line looks like a name
                words = second_line.split()
                if 2 <= len(words) <= 4:
                    name_words = []
                    for word in words:
                        clean_word = re.sub(r'[^\w\s-]', '', word)
                        if clean_word.isalpha() or clean_word.replace('-', '').isalpha():
                            name_words.append(clean_word)
                    
                    if name_words and len(name_words) >= 2:
                        return ' '.join(name_words)
    
    # Pattern 2: Look for "Name:" or similar patterns
    name_patterns = [
        r'(?:Name|Full Name|Candidate Name|Applicant)[:\s]+([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        r'^([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:\n|$)',  # Line with capitalized name (exclude common non-name words)
        r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Email|Phone|Resume)',  # Name before contact info (removed "Contact")
    ]
    
    for pattern in name_patterns:
        matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
        for match in matches:
            potential_name = match.strip()
            if len(potential_name.split()) >= 2 and len(potential_name) < 50:
                # Additional validation: exclude common non-name phrases
                non_name_phrases = ['contact information', 'professional experience', 'education summary', 'skills overview', 'work history', 'education', 'experience', 'skills']
                if not any(phrase.lower() in potential_name.lower() for phrase in non_name_phrases):
                    return potential_name
    
    # Pattern 3: Look for email addresses and extract name from them
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    
    if emails:
        # Pattern 3a: If first line is header, extract from email
        if lines:
            first_line = lines[0]
            header_words = ['resume', 'cv', 'curriculum', 'vitae', 'application', 'profile']
            if any(header_word.lower() in first_line.lower() for header_word in header_words):
                email = emails[0]
                local_part = email.split('@')[0]
                
                if '.' in local_part:
                    parts = local_part.split('.')
                    if len(parts) >= 2:
                        name_from_email = ' '.join(part.capitalize() for part in parts[:2] if part.isalpha())
                        if name_from_email and len(name_from_email.split()) >= 2:
                            return name_from_email
        
        # Pattern 3b: General email extraction (fallback)
        email = emails[0]
        local_part = email.split('@')[0]
        
        # Handle common name patterns in emails
        name_from_email = None
        
        # john.doe -> John Doe
        if '.' in local_part:
            parts = local_part.split('.')
            if len(parts) >= 2:
                name_from_email = ' '.join(part.capitalize() for part in parts[:2] if part.isalpha())
        
        # johndoe -> John Doe (if reasonable length)
        elif len(local_part) >= 6 and len(local_part) <= 20:
            # Try to split common name patterns
            for i in range(3, min(8, len(local_part))):
                first = local_part[:i]
                second = local_part[i:]
                if first.isalpha() and second.isalpha():
                    name_from_email = f"{first.capitalize()} {second.capitalize()}"
                    break
        
        if name_from_email and len(name_from_email.split()) >= 2:
            return name_from_email
    
    # Pattern 4: Look for capitalized 2-4 word combinations in first few lines
    for i in range(min(8, len(lines))):
        line = lines[i]
        # Skip if it contains common non-name content
        skip_words = ['resume', 'cv', 'curriculum', 'vitae', 'experience', 'education', 'skills', 'contact', 'phone', 'email', 'address', 'linkedin', 'github', 'portfolio', 'website', 'professional', 'summary', 'objective', 'analyst', 'developer', 'engineer']
        if any(skip_word.lower() in line.lower() for skip_word in skip_words):
            continue
            
        # Look for capitalized name patterns
        words = line.split()
        if 2 <= len(words) <= 4:
            capitalized_words = []
            for word in words:
                cleaned = re.sub(r'[^\w\s-]', '', word)
                # Check if word starts with capital and is mostly letters
                if cleaned and cleaned[0].isupper() and sum(c.isalpha() for c in cleaned) > len(cleaned) * 0.8:
                    capitalized_words.append(cleaned)
            
            if len(capitalized_words) >= 2:
                return ' '.join(capitalized_words)
    
    # Pattern 5: Enhanced email extraction for names
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    if emails:
        email = emails[0]
        local_part = email.split('@')[0]
        
        # More sophisticated email name extraction
        if '.' in local_part:
            parts = local_part.split('.')
            # Filter out numbers and common non-name patterns
            name_parts = []
            for part in parts[:3]:  # Look at first 3 parts max
                if part.isalpha() and len(part) > 1:
                    name_parts.append(part.capitalize())
            
            if len(name_parts) >= 2:
                return ' '.join(name_parts)
    
    return None


def extract_text(file_path: str) -> str:
    """Extract text from resume file"""
    if file_path.endswith(".pdf"):
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    elif file_path.endswith(".docx"):
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)

    return ""


def extract_candidate_info(file_path: str) -> dict:
    """Extract both text and name from resume"""
    text = extract_text(file_path)
    name = extract_name_from_text(text)
    
    return {
        "text": text,
        "name": name or "Unknown"
    }
