from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.conversations.models import Conversation, AgentState
from app.domain.clients.models import Client

class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_conversation(self, crm_thread_id: str, client_external_id: str) -> Conversation:
        # 1. Resolve Client
        result = await self.db.execute(select(Client).where(Client.external_id == client_external_id))
        client = result.scalar_one_or_none()
        
        if not client:
            # Auto-create client for dev convenience, or error out
            client = Client(external_id=client_external_id, name=f"Client {client_external_id}")
            self.db.add(client)
            await self.db.flush() # get ID

        # 2. Find Conversation
        result = await self.db.execute(select(Conversation).where(Conversation.crm_thread_id == crm_thread_id))
        conversation = result.scalar_one_or_none()

        if not conversation:
            conversation = Conversation(
                client_id=client.id,
                crm_thread_id=crm_thread_id,
                status="open"
            )
            self.db.add(conversation)
            await self.db.flush()
            
            # Create empty agent state
            agent_state = AgentState(conversation_id=conversation.id, state={})
            self.db.add(agent_state)
            await self.db.commit() # Commit all
            await self.db.refresh(conversation)
        
        return conversation

    async def get_agent_state(self, conversation_id: int) -> dict:
        result = await self.db.execute(select(AgentState).where(AgentState.conversation_id == conversation_id))
        state_row = result.scalar_one_or_none()
        return state_row.state if state_row else {}

    async def update_agent_state(self, conversation_id: int, new_state: dict):
        result = await self.db.execute(select(AgentState).where(AgentState.conversation_id == conversation_id))
        state_row = result.scalar_one_or_none()
        if state_row:
            state_row.state = new_state
            # self.db.add(state_row) # not needed if attached
            await self.db.commit()
