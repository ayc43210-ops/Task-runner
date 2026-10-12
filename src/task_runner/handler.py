from collections.abc import Callable

type Handler = Callable[[dict], dict]


def generate_report(payload: dict) -> dict:
    return {"report_id": payload["report_id"], "pages": 3}


def send_email(payload: dict) -> dict:
    return {"sent_to": payload["to"]}


REGISTRY: dict[str, Handler] = {
    "generate_report": generate_report,
    "send_email": send_email,
}
