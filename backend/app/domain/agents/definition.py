from agents import Agent, function_tool, RunContextWrapper
from app.domain.ops.client import ops_client
from app.services.milvus_service import milvus_service
from app.services.sync_service import sync_service
from app.domain.admin.client import admin_client
from app.domain.shopify.client import ShopifyClient
from app.domain.agents.context import ClientContext
from app.services.tracking_service import tracking_service
from app.core.config import settings
import random
import time
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal, List
from datetime import datetime

# --- Tool Functions ---

@function_tool
async def get_order_details(ctx: RunContextWrapper[ClientContext], order_id: str, contact: str = ""):
    """
    Get details of an order. Requires email or phone verification.
    If the user has not provided their email/phone, YOU MUST ASK for it.
    """
    # 1. Resolve Contact (Context > Arg)
    # Prefer context (authenticated user) overrides explicit argument
    final_contact = ctx.context.customer_email or ctx.context.customer_phone or contact
    
    # If explicit contact is provided, allow it (e.g. user typing email in chat)
    # But ideally we trust context first.
    
    if not final_contact:
        return "I need your email address or phone number to verify your identity before showing order details."

    print(f"DEBUG get_order_details: Fetching {order_id} for verification against '{final_contact}'")
    
    # 2. Fetch Order
    order_data = await ops_client.get_order(order_id)
    if not order_data:
        return "Order not found."
    
    # 3. Verify Contact Match
    # Normalize for comparison
    contact_norm = str(final_contact).lower().strip()
    
    # Extract order contact info (robust check)
    order_email = str(order_data.get("email", "")).lower()
    order_phone = str(order_data.get("phone", "") or order_data.get("customer", {}).get("phone", ""))
    
    # Check match (loose check for improved UX)
    if contact_norm in order_email or contact_norm in order_phone or order_phone in contact_norm:
         return json.dumps(order_data)
    else:
         print(f"DEBUG: Auth Failed. Contact '{contact_norm}' not in Order Email '{order_email}' or Phone '{order_phone}'")
         return "Verification failed. The provided email or phone number does not match this order."

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



# =========================================
# NEW ARCHITECTURE TOOLS (OTP + ACTIONS)
# =========================================

ActionType = Literal["cancel_order", "change_address"]

@function_tool
def human_handoff(ctx: RunContextWrapper[ClientContext], reason: str, user_message: str) -> str:
    """Escalate to a human support specialist."""
    return f"HANDOFF_TO_HUMAN: {reason} (User said: {user_message})"

# ---- Sales tools ----

@function_tool
def get_payment_methods(country: str = "LK") -> str:
    return json.dumps({"methods": ["Cash on Delivery", "Bank Transfer", "Card (if enabled)"]})

@function_tool
def get_delivery_info(country: str = "LK") -> str:
    if country == "LK":
        return json.dumps({"delivery_charge": "Calculated at checkout", "eta": "1–4 business days"})
    return json.dumps({"delivery_charge": "Calculated at checkout", "eta": "2–6 business days"})

@function_tool
def get_store_locations(country: str = "LK") -> str:
    if country == "LK":
        return json.dumps({"locations": ["Online store (nationwide delivery)"], "note": "Share city to check nearest pickup option if available."})
    return json.dumps({"locations": ["Online store (nationwide delivery)"], "note": "Share city to check nearest pickup option if available."})

# ---- Ops tools (OTP gated) ----

@function_tool
async def get_order_status_ops(ctx: RunContextWrapper[ClientContext], order_id: str) -> str:
    """Get status of an order for Ops agent."""
    # Using existing ops_client
    try:
        order = await ops_client.get_order(order_id)
        if not order:
            return json.dumps({"error": "ORDER_NOT_FOUND"})
        # Simple transform for LLM consumption
        return json.dumps(order)
    except Exception as e:
        return json.dumps({"error": str(e)})

@function_tool
def request_otp(ctx: RunContextWrapper[ClientContext], order_id: str, action: ActionType) -> str:
    """
    Request an OTP for a sensitive action (cancel_order, change_address).
    If the user is authenticated (Trusted Context), we skip the challenge and return 'VERIFIED_BY_CONTEXT'.
    """
    # 1. Trusted Context Check
    if ctx.context.is_authenticated:
        return json.dumps({
            "status": "SKIPPED", 
            "message": "User is authenticated via CRM (Email/Phone present). No OTP needed.",
            "otp_verified_automatically": True
        })

    # 2. Setup Challenge
    code = f"{random.randint(0, 999999):06d}"
    challenge = {
        "action": action,
        "order_id": order_id,
        "code": code,
        "expires_at_epoch": time.time() + 300,
        "attempts": 0,
        "verified": False
    }
    
    # Update Context (This must be persisted back to DB by the runner/endpoint)
    ctx.context.pending_otp = challenge
    
    # In a real app, you would send this via SMS/Email using `ops_client.send_otp`
    # payload = await ops_client.send_otp(...)
    
    # For now, returning the code in dev mode or masking it
    payload = {"sent_to": "User's Registered Phone", "expires_in_sec": 300}
    
    # If dev/debug, return code
    # if settings.DEBUG:
    #     payload["dev_otp_code"] = code
        
    return json.dumps(payload)

@function_tool
def verify_otp(ctx: RunContextWrapper[ClientContext], otp_code: str) -> str:
    """Verify the OTP code provided by the user."""
    ch = ctx.context.pending_otp
    
    if not ch:
        # Check if already authenticated via context
        if ctx.context.is_authenticated:
             return json.dumps({"verified": True, "method": "trusted_context"})
        return json.dumps({"error": "NO_PENDING_OTP"})
        
    # Check expiry
    if time.time() > ch.get("expires_at_epoch", 0):
        ctx.context.pending_otp = None
        return json.dumps({"error": "OTP_EXPIRED"})
        
    ch["attempts"] = ch.get("attempts", 0) + 1

    if otp_code.strip() == ch.get("code"):
        ch["verified"] = True
        return json.dumps({"verified": True, "action": ch.get("action"), "order_id": ch.get("order_id")})

    if ch["attempts"] >= 3:
        ctx.context.pending_otp = None
        return json.dumps({"verified": False, "error": "TOO_MANY_ATTEMPTS"})
        
    return json.dumps({"verified": False, "error": "INVALID_OTP", "attempts_used": ch["attempts"]})

@function_tool
async def cancel_order(ctx: RunContextWrapper[ClientContext], order_id: str) -> str:
    """Cancel an order. Requires OTP verification OR Trusted Context."""
    # Check Auth
    is_trusted = ctx.context.is_authenticated
    otp_verified = False
    
    if ctx.context.pending_otp:
        ch = ctx.context.pending_otp
        if ch.get("verified") and ch.get("action") == "cancel_order" and ch.get("order_id") == order_id:
            otp_verified = True
            
    if not (is_trusted or otp_verified):
         return json.dumps({"error": "OTP_REQUIRED_OR_NOT_VERIFIED"})

    # Execute
    # In real app: await ops_client.cancel_order(order_id)
    # Mocking for now as ops_client might not have this method
    try:
        # await ops_client.cancel_order(order_id)
        # Clear OTP state
        ctx.context.pending_otp = None
        return json.dumps({"ok": True, "order_id": order_id, "status": "Cancelled"})
    except Exception as e:
        return json.dumps({"error": str(e)})

@function_tool
async def update_order_address(ctx: RunContextWrapper[ClientContext], order_id: str, new_address: str) -> str:
    """Update order shipping address. Requires OTP verification OR Trusted Context."""
    # Check Auth
    is_trusted = ctx.context.is_authenticated
    otp_verified = False
    
    if ctx.context.pending_otp:
        ch = ctx.context.pending_otp
        if ch.get("verified") and ch.get("action") == "change_address" and ch.get("order_id") == order_id:
            otp_verified = True
            
    if not (is_trusted or otp_verified):
         return json.dumps({"error": "OTP_REQUIRED_OR_NOT_VERIFIED"})

    # Execute
    try:
        # await ops_client.update_address(order_id, new_address)
        ctx.context.pending_otp = None
        return json.dumps({"ok": True, "order_id": order_id, "shipping_address": new_address})
    except Exception as e:
         return json.dumps({"error": str(e)})

# ---- Support tools ----

@function_tool
def create_return_request(ctx: RunContextWrapper[ClientContext], order_id: str, reason: str) -> str:
    return_id = f"R-{random.randint(10000,99999)}"
    return json.dumps({"ok": True, "return_id": return_id, "order_id": order_id, "reason": reason})

@function_tool
def get_refund_status(ctx: RunContextWrapper[ClientContext], order_id: str) -> str:
    return json.dumps({"order_id": order_id, "refund_status": "Not started / In progress / Completed (demo)"})


# =========================================
# NEW AGENT DEFINITIONS
# =========================================

BASE_LANGUAGE_RULES = """
LANGUAGE RULES (Code-switching):
- Mirror the user’s writing style: English, Singlish (Sinhala written in English letters), Roman Urdu, or mixed.
- Do NOT switch scripts unless the user does.
- Keep messages short, clear. Ask at most 1 clarifying question when needed.
- Be respectful. No offensive slang.
"""

# Re-using the prompt logic using a dynamic context fetcher if needed, 
# or just static strings since instructions are static in this dict.

NEW_ARCHITECTURE_AGENTS = {
    "triage_agent": {
        "name": "Triage Agent",
        "instructions": f"""
You are the TRIAGE AGENT (Receptionist) for a fashion e-commerce support chat.

You must:
1) Handle greetings directly (hi/hello/good morning) with a friendly short reply.
2) Filter spam/junk: reply briefly that you can help with shopping, orders, returns.
3) CATEGORY 5 ESCALATION: If user is angry/abusive or mentions scams/consumer authority/police/legal threats:
   - Immediately call human_handoff(reason=..., user_message=...).
   - Do NOT route to other agents and do NOT argue.

4) GENERAL QUERIES & FAQs:
   - If the user asks for general company info (contact details, policies, about us), use `kb_search`.
   - If the answer is found, reply directly.

Otherwise route EXACTLY ONE specialist via handoff:
- Sales Agent: Category 1 (pre-purchase) + Category 4 (delivery/payment/location).
- Ops Agent: Category 2 (tracking, cancellations, address changes).
- Support Agent: Category 3 (returns, exchanges, damaged, refunds).

Rules:
- Do not solve non-greeting issues yourself; route.
- If message contains a 6-digit OTP OR a pending OTP exists, route to Ops.
{BASE_LANGUAGE_RULES}
""".strip(),
        "model": "gpt-4o-mini",
        # Note: handoff tools will be bound dynamically in ai.py by name mapping
        "tools": ["kb_search", "human_handoff", "transfer_to_sales_agent", "transfer_to_ops_agent", "transfer_to_support_agent"]
    },
    
    "sales_agent": {
        "name": "Sales Agent",
        "instructions": f"""
You are the SALES AGENT (Stylist). Goal: conversion + accurate info.

Handle only:
- Category 1 (Pre-purchase): availability, sizes, material, price/discounts, real photo requests.
- Category 4 (General): delivery, payment methods, shop/location info.

Tooling:
- Use search_products/get_product_details (from registry product_search etc) for product facts.
- Use get_delivery_info/get_payment_methods/get_store_locations for policies.
- If user asks about order tracking/cancel/address change: explain Ops handles it.
- If user asks about returns/refunds/damage: explain Support handles it.

Style: enthusiastic, friendly, helpful.
{BASE_LANGUAGE_RULES}
""".strip(),
        "model": "gpt-4o-mini",
        "tools": [
            "product_search", "product_search_by_image", "get_product_details", "get_delivery_info", 
            "get_payment_methods", "get_store_locations", "transfer_to_ops_agent", "transfer_to_support_agent"
        ]
    },
    
    "ops_agent": {
        "name": "Ops Agent",
        "instructions": f"""
You are the OPS AGENT (Manager). Goal: efficient and secure order management.

Handle only Category 2:
- Order tracking/status
- Address change
- Cancellation

OTP SECURITY:
- For cancellation OR address change: MUST request_otp then verify_otp.
- EXCEPTION: If the user is AUTHENTICATED (Trusted Context), request_otp will automatically skip. 
- You still MUST call request_otp to check if auth is valid.
- Only after verify_otp returns verified=true (or auth skipped), you may call cancel_order or update_order_address.
- If user sends OTP but NO pending OTP: explain you need to start verification and ask for order_id.

Workflow:
- Cancellation: get_order_status -> if can_cancel true -> request_otp(action="cancel_order") -> wait OTP -> verify_otp -> cancel_order
- Address change: get_order_status -> request_otp(action="change_address") -> wait OTP -> verify_otp -> update_order_address
Style: professional, direct, concise.
{BASE_LANGUAGE_RULES}
""".strip(),
        "model": "gpt-4o-mini",
        "tools": [
            "get_order_details", "request_otp", "verify_otp", "cancel_order", "update_order_address",
            "track_order" # Including track_order for tracking
        ]
    },
    
    "support_agent": {
        "name": "Support Agent",
        "instructions": f"""
You are the SUPPORT AGENT (Care Rep). Goal: retention + empathy.

Handle only Category 3:
- Returns/exchanges
- Damaged items
- Refund status

Tooling:
- Use create_return_request and get_refund_status.
- Ask for order_id if missing.
Style: empathetic, apologetic, patient.
{BASE_LANGUAGE_RULES}
""".strip(),
        "model": "gpt-4o-mini",
        "tools": ["create_return_request", "get_refund_status", "kb_search"]
    }
}

# Update Registry with new tools
TOOL_REGISTRY.update({
    "human_handoff": human_handoff,
    "get_payment_methods": get_payment_methods,
    "get_delivery_info": get_delivery_info,
    "get_store_locations": get_store_locations,
    "request_otp": request_otp,
    "verify_otp": verify_otp,
    "cancel_order": cancel_order,
    "update_order_address": update_order_address,
    "create_return_request": create_return_request,
    "get_refund_status": get_refund_status,
    "get_order_status_ops": get_order_status_ops
})
