"""
PII Utilities - Mask and redact personally identifiable information
"""
import re
from typing import Optional


def mask_email(email: Optional[str]) -> str:
    """
    Mask an email address for display/logging.
    Example: john.doe@example.com -> j***@example.com
    """
    if not email or "@" not in email:
        return email or ""
    
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        masked_local = local
    else:
        masked_local = local[0] + "***"
    
    return f"{masked_local}@{domain}"


def mask_phone(phone: Optional[str]) -> str:
    """
    Mask a phone number for display/logging.
    Example: 03312541962 -> ***-***-1962
    """
    if not phone:
        return ""
    
    # Remove non-numeric characters for processing
    digits = re.sub(r'\D', '', phone)
    
    if len(digits) < 4:
        return "***"
    
    # Show only last 4 digits
    return f"***-***-{digits[-4:]}"


def redact_pii_for_log(text: str) -> str:
    """
    Redact common PII patterns from text for safe logging.
    Detects and masks emails and phone numbers.
    """
    if not text:
        return text
    
    # Mask emails
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    text = re.sub(email_pattern, lambda m: mask_email(m.group()), text)
    
    # Mask phone numbers (various formats)
    # Matches patterns like: +1234567890, 123-456-7890, (123) 456-7890, 03312541962
    phone_pattern = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}'
    text = re.sub(phone_pattern, lambda m: mask_phone(m.group()), text)
    
    return text
