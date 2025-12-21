import httpx
from typing import List, Dict, Optional
from pydantic import BaseModel
from app.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential

class StorefrontCreds(BaseModel):
    id: int
    name: str
    shop_url: str
    access_token: str
    api_key: str
    api_secret: str

class AdminClient:
    def __init__(self):
        self.base_url = settings.ADMIN_API_URL
        self.api_key = settings.ADMIN_API_KEY
        self.headers = {
            "X-ADMIN-API-KEY": self.api_key,
            "Accept": "application/json"
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_shopify_credentials(self, app_name: str) -> List[StorefrontCreds]:
        """
        Fetches Shopify credentials for a given client (app_name) from the Admin API.
        """
        url = f"{self.base_url}/api/external/v1/clients/{app_name}/shopify-credentials"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, timeout=10.0)
            
            if response.status_code == 404:
                # Client not found or no storefronts
                return []
            
            response.raise_for_status()
            data = response.json()
            
            # The API returns {"storefronts": [...]}
            storefronts_data = data.get("storefronts", [])
            return [StorefrontCreds(**store) for store in storefronts_data]

admin_client = AdminClient()
