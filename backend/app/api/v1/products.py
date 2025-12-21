from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from typing import List, Optional
from app.domain.admin.client import admin_client
from app.domain.shopify.client import ShopifyClient
from app.domain.shopify.models import ProductListResponse, ShopifyProduct
from app.services.sync_service import sync_service
from app.services.milvus_service import milvus_service
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.domain.clients import models as client_models
from pydantic import BaseModel

router = APIRouter()

# --- Search Schemas ---
class SearchRequest(BaseModel):
    query_text: Optional[str] = None # Future use
    query_image_vector: Optional[List[float]] = None # Raw vector for now (frontend generates?) 
    # OR better: Frontend sends Image URL or Base64, Backend embeds it.
    # For Phase 1 demo: Let's assume Backend embeds from a URL provided in body?
    image_url: Optional[str] = None 
    top_k: int = 20

class SearchResponse(BaseModel):
    product_id: int
    store_id: int
    score: float
    vote_count: int
    product_details: Optional[ShopifyProduct] = None

# --- Helpers ---
from sqlalchemy import select

async def get_client_app_name(db: Session, client_id: int) -> str:
    result = await db.execute(select(client_models.Client).where(client_models.Client.id == client_id))
    client = result.scalars().first()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    # Assuming external_id maps to 'app_name' or subdomain in Admin API
    return client.external_id

# --- Endpoints ---

@router.get("/{client_id}/products")
async def get_products(
    client_id: int, 
    store_id: Optional[int] = None, 
    limit: int = 20, 
    cursor: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get products for a client. 
    1. Fetch Creds from Admin.
    2. Select specific store (or default to first).
    3. Call Shopify.
    """
    app_name = await get_client_app_name(db, client_id)
    print(f"[DEBUG] Fetching creds for app: {app_name}")
    
    try:
        creds_list = await admin_client.get_shopify_credentials(app_name)
    except Exception as e:
        print(f"[ERROR] Admin Creds Fetch Failed: {e}")
        # Helpful message for user
        raise HTTPException(status_code=502, detail=f"Failed to fetch credentials from Admin API. Check backend logs. Error: {str(e)}")
    
    if not creds_list:
        raise HTTPException(status_code=404, detail="No shopify credentials found for client")
    
    # Select Store
    selected_cred = None
    if store_id:
        selected_cred = next((c for c in creds_list if c.id == store_id), None)
    
    if not selected_cred:
        selected_cred = creds_list[0] # Default to first
        
    # Call Shopify
    try:
        shopify_client = ShopifyClient(selected_cred)
        products = shopify_client.get_products(limit=limit, cursor=cursor)
        
        # Prepare Response
        return {
            "products": products, 
            "store_id": selected_cred.id, 
            "store_name": selected_cred.name,
            "available_stores": [{"id": c.id, "name": c.name} for c in creds_list]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Shopify Data Error: {e}")
        raise HTTPException(status_code=500, detail=f"Shopify Error: {str(e)}")

@router.post("/{client_id}/products/sync")
async def trigger_sync(
    client_id: int, 
    background_tasks: BackgroundTasks,
    store_id: Optional[int] = Query(None), # Optional Store ID
    limit: int = 50, # Default to 50 as requested
    fresh_start: bool = False, # Force drop/recreate collection
    db: Session = Depends(get_db)
):
    """
    Trigger async sync for client.
    Can specify store_id to sync only one store.
    """
    app_name = await get_client_app_name(db, client_id)
    background_tasks.add_task(sync_service.sync_client, app_name, client_id, store_id, limit, fresh_start)
    return {"status": "Sync started in background"}

@router.get("/{client_id}/products/{product_id}/sync-status")
async def get_product_sync_status(
    client_id: int, 
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    Check if a product exists in Milvus. Returns vector count.
    """
    app_name = await get_client_app_name(db, client_id)
    count = await milvus_service.count_product_vectors(app_name, product_id)
    return {"product_id": product_id, "vector_count": count, "is_synced": count > 0}

@router.post("/{client_id}/products/{product_id}/sync")
async def sync_single_product(
    client_id: int, 
    product_id: int,
    background_tasks: BackgroundTasks,
    store_id: int = Query(..., description="Store ID is required for single product sync"),
    db: Session = Depends(get_db)
):
    """
    Sync a specific product.
    """
    app_name = await get_client_app_name(db, client_id)
    background_tasks.add_task(sync_service.sync_product, app_name, store_id, product_id)
    return {"status": f"Sync for product {product_id} started"}

@router.post("/{client_id}/search", response_model=List[SearchResponse])
async def search_products(
    client_id: int,
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    Image Search + Majority Voting.
    1. Embed Image (from URL or Body).
    2. Milvus Search (Vote).
    3. Fetch Details from Shopify (for top results).
    """
    app_name = await get_client_app_name(db, client_id)
    
    # 1. Embed
    if request.image_url:
        vector = sync_service._generate_embedding_from_url(request.image_url)
    elif request.query_image_vector:
        vector = request.query_image_vector
    else:
        raise HTTPException(status_code=400, detail="Must provide image_url or vector")
        
    if not vector:
        raise HTTPException(status_code=500, detail="Failed to generate embedding")
        
    # 2. Search (Milvus)
    # Note: Using app_name as collection identifier
    results = await milvus_service.search_image(app_name, vector, top_k=request.top_k)
    
    # 3. Optimize Fetching Details
    # We need to fetch details for these products. 
    # They might belong to different stores.
    # Group by store_id
    response_items = []
    
    # Lazy load creds
    creds_list = await admin_client.get_shopify_credentials(app_name)
    creds_map = {c.id: c for c in creds_list}
    
    # TODO: In production, optimize this to bulk fetch. 
    # For now, simplistic loop (Top 5-10 is small).
    for res in results:
        pid = res["product_id"]
        sid = res["store_id"]
        
        product_details = None
        if sid in creds_map:
            # We don't have get_product(id) in ShopifyClient yet, let's assume it exists or stub it
            # For Phase 1 demo, we might skip full details or fetch simplistic
            pass 
            
        response_items.append(SearchResponse(
            product_id=pid,
            store_id=sid,
            score=res["best_score"],
            vote_count=res["vote_count"],
            product_details=None # Populate if possible
        ))
        
    return response_items
