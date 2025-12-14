from agents import Agent, function_tool
from app.domain.ops.client import ops_client
# from app.core.llm import llm_client

# --- Tool Functions ---

@function_tool
async def get_order_details(order_id: str):
    """Get details of an order."""
    return await ops_client.get_order(order_id)

@function_tool
def kb_search(query: str):
    """Search knowledge base."""
    # Stub
    return "Policies: Returns allowed within 30 days. Shipping takes 3-5 days."

# --- Handoff Stubs (will receive full agent objects at runtime if needed, 
# but simply returning the agent name/object is handled by the framework usually) ---

# For stateless/statelss architecture, handoffs might need to be handled carefully.
# In the OpenAI Agents SDK, a handoff tool returns the Agent object.
# Since we are constructing Agents dynamically, we need a way to resolve them.
# We will define generic handoff tools that 'ai.py' can bind, OR we handle handoffs via names.
# For simplicity in this iteration, we'll keep specifically named tools but they will need access to the agent instances.
# NOTE: The simplest way with dynamic agents is to have a 'handoff_to_agent(agent_name)' tool. 
# But the SDK usually requires returning the Agent object.

# We will define mapped tools here.
TOOL_REGISTRY = {
    "get_order_details": get_order_details,
    "kb_search": kb_search,
}

# We need separate handoff resolution in AI service or use a factory.
# For now, let's define the templates.

DEFAULT_AGENTS = {
    "orchestrator": {
        "name": "Orchestrator",
        "role": "orchestrator",
        "instructions": """You are the main receptionist. 
    - Answer greetings and FAQs using `kb_search`.
    - If user asks about a specific order, handoff to `OrderAgent`.
    - If user asks about shipping/tracking, handoff to `ShippingAgent`.
    - Always be polite.""",
        "model": "gpt-4o-mini",
        "tools": ["kb_search", "transfer_to_order_agent", "transfer_to_shipping_agent"]
    },
    "order_agent": {
        "name": "OrderAgent",
        "role": "specialist",
        "instructions": """You are the Order Specialist.
    - You can view order details with `get_order_details`.
    - You can PROPOSE cancellations (but cannot execute them directly yet).
    - If the user has a general question, handoff back to `Orchestrator`.""",
        "model": "gpt-4o-mini",
        "tools": ["get_order_details", "transfer_back_to_orchestrator"]
    },
    "shipping_agent": {
        "name": "ShippingAgent",
        "role": "specialist",
        "instructions": """You are the Shipping Specialist.
    - You check status with `get_order_details`.
    - You handle address changes.""",
        "model": "gpt-4o-mini",
        "tools": ["get_order_details", "transfer_back_to_orchestrator"]
    }
}
