from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRACE_PATH = Path(__file__).resolve().parents[2] / "workflow_trace.log"


def trace_step(stage: str, incident_id: int | None, message: str, **details: Any) -> None:
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    incident = f"incident={incident_id}" if incident_id is not None else "incident=-"
    detail_text = _format_details(details)
    line = f"{timestamp} | {stage.upper()} | {incident} | {message}"

    if detail_text:
        line = f"{line} | {detail_text}"

    with TRACE_PATH.open("a", encoding="utf-8") as trace_file:
        trace_file.write(f"{line}\n")


def _format_details(details: dict[str, Any]) -> str:
    parts = []

    for key, value in details.items():
        if value is None:
            continue

        if isinstance(value, (list, tuple)):
            value = ", ".join(str(item) for item in value) or "none"

        parts.append(f"{key}={_one_line(str(value))}")

    return " | ".join(parts)


def _one_line(value: str) -> str:
    return " ".join(value.split())
