from __future__ import annotations

import base64
import json
from datetime import datetime
from uuid import UUID

from app.platform.task.ports import TaskListCursor


class InvalidTaskCursor(ValueError):
    """任务列表游标不能被安全解析。"""


def encode_task_cursor(cursor: TaskListCursor) -> str:
    payload = json.dumps(
        {"updated_at": cursor.updated_at.isoformat(), "id": str(cursor.id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_task_cursor(value: str | None) -> TaskListCursor | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > 256:
        raise InvalidTaskCursor("任务列表游标无效。")
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        updated_at = datetime.fromisoformat(payload["updated_at"])
        task_id = UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise InvalidTaskCursor("任务列表游标无效。") from exc
    if updated_at.tzinfo is None:
        raise InvalidTaskCursor("任务列表游标无效。")
    return TaskListCursor(updated_at=updated_at, id=task_id)
