from agents import Agent, function_tool, RunContextWrapper
from app.domain.ops.client import ops_client
from app.services.milvus_service import milvus_service
from app.services.sync_service import sync_service
from app.domain.admin.client import admin_client
from app.domain.shopify.client import ShopifyClient
from app.domain.agents.context import ClientContext
from app.services.tracking_service import tracking_service
from app.core.config import settings
# from app.core.llm import llm_client

# --- Tool Functions ---

@function_tool
async def get_order_details(order_id: str):
    """Get details of an order."""
    return await ops_client.get_order(order_id)

@function_tool
def kb_search(ctx: RunContextWrapper[ClientContext], query: str):
    """Search knowledge base for policy information, FAQs, and company guidelines."""
    policies = ctx.context.policies
    documents = policies.get("documents", [])
    
    if not documents:
        return "No policy documents available for this client."
    
    # Search for relevant documents
    query_lower = query.lower()
    query_words = query_lower.split()
    
    # Score each document by keyword matches
    scored_docs = []
    for doc in documents:
        content = doc.get("content", "").lower()
        name = doc.get("name", "").lower()
        
        # Count matching words
        score = sum(1 for word in query_words if word in content or word in name)
        if score > 0:
            scored_docs.append((score, doc))
    
    # Sort by score (highest first)
    scored_docs.sort(key=lambda x: x[0], reverse=True)
    
    if scored_docs:
        # Return matching documents
        results = []
        for score, doc in scored_docs[:3]:  # Top 3 matches
            results.append(f"**{doc['name']}**: {doc['content']}")
        return "\n\n".join(results)
    
    # No direct matches - return all policies as fallback context
    all_policies = [f"**{d['name']}**: {d['content']}" for d in documents]
    return "Available policies:\n\n" + "\n\n".join(all_policies)

@function_tool
async def product_search(ctx: RunContextWrapper[ClientContext], query: str):
    """Search for products using natural language (e.g. 'blue summer dress')."""
    # 1. Embed Query
    vector = sync_service.embed_text(query)
    if not vector:
        return "Error: Could not process search query."
    
    # 2. Search Milvus using client context
    app_name = ctx.context.app_name
    results = await milvus_service.search_image(app_name, vector)
    
    if not results:
        return "No matching products found."
        
    # Format
    info = []
    for r in results:
        info.append(f"Product ID: {r['product_id']}, Score: {r['best_score']:.2f}, Store: {r['store_id']}")
        
    return "\n".join(info)

@function_tool
async def product_search_by_image(ctx: RunContextWrapper[ClientContext], image_url: str):
    """Search for products using an image URL."""
    app_name = ctx.context.app_name
    print(f"DEBUG: product_search_by_image called with {image_url} for client {app_name}")
    
    # 1. Embed Image
    vector = await sync_service.embed_image_url(image_url)
    if not vector:
        print("DEBUG: Embedding failed")
        return "Error: Could not process image from URL."
    
    print(f"DEBUG: Embedding successful, searching Milvus for {app_name}...")
    
    # 2. Search Milvus using client context
    results = await milvus_service.search_image(app_name, vector)
    
    if not results:
        return "No matching products found. The image may not match any products in our catalog."
        
    # Only return the BEST match - prevents agent from fetching multiple products
    best = results[0]
    match_quality = "HIGH" if best['best_score'] >= 0.7 else "MEDIUM" if best['best_score'] >= 0.5 else "LOW"
    
    print(f"DEBUG: Best match - Product {best['product_id']} with score {best['best_score']:.2f}")
    
    return f"Best Match: Product ID {best['product_id']}, Similarity: {best['best_score']:.0%} ({match_quality}), Store ID: {best['store_id']}"

@function_tool
async def get_product_details(ctx: RunContextWrapper[ClientContext], product_id: str, store_id: int):
    """Get live product details (price, stock, currency) from Shopify given Product ID and Store ID."""
    # 1. Get Creds using client context
    app_name = ctx.context.app_name
    stores = await admin_client.get_shopify_credentials(app_name)
    
    # 2. Find Store
    target_store = next((s for s in stores if s.id == int(store_id)), None)
    if not target_store:
        return f"Error: Store {store_id} not found."
        
    # 3. Fetch from Shopify
    shopify_client = ShopifyClient(target_store)
    product = shopify_client.get_product(int(product_id))
    
    if not product:
        return "Product not found in Shopify."
    
    # 4. Get shop info for currency
    shop_info = shopify_client.get_shop_info()
    currency = shop_info.get("currency", "USD")
        
    # 5. Calculate price range
    prices = [float(v.price) for v in product.variants if v.price]
    if prices:
        min_price, max_price = min(prices), max(prices)
        if min_price == max_price:
            price_str = f"{currency} {min_price:,.2f}"
        else:
            price_str = f"{currency} {min_price:,.2f} - {max_price:,.2f}"
    else:
        price_str = "Price not available"
    
    # 6. Calculate stock
    stock_quantities = [v.inventory_quantity for v in product.variants if v.inventory_quantity is not None]
    total_stock = sum(stock_quantities) if stock_quantities else None
    
    if total_stock is None:
        stock_status = "Stock info not available"
    elif total_stock <= 0:
        stock_status = "OUT_OF_STOCK"
    elif total_stock < 5:
        stock_status = f"LOW_STOCK ({total_stock} left)"
    else:
        stock_status = f"IN_STOCK ({total_stock} available)"
    
    # 7. Build proper URL using handle (not product ID)
    if product.handle:
        product_url = f"https://{target_store.shop_url}/products/{product.handle}"
    else:
        product_url = f"https://{target_store.shop_url}/products/{product.id}"
        
    return f"Title: {product.title}\nPrice: {price_str}\nStock: {stock_status}\nStatus: {product.status}\nURL: {product_url}"

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

@function_tool
def transfer_to_human(ctx: RunContextWrapper[ClientContext]):
    """Transfer the conversation to a human agent when customer explicitly requests human support."""
    return "HANDOFF_TO_HUMAN: Customer has requested to speak with a human agent. The conversation will be transferred to a human support representative who will assist shortly."


@function_tool
async def track_order(ctx: RunContextWrapper[ClientContext], order_number: str = "", contact: str = ""):
    """
    Track an order using order number and customer contact (email or phone).
    
    Args:
        order_number: The order number to track. If not provided, uses context.
        contact: Customer email or phone. If not provided, uses context.
    
    Returns:
        Formatted tracking information with item-wise status and timeline.
    """
    # Debug logging
    print(f"DEBUG track_order: Received order_number='{order_number}', contact='{contact}'")
    print(f"DEBUG track_order: Context - order_number={ctx.context.order_number}, email={ctx.context.customer_email}, phone={ctx.context.customer_phone}")
    
    # Get order number - prefer context, fallback to parameter
    final_order_number = ctx.context.order_number or order_number
    
    # Get contact - ALWAYS prefer context values over parameters
    # This is because the AI might pass masked values from system message
    # Context has the real, unmasked values
    final_contact = None
    
    # First try context (unmasked values)
    if ctx.context.customer_email:
        final_contact = ctx.context.customer_email
        print(f"DEBUG track_order: Using context email: {final_contact}")
    elif ctx.context.customer_phone:
        final_contact = ctx.context.customer_phone
        print(f"DEBUG track_order: Using context phone: {final_contact}")
    # Only use passed contact if context has nothing AND it's not masked
    elif contact and "***" not in contact:
        final_contact = contact
        print(f"DEBUG track_order: Using parameter contact: {final_contact}")
    
    tracking_key = ctx.context.tracking_key or settings.TRACKING_KEY
    app_name = ctx.context.app_name
    
    print(f"DEBUG track_order: Final values - order_number='{final_order_number}', contact='{final_contact}', app_name='{app_name}'")
    print(f"DEBUG track_order: tracking_key present = {bool(tracking_key)}")
    
    # Validate required fields
    if not final_order_number:
        return "I need an order number to track your order. Could you please provide your order number?"
    
    if not final_contact:
        return "I need your email address or phone number to look up your order. Could you please provide either one?"
    
    if not tracking_key:
        print("ERROR track_order: No tracking_key configured!")
        return "I'm sorry, order tracking is not configured for this store. Please contact support for order status updates."
    
    # Call tracking API
    print(f"DEBUG track_order: Calling tracking API...")
    response = await tracking_service.track_order(
        app_name=app_name,
        order_number=final_order_number,
        contact=final_contact,
        tracking_key=tracking_key
    )
    
    print(f"DEBUG track_order: API response success={response.get('success')}")
    if not response.get('success'):
        print(f"DEBUG track_order: API error - {response.get('message', 'Unknown')}")
    
    # Format and return response
    result = tracking_service.format_tracking_response(response)
    print(f"DEBUG track_order: Formatted result length = {len(result)} chars")
    return result


TOOL_REGISTRY = {
    "get_order_details": get_order_details,
    "kb_search": kb_search,
    "product_search": product_search,
    "product_search_by_image": product_search_by_image,
    "get_product_details": get_product_details,
    "transfer_to_human": transfer_to_human,
    "track_order": track_order,
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
    - You can track order status with `track_order` - this gives item-wise tracking with timeline.
    - You can PROPOSE cancellations (but cannot execute them directly yet).
    - If customer asks about tracking/status, use `track_order` first.
    - If order number or contact is not available in context, ask the customer for it.
    - If the user has a general question, handoff back to `Orchestrator`.""",
        "model": "gpt-4o-mini",
        "tools": ["get_order_details", "track_order", "transfer_back_to_orchestrator"]
    },
    "shipping_agent": {
        "name": "ShippingAgent",
        "role": "specialist",
        "instructions": """You are the Shipping Specialist.
    - Use `track_order` to get detailed item-wise tracking with courier info and timeline.
    - Check customer context for order number and email/phone - if missing, ask the customer.
    - You handle address changes.
    - Explain tracking status clearly: Processing, Packaging, Dispatched, Delivered, etc.""",
        "model": "gpt-4o-mini",
        "tools": ["track_order", "transfer_back_to_orchestrator"]
    },
    "product_agent": {
        "name": "ProductAgent",
        "role": "specialist",
        "instructions": """You are the Product Specialist.
    - If you see `[User uploaded image: URL]`, YOU MUST call `product_search_by_image(URL)`. DO NOT ask for description.
    - If user provides a text query, use `product_search`.
    - IMPORTANT: Focus on the BEST MATCH (Match 1 with highest similarity) FIRST.
    - Only call `get_product_details` for the TOP 1 result initially.
    - Present the best matching product to the user. Only show alternatives if:
      a) User asks for more options, OR
      b) The best match is unavailable/out of stock
    - If the user wants to buy or has other questions, handoff back to `Orchestrator` only AFTER finding product info.""",
        "model": "gpt-4o-mini",
        "tools": ["product_search", "product_search_by_image", "get_product_details", "transfer_back_to_orchestrator"]
    }
}
