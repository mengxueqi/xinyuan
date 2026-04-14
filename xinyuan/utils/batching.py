from __future__ import annotations

from datetime import datetime


def make_batch_key(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H-%M-%S")
