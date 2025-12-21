from agents import Agent, function_tool
from app.domain.ops.client import ops_client
from app.services.milvus_service import milvus_service
from app.services.sync_service import sync_service
from app.domain.admin.client import admin_client
from app.domain.shopify.client import ShopifyClient
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
    # Stub
    return "Policies: Returns allowed within 30 days. Shipping takes 3-5 days."

@function_tool
async def product_search(query: str):
    """Search for products using natural language (e.g. 'blue summer dress')."""
    # 1. Embed Query
    vector = sync_service.embed_text(query)
    if not vector:
        return "Error: Could not process search query."
    
    # 2. Search Milvus
    # We need to search across ALL clients? Or the current client?
    # Context: The Agent is running for a specific client (loaded in ai.py).
    # However, 'milvus_service.search_image' requires 'client_name'.
    # IMPORTANT: We need the context of "which client is this?" 
    # For now, we'll hardcode or inject. 
    # Actually, the 'function_tool' context injection isn't setup.
    # We'll assume for this SINGLE TENANT DEMO usage or pass it.
    # WAIT: ai.py loads for a specific client.
    # But how does the tool know?
    # For this specific user request (building "our product search agent"), 
    # let's assume 'sania' or handle generic.
    # Real solution: Tool context injection. 
    # Hack for now: Search 'sania' since user explicitly asked for 'sania_products'.
    
    results = await milvus_service.search_image("sania", vector)
    
    if not results:
        return "No matching products found."
        
    # Format
    info = []
    for r in results:
        info.append(f"Product ID: {r['product_id']}, Score: {r['best_score']:.2f}, Store: {r['store_id']}")
        
    return "\n".join(info)

@function_tool
async def product_search_by_image(image_url: str):
    """Search for products using an image URL."""
    print(f"DEBUG: product_search_by_image called with {image_url}")
    # 1. Embed Image
    vector = await sync_service.embed_image_url(image_url)
    if not vector:
        print("DEBUG: Embedding failed")
        return "Error: Could not process image from URL."
    
    print("DEBUG: Embedding successful, searching Milvus...")
    
    # 2. Search Milvus (assuming current client context 'sania' for now)
    results = await milvus_service.search_image("sania", vector)
    
    if not results:
        return "No matching products found."
        
    # Format
    info = []
    for r in results:
        info.append(f"Product ID: {r['product_id']}, Score: {r['best_score']:.2f}, Store: {r['store_id']}")
        
    return "\n".join(info)

@function_tool
async def get_product_details(product_id: str, store_id: int):
    """Get live product details (price, stock) from Shopify given Product ID and Store ID."""
    # 1. Get Creds (Accessing 'sania' or passing client context? We'll assume 'sania' for the demo agent)
    client_app_name = "sania" 
    stores = await admin_client.get_shopify_credentials(client_app_name)
    
    # 2. Find Store
    target_store = next((s for s in stores if s.id == int(store_id)), None)
    if not target_store:
        return f"Error: Store {store_id} not found."
        
    # 3. Fetch from Shopify
    shopify_client = ShopifyClient(target_store)
    product = shopify_client.get_product(int(product_id))
    
    if not product:
        return "Product not found in Shopify."
        
    # 4. Format Info
    # Get range of prices if variants differ
    prices = [v.price for v in product.variants]
    price_str = prices[0] if prices else "N/A"
    if len(prices) > 1 and len(set(prices)) > 1:
        price_str = f"{min(prices)} - {max(prices)}"
        
    return f"Title: {product.title}\nPrice: {price_str}\nStatus: {product.status}\nURL: https://{target_store.shop_url}/products/{product.id}"

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
    "product_search": product_search,
    "product_search_by_image": product_search_by_image,
    "get_product_details": get_product_details,
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
        "tools": ["kb_search", "transfer_to_order_agent", "transfer_to_shipping_agent", "transfer_to_product_agent"]
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
    },
    "product_agent": {
        "name": "ProductAgent",
        "role": "specialist",
        "instructions": """You are the Product Specialist.
    - You help users find products using `product_search`.
    - If you find products, summarize them enthusiastically.
    - If the user wants to buy or has other questions, handoff back to `Orchestrator`.""",
        "model": "gpt-4o-mini",
        "tools": ["product_search", "product_search_by_image", "get_product_details", "transfer_back_to_orchestrator"]
    }
}
