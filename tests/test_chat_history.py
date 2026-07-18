"""Tests for chat history persistence."""
from database import get_session, init_db
from services.chat_history import add_message, create_session, get_session_messages, list_sessions


def test_chat_session_lifecycle():
    init_db()
    session = get_session()
    try:
        chat = create_session(session, title="New chat")
        session_id = chat["session_id"]
        add_message(session, session_id, "user", "Find bills in Downloads")
        add_message(session, session_id, "assistant", "I found 2 ZIP files.", metadata={"success": True})

        listed = list_sessions(session)
        assert any(item["session_id"] == session_id for item in listed)

        payload = get_session_messages(session, session_id)
        assert payload is not None
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "user"
        assert payload["session"]["title"] == "Find bills in Downloads"
    finally:
        session.close()
