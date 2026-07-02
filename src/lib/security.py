import os
import datetime

# Directory for logs
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))
LOG_FILE = os.path.join(LOG_DIR, "security_rejections.log")

def log_rejection(user_input: str, reason: str) -> None:
    """Logs rejected user input and the reason to a local log file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().isoformat()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] REJECTED: {repr(user_input)} | REASON: {reason}\n")

def screen_input(user_input: str) -> tuple[bool, str]:
    """Validates user input against prompt injection and low-effort constraints.

    Returns:
        (is_safe, message_or_input) where is_safe is boolean,
        and the second value is the clean input or error message.
    """
    cleaned = user_input.strip()
    
    # 1. Empty/whitespace checks
    if not cleaned:
        reason = "Empty input"
        log_rejection(user_input, reason)
        return False, "Input cannot be empty. Please ask a valid UPSC Polity or Civics question."
        
    # 2. Single-word or extremely short low-effort inputs - reframe instead of rejecting
    words = cleaned.split()
    if len(words) <= 1 or len(cleaned) < 10:
        cleaned = f"Explain the concept of '{cleaned}' in the context of UPSC Polity and Indian Civics."

    # 3. Prompt injection patterns
    injection_patterns = [
        "ignore previous",
        "ignore instructions",
        "system prompt",
        "you are now",
        "developer mode",
        "override prompt",
        "dan mode",
        "bypass restriction",
        "do anything now"
    ]
    
    lower_input = cleaned.lower()
    for pattern in injection_patterns:
        if pattern in lower_input:
            reason = f"Prompt injection pattern detected: '{pattern}'"
            log_rejection(user_input, reason)
            return False, "Security warning: Request pattern not allowed. Please ask a constructive UPSC Polity question."

    return True, cleaned
