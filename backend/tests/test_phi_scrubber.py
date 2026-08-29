import logging
import sys
from src.core.logger import scrub_phi, PHIScrubberFilter

def test_scrub_phi():
    # Test Email redaction
    assert scrub_phi("My email is john.doe@example.com") == "My email is [REDACTED_EMAIL]"
    
    # Test USA Phone Number redaction (various formats)
    assert scrub_phi("Call me at 555-123-4567") == "Call me at [REDACTED_PHONE]"
    assert scrub_phi("Call me at (555) 123-4567") == "Call me at [REDACTED_PHONE]"
    assert scrub_phi("Call me at +1 555-123-4567") == "Call me at [REDACTED_PHONE]"
    
    # Test DOB redaction
    assert scrub_phi("Born on 1990-05-15") == "Born on [REDACTED_DOB]"
    assert scrub_phi("DOB is 05/15/1990") == "DOB is [REDACTED_DOB]"

def test_phi_scrubber_filter(capsys):
    # Setup a local logger with the scrubber filter
    test_logger = logging.getLogger("test_phi_scrubber")
    test_logger.setLevel(logging.INFO)
    
    # Simple stream handler outputting to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(PHIScrubberFilter())
    test_logger.addHandler(handler)
    
    # Log sensitive info
    test_logger.info("Patient John Doe has email test@example.com and phone (123) 456-7890. Born: 1985-12-01.")
    
    # Capture output
    captured = capsys.readouterr()
    output = captured.out.strip()
    
    assert "test@example.com" not in output
    assert "(123) 456-7890" not in output
    assert "1985-12-01" not in output
    
    assert "[REDACTED_EMAIL]" in output
    assert "[REDACTED_PHONE]" in output
    assert "[REDACTED_DOB]" in output
    
    # Clean up handler
    test_logger.removeHandler(handler)
