"""Persist chat sessions and messages for the web UI."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from database.orm_models import ChatMessageORM, ChatSessionORM


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _title_from_message(message: str) -> str:
    text = " ".join(message.strip().split())
    if len(text) <= 56:
        return text or "New chat"
    return f"{text[:53]}..."


def create_session(session: Session, title: str = "New chat") -> dict[str, Any]:
    chat_session = ChatSessionORM(
        session_id=uuid4().hex,
        title=title,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(chat_session)
    session.commit()
    return _session_dict(chat_session, message_count=0)


def list_sessions(session: Session, limit: int = 50) -> list[dict[str, Any]]:
    rows = (
        session.query(ChatSessionORM)
        .order_by(ChatSessionORM.updated_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for row in rows:
        count = session.query(ChatMessageORM).filter(ChatMessageORM.session_id == row.session_id).count()
        result.append(_session_dict(row, message_count=count))
    return result


def get_session_messages(session: Session, session_id: str) -> Optional[dict[str, Any]]:
    chat_session = session.query(ChatSessionORM).filter(ChatSessionORM.session_id == session_id).first()
    if not chat_session:
        return None
    messages = (
        session.query(ChatMessageORM)
        .filter(ChatMessageORM.session_id == session_id)
        .order_by(ChatMessageORM.created_at.asc())
        .all()
    )
    return {
        "session": _session_dict(chat_session, message_count=len(messages)),
        "messages": [_message_dict(message) for message in messages],
    }


def delete_session(session: Session, session_id: str) -> bool:
    chat_session = session.query(ChatSessionORM).filter(ChatSessionORM.session_id == session_id).first()
    if not chat_session:
        return False
    session.query(ChatMessageORM).filter(ChatMessageORM.session_id == session_id).delete()
    session.delete(chat_session)
    session.commit()
    return True


def add_message(
    db: Session,
    session_id: str,
    role: str,
    content: str,
    *,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    chat_session = db.query(ChatSessionORM).filter(ChatSessionORM.session_id == session_id).first()
    if not chat_session:
        raise ValueError(f"Chat session not found: {session_id}")

    message = ChatMessageORM(
        message_id=uuid4().hex,
        session_id=session_id,
        role=role,
        content=content,
        metadata_json=json.dumps(metadata or {}),
        created_at=_now(),
    )
    db.add(message)
    if role == "user" and (chat_session.title == "New chat" or not chat_session.title):
        chat_session.title = _title_from_message(content)
    chat_session.updated_at = _now()
    db.commit()
    return _message_dict(message)


def _session_dict(chat_session: ChatSessionORM, *, message_count: int) -> dict[str, Any]:
    return {
        "session_id": chat_session.session_id,
        "title": chat_session.title,
        "created_at": chat_session.created_at.isoformat(),
        "updated_at": chat_session.updated_at.isoformat(),
        "message_count": message_count,
    }


def _message_dict(message: ChatMessageORM) -> dict[str, Any]:
    metadata = {}
    if message.metadata_json:
        try:
            metadata = json.loads(message.metadata_json)
        except json.JSONDecodeError:
            metadata = {}
    return {
        "message_id": message.message_id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "metadata": metadata,
        "created_at": message.created_at.isoformat(),
    }
