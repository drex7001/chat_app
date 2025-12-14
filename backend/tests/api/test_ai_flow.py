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
@patch("app.api.v1.ai.Runner")
@patch("app.api.v1.ai.AIRunService")
def test_ai_message_endpoint_flow(MockRunService, MockRunner, MockServiceClass, override_get_db):
    # 1. Setup Conversation Service Stub
    mock_service_instance = MockServiceClass.return_value
    mock_service_instance.get_or_create_conversation = AsyncMock(
        return_value=Conversation(id=1, crm_thread_id="t1", client_id=100)
    )
    mock_service_instance.get_agent_state = AsyncMock(return_value={})
    mock_service_instance.update_agent_state = AsyncMock()
    
    # 2. Setup Runner Stub
    # We need to simulate the Result object returned by Runner.run()
    mock_result = MagicMock()
    mock_result.final_output = "Hello from Agent SDK"
    mock_result.last_agent.name = "Orchestrator"
    
    MockRunner.run = AsyncMock(return_value=mock_result)
    
    # 3. Setup Run Service Stub
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
    # Mock crm_client to avoid background task errors if any
    with patch("app.api.v1.ai.crm_client.send_message", new_callable=AsyncMock):
        response = client.post("/ai/message", json=payload)
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["reply_text"] == "Hello from Agent SDK"
    assert data["metadata"]["agent"] == "Orchestrator"
    
    # Verify Interactions
    mock_service_instance.get_or_create_conversation.assert_awaited_once()
    MockRunner.run.assert_awaited_once() # Verify Runner was called
    mock_run_instance.create_run.assert_awaited_once() # Verify logging

