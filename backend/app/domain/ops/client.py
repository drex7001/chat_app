from typing import Dict, Any, Optional
import httpx
from app.core.config import settings

class OPSClient:
    def __init__(self):
        self.base_url = settings.OPS_API_URL
        self.api_key = settings.OPS_API_KEY
        
    async def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Fetches order details from OPS.
        """
        # STUB: Mock data for testing
        if order_id == "12345":
            return {
                "id": "12345",
                "status": "SHIPPED",
                "items": [{"sku": "SKU123", "name": "Widget"}],
                "created_at": "2023-01-01T12:00:00Z",
                "delivery_address": "123 Main St"
            }
        
        print(f"[OPS MOCK] Fetching order {order_id}")
        return {"id": order_id, "status": "PROCESSING"}

    async def cancel_order(self, order_id: str, reason: str) -> Dict[str, Any]:
        """
        Cancels an order in OPS.
        """
        print(f"[OPS MOCK] Cancelling order {order_id} reason: {reason}")
        return {"status": "CANCELLED"}

ops_client = OPSClient()
