from openai import AsyncOpenAI
from app.core.config import settings
from typing import List, Dict, Any, Optional
import json

class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini" # Or from settings

    async def get_completion(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Any:
        """
        Wrapper for OpenAI ChatCompletion.
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
            temperature=0.0, # Deterministic behavior preferred
        )
        return response.choices[0].message

llm_client = LLMClient()
