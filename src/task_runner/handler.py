import time
import os
from collections.abc import Callable
from pathlib import Path

from task_runner.retry import PermanentError

type Handler = Callable[[dict], dict]


def generate_report(payload: dict) -> dict:
    return {"report_id": payload["report_id"], "pages": 3}


def send_email(payload: dict) -> dict:
    return {"sent_to": payload["to"]}



def sleep_handler(payload: dict) -> dict:
    seconds = payload.get("seconds")

    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise PermanentError("seconds must be a number")

    if seconds <= 0 or seconds > 30:
        raise PermanentError("seconds must be between 0 and 30")

    time.sleep(seconds)

    return {"slept_seconds": seconds}

def write_to_file_and_sleep(payload: dict)->dict:
    raw = payload.get("path")
    line = payload.get("line")
    request_id = payload.get("request_id")
    if not isinstance(raw, str):
        raise PermanentError("path must be a string")
    
    if not isinstance(line, str):
        raise PermanentError("line must be a string")
    
    if not isinstance(request_id, str):
        raise PermanentError("request_id must be a string")
    
    if "\n" in line or "\n" in request_id:
        raise PermanentError("line and request_id must not contain newlines")
        
    folder = os.environ.get("DEMO_DIR")
    if folder is None:
        raise PermanentError("DEMO_DIR is not configured")
    
    SAFE_ZONE = Path(folder).resolve()
    
    file_path = (SAFE_ZONE / raw).resolve()

    # Check if the file lives inside the safe zone
    if not file_path.is_relative_to(SAFE_ZONE):
        raise PermanentError("path escapes the allowed folder")
    
    
    if file_path.exists():
        for existing in file_path.read_text(encoding="utf-8").splitlines():
            if existing.startswith(f"{request_id} "):
                return {"written": False}

    try:
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(f"{request_id} {line}\n")
    except OSError as exc:
        raise PermanentError(f"failed to write to file: {exc}") from exc
    
    
    time.sleep(4)
    return {"written": True}
    


REGISTRY: dict[str, Handler] = {
    "generate_report": generate_report,
    "send_email": send_email,
    "sleep": sleep_handler,
    "write_to_file": write_to_file_and_sleep,
}
