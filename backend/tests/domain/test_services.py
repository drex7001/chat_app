import pytest
from unittest.mock import AsyncMock, MagicMock
from app.domain.conversations.service import ConversationService
from app.domain.conversations.models import Conversation, AgentState
from app.domain.clients.models import Client

@pytest.mark.asyncio
async def test_get_or_create_conversation_creates_new(mock_db_session):
    # Setup
    service = ConversationService(mock_db_session)
    # mock_db_session.execute is AsyncMock. It returns a MagicMock (via fixture).
    # We set side_effect on that MagicMock's scalar_one_or_none method.
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [
        None, # Client result
        None  # Conversation result
    ]
    
    # Act
    conv = await service.get_or_create_conversation("thread-123", "client-abc")
    
    # Assert
    assert conv.crm_thread_id == "thread-123"
    assert conv.status == "open"
    # Verify DB calls
    assert mock_db_session.add.call_count == 3 # Client, Conversation, AgentState
    assert mock_db_session.commit.called

@pytest.mark.asyncio
async def test_get_or_create_conversation_returns_existing(mock_db_session):
    # Setup
    service = ConversationService(mock_db_session)
    existing_client = Client(id=1, external_id="client-abc")
    existing_conv = Conversation(id=10, crm_thread_id="thread-123", client_id=1)
    
    mock_db_session.execute.return_value.scalar_one_or_none.side_effect = [
        existing_client, # Client lookup -> Found
        existing_conv    # Conversation lookup -> Found
    ]
    
    # Act
    conv = await service.get_or_create_conversation("thread-123", "client-abc")
    
    # Assert
    assert conv.id == 10
    assert mock_db_session.add.call_count == 0

@pytest.mark.asyncio
async def test_get_agent_state(mock_db_session):
    # Setup
    service = ConversationService(mock_db_session)
    mock_state = AgentState(conversation_id=1, state={"foo": "bar"})
    mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_state
    
    # Act
    state = await service.get_agent_state(1)
    
    # Assert
    assert state == {"foo": "bar"}
