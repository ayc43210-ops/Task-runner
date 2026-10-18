import time
from collections.abc import Callable

type Handler = Callable[[dict], dict]


def generate_report(payload: dict) -> dict:
    return {"report_id": payload["report_id"], "pages": 3}


def send_email(payload: dict) -> dict:
    return {"sent_to": payload["to"]}



def sleep_handler(payload: dict) -> dict:
    seconds = payload["seconds"]

    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise ValueError("seconds must be a number")

    if seconds <= 0 or seconds > 30:
        raise ValueError("seconds must be between 0 and 30")

    time.sleep(seconds)

    return {"slept_seconds": seconds}


REGISTRY: dict[str, Handler] = {
    "generate_report": generate_report,
    "send_email": send_email,
    "sleep": sleep_handler,
}
