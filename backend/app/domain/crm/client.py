from typing import List, Dict, Any, Optional
import httpx
from app.core.config import settings

class CRMClient:
    def __init__(self):
        self.base_url = settings.CRM_API_URL
        self.api_key = settings.CRM_API_KEY
        
    async def send_message(self, thread_id: str, text: str, sender: str = "ai") -> Dict[str, Any]:
        """
        Sends a message back to the CRM.
        """
        # SUB: In real impl, use httpx to post to CRM
        # async with httpx.AsyncClient() as client:
        #     resp = await client.post(f"{self.base_url}/threads/{thread_id}/messages", ...)
        #     return resp.json()
        
        print(f"[CRM MOCK] Sending message to thread {thread_id}: {text}")
        return {"id": "mock-msg-id", "status": "sent"}

    async def get_history(self, thread_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetches conversation history.
        """
        # STUB
        return []

crm_client = CRMClient()
