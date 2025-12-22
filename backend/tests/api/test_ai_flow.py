import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db
from app.domain.conversations.models import Conversation

client = TestClient(app)

@pytest.fixture
def override_get_db():
    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session
    yield mock_session
    app.dependency_overrides = {}

@patch("app.api.v1.ai.ConversationService")
@patch("app.api.v1.ai.ClientService")
@patch("app.api.v1.ai.Runner")
@patch("app.api.v1.ai.AIRunService")
def test_ai_message_endpoint_flow(MockRunService, MockRunner, MockClientService, MockConvService, override_get_db):
    # 1. Setup Conversation Service Stub
    mock_conv_instance = MockConvService.return_value
    mock_conv_instance.get_or_create_conversation = AsyncMock(
        return_value=Conversation(id=1, crm_thread_id="t1", client_id=100)
    )
    mock_conv_instance.get_agent_state = AsyncMock(return_value={})
    mock_conv_instance.update_agent_state = AsyncMock()
    
    # 2. Setup ClientService mock
    mock_client = MagicMock()
    mock_client.external_id = "client-1"
    mock_client.config = {
        "agents": {
            "orchestrator": {
                "name": "Orchestrator",
                "instructions": "Test instructions",
                "model": "gpt-4o-mini",
                "tools": []
            }
        }
    }
    mock_client.policies = {}
    
    mock_client_svc = MockClientService.return_value
    mock_client_svc.get_client_by_external_id = AsyncMock(return_value=mock_client)
    
    # 3. Setup Runner Stub
    mock_result = MagicMock()
    mock_result.final_output = "Hello from Agent SDK"
    mock_result.last_agent.name = "Orchestrator"
    MockRunner.run = AsyncMock(return_value=mock_result)
    
    # 4. Setup Run Service Stub
    mock_run_instance = MockRunService.return_value
    mock_run_instance.create_run = AsyncMock()

    payload = {
        "thread_id": "t1",
        "message_id": "m1",
        "sender_type": "customer",
        "text": "Hello AI",
        "client_external_id": "client-1"
    }

    # Act
    with patch("app.api.v1.ai.crm_client.send_message", new_callable=AsyncMock):
        response = client.post("/ai/message", json=payload)
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["reply_text"] == "Hello from Agent SDK"
    assert data["metadata"]["agent"] == "Orchestrator"
    
    # Verify Interactions
    mock_conv_instance.get_or_create_conversation.assert_awaited_once()
    MockRunner.run.assert_awaited_once()
    mock_run_instance.create_run.assert_awaited_once()


@patch("app.api.v1.ai.ConversationService")
@patch("app.api.v1.ai.ClientService")
@patch("app.api.v1.ai.Runner")
@patch("app.api.v1.ai.AIRunService")
def test_ai_message_with_chat_history(MockRunService, MockRunner, MockClientService, MockConvService, override_get_db):
    """Test that chat_history is properly passed to the agent."""
    # Setup mocks
    mock_conv_instance = MockConvService.return_value
    mock_conv_instance.get_or_create_conversation = AsyncMock(
        return_value=Conversation(id=1, crm_thread_id="t2", client_id=100)
    )
    mock_conv_instance.get_agent_state = AsyncMock(return_value={})
    mock_conv_instance.update_agent_state = AsyncMock()
    
    mock_client = MagicMock()
    mock_client.external_id = "client-1"
    mock_client.config = {
        "agents": {
            "orchestrator": {
                "name": "Orchestrator",
                "instructions": "Test",
                "model": "gpt-4o-mini",
                "tools": []
            }
        }
    }
    mock_client.policies = {}
    
    mock_client_svc = MockClientService.return_value
    mock_client_svc.get_client_by_external_id = AsyncMock(return_value=mock_client)
    
    mock_result = MagicMock()
    mock_result.final_output = "Colors available: red, blue"
    mock_result.last_agent.name = "Orchestrator"
    MockRunner.run = AsyncMock(return_value=mock_result)
    
    mock_run_instance = MockRunService.return_value
    mock_run_instance.create_run = AsyncMock()
    
    # Payload with chat_history
    payload = {
        "thread_id": "t2",
        "message_id": "m2",
        "sender_type": "customer",
        "text": "What colors are available?",
        "client_external_id": "client-1",
        "chat_history": [
            {"role": "user", "content": "Show me Nike shoes"},
            {"role": "assistant", "content": "Found Nike Air Max 90."}
        ]
    }
    
    with patch("app.api.v1.ai.crm_client.send_message", new_callable=AsyncMock):
        response = client.post("/ai/message", json=payload)
    
    assert response.status_code == 200
    
    # Verify Runner.run was called with the full message history
    call_args = MockRunner.run.call_args
    input_messages = call_args.kwargs.get("input") or call_args[1].get("input")
    
    # Should have 3 messages: 2 from history + 1 current
    assert len(input_messages) == 3
    assert input_messages[0]["content"] == "Show me Nike shoes"
    assert input_messages[1]["content"] == "Found Nike Air Max 90."
    assert input_messages[2]["content"] == "What colors are available?"

