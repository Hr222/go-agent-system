from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from uuid import UUID

from app.modules.conversation.ports import ConversationListCursor


class InvalidConversationCursor(ValueError):
    """客户端提供了无法解析的会话列表游标。"""


def encode_conversation_cursor(cursor: ConversationListCursor) -> str:
    payload = json.dumps(
        {
            "id": str(cursor.id),
            "updated_at": cursor.updated_at.isoformat(),
            "is_pinned": cursor.is_pinned,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_conversation_cursor(value: str | None) -> ConversationListCursor | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise InvalidConversationCursor("会话列表游标无效。")
    allowed_characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    if any(character not in allowed_characters for character in value):
        raise InvalidConversationCursor("会话列表游标无效。")

    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(value + padding).decode("utf-8"))
        if not isinstance(payload, dict) or not {"id", "updated_at"}.issubset(payload):
            raise InvalidConversationCursor("会话列表游标无效。")
        conversation_id = UUID(payload["id"])
        updated_at = datetime.fromisoformat(payload["updated_at"])
        if updated_at.tzinfo is None:
            raise InvalidConversationCursor("会话列表游标无效。")
        is_pinned = payload.get("is_pinned", False)
        if not isinstance(is_pinned, bool):
            raise InvalidConversationCursor("会话列表游标无效。")
    except (
        ValueError,
        TypeError,
        KeyError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ) as error:
        raise InvalidConversationCursor("会话列表游标无效。") from error

    return ConversationListCursor(
        updated_at=updated_at,
        id=conversation_id,
        is_pinned=is_pinned,
    )


__all__ = [
    "InvalidConversationCursor",
    "decode_conversation_cursor",
    "encode_conversation_cursor",
]
