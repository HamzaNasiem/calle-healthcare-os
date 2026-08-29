import logging
import sys
import contextvars
try:
    from pythonjsonlogger import json as jsonlogger
except ImportError:
    from pythonjsonlogger import jsonlogger

correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")

import re

# Regex patterns for PHI (Emails, USA Phone Numbers, DOB formats like YYYY-MM-DD or MM/DD/YYYY)
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
PHONE_REGEX = re.compile(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
DOB_REGEX = re.compile(r'\b(19|20)\d{2}[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b|\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/](19|20)?\d{2}\b')

def scrub_phi(text: str) -> str:
    if not isinstance(text, str):
        return text
    # Redact Email
    text = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
    # Redact Phone
    text = PHONE_REGEX.sub("[REDACTED_PHONE]", text)
    # Redact DOB
    text = DOB_REGEX.sub("[REDACTED_DOB]", text)
    return text

class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = correlation_id.get()
        return True

class PHIScrubberFilter(logging.Filter):
    def filter(self, record):
        # Scrub message
        if isinstance(record.msg, str):
            record.msg = scrub_phi(record.msg)
        # Scrub log arguments
        if record.args:
            new_args = tuple(scrub_phi(arg) if isinstance(arg, str) else arg for arg in record.args)
            record.args = new_args
        return True

def setup_logger(name="bytelytic_os"):
    logger = logging.getLogger(name)
    
    # Avoid attaching handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    logHandler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(correlation_id)s %(message)s",
        rename_fields={"levelname": "severity", "asctime": "timestamp"}
    )
    logHandler.setFormatter(formatter)
    
    # Add correlation filter
    corr_filter = CorrelationIdFilter()
    logHandler.addFilter(corr_filter)
    logger.addFilter(corr_filter)
    
    # Add PHI Scrubber filter
    scrub_filter = PHIScrubberFilter()
    logHandler.addFilter(scrub_filter)
    logger.addFilter(scrub_filter)
    
    logger.addHandler(logHandler)
    logger.propagate = False

    # Apply same JSON formatting and PHI scrubbing to Uvicorn servers logs
    for uvicorn_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        u_logger = logging.getLogger(uvicorn_name)
        # Remove existing standard plain handlers
        for h in list(u_logger.handlers):
            u_logger.removeHandler(h)
        u_logger.addHandler(logHandler)
        u_logger.propagate = False

    # Apply PHI scrubbing to the root logger to catch any stray loggers
    root_logger = logging.getLogger()
    root_logger.addFilter(scrub_filter)
    # Also attach to any existing handlers on root logger
    for h in root_logger.handlers:
        h.addFilter(scrub_filter)
        
    return logger

log = setup_logger()
