import pytest
import asyncio
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# CRITICAL: Mock Milvus Service module-level instantiation BEFORE it is imported anywhere
mock_milvus_module = MagicMock()
sys.modules["app.services.milvus_service"] = mock_milvus_module
mock_milvus_module.milvus_service = MagicMock()

# Mock Sync Service
mock_sync_module = MagicMock()
sys.modules["app.services.sync_service"] = mock_sync_module
mock_sync_module.sync_service = MagicMock()

# Mock Ops Client
mock_ops_module = MagicMock()
sys.modules["app.domain.ops.client"] = mock_ops_module
mock_ops_module.ops_client = MagicMock()

# Mock helpers
class MockRunResult:
    def __init__(self, final_output="Mock Output", agent_name="MockAgent"):
        self.final_output = final_output
        self.agent_name = agent_name
        self.usage = MagicMock()

@pytest.mark.asyncio
async def test_trusted_context_skip_otp():
    """Test that providing email/phone allows skipping OTP."""
    # Delayed imports to avoid global init issues
    from app.api.v1.schemas import AIMessageRequest
    from app.domain.agents.context import ClientContext
    
    # Mock dependencies
    mock_db = AsyncMock()
    mock_bg_tasks = MagicMock()
    
    # Mock Request with Email (Trusted)
    request_data = AIMessageRequest(
        message_id="msg-1",
        thread_id="t-1",
        client_external_id="drex7001",
        text="Cancel order 123",
        app_name="drex7001",
        customer={"email": "test@example.com"} # Trusted!
    )
    
    # Mock Client Service
    mock_client = MagicMock()
    mock_client.external_id = "drex7001"
    mock_client.config = {"use_new_architecture": True}
    
    # Mock Conversation Service
    mock_conv = MagicMock()
    mock_conv.id = 123
    
    with patch("app.api.v1.ai.ClientService") as MockClientService, \
         patch("app.api.v1.ai.ConversationService") as MockConversationService, \
         patch("app.api.v1.ai.Runner.run", new_callable=AsyncMock) as MockRunner, \
         patch("app.api.v1.ai.AIRunService") as MockRunService, \
         patch("app.domain.agents.definition.milvus_service") as MockMilvus, \
         patch("app.domain.agents.definition.sync_service") as MockSync, \
         patch("app.domain.agents.definition.ops_client") as MockOps:
            
        # Verify import works now that patches are active (or at least valid during run)
        from app.api.v1.ai import ai_message
        
        MockClientService.return_value.get_client_by_external_id = AsyncMock(return_value=mock_client)
        MockConversationService.return_value.get_or_create_conversation = AsyncMock(return_value=mock_conv)
        MockConversationService.return_value.get_agent_state = AsyncMock(return_value={})
        MockConversationService.return_value.update_agent_state = AsyncMock()
        
        MockRunService.return_value.create_run = AsyncMock()
        
        MockRunner.return_value = MockRunResult("Cancelled Successfully", "Ops Agent")
        
        # Run
        response = await ai_message(request_data, mock_bg_tasks, mock_db)
        
        # Verify Context Created with is_authenticated=True
        call_args = MockRunner.call_args
        assert call_args is not None
        _, kwargs = call_args
        context = kwargs.get("context")
        assert isinstance(context, ClientContext)
        assert context.is_authenticated == True
        print("\\n✅ Trusted Context Test Passed: is_authenticated=True")

@pytest.mark.asyncio
async def test_sticky_routing_pending_otp():
    """Test that pending OTP forces sticky routing to Ops Agent."""
    from app.api.v1.schemas import AIMessageRequest
    
    mock_db = AsyncMock()
    mock_bg_tasks = MagicMock()
    
    request_data = AIMessageRequest(
        message_id="msg-2",
        thread_id="t-2",
        client_external_id="drex7001",
        text="Here is the OTP",
        app_name="drex7001"
    )
    
    mock_client = MagicMock()
    mock_client.external_id = "drex7001"
    mock_client.config = {"use_new_architecture": True}
    
    mock_conv = MagicMock()
    mock_conv.id = 123
    
    # Mock State with Pending OTP
    pending_otp_state = {
        "action": "cancel_order", 
        "order_id": "123", 
        "verified": False # IMPORTANT: Not verified yet
    }
    
    with patch("app.api.v1.ai.ClientService") as MockClientService, \
         patch("app.api.v1.ai.ConversationService") as MockConversationService, \
         patch("app.api.v1.ai.Runner.run", new_callable=AsyncMock) as MockRunner, \
         patch("app.api.v1.ai.AIRunService") as MockRunService, \
         patch("app.domain.agents.definition.milvus_service") as MockMilvus, \
         patch("app.domain.agents.definition.sync_service") as MockSync, \
         patch("app.domain.agents.definition.ops_client") as MockOps:
         
        from app.api.v1.ai import ai_message

        MockClientService.return_value.get_client_by_external_id = AsyncMock(return_value=mock_client)
        MockConversationService.return_value.get_or_create_conversation = AsyncMock(return_value=mock_conv)
        # Return state with Pending OTP
        MockConversationService.return_value.get_agent_state = AsyncMock(return_value={"pending_otp": pending_otp_state})
        MockConversationService.return_value.update_agent_state = AsyncMock()
        
        MockRunService.return_value.create_run = AsyncMock()
        
        MockRunner.return_value = MockRunResult("Verifying...", "Ops Agent")
        
        # Run
        await ai_message(request_data, mock_bg_tasks, mock_db)
        
        # Verify Runner was called with Ops Agent
        call_args = MockRunner.call_args
        entry_agent = call_args[0][0]
        assert entry_agent.name == "Ops Agent"
        print("\\n✅ Sticky Routing Test Passed: Routed to Ops Agent due to pending OTP")

if __name__ == "__main__":
    # Manually run async tests if executed as script
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_trusted_context_skip_otp())
    loop.run_until_complete(test_sticky_routing_pending_otp())
