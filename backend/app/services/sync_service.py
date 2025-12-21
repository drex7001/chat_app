import logging
from typing import List
from app.domain.admin.client import admin_client
from app.domain.shopify.client import ShopifyClient
from app.services.milvus_service import milvus_service
from datetime import datetime, timedelta
# Import sentence_transformers inside function or class to avoid heavy load at startup if possible?
# For now, top level is fine for "Agent" service.
from sentence_transformers import SentenceTransformer
from PIL import Image
import requests
from io import BytesIO

logger = logging.getLogger(__name__)

class SyncService:
    def __init__(self):
        # Load CLIP model (Multi-lingual / Vision)
        # Using 'clip-ViT-B-32' or similar. 
        # Note: This downloads the model ~600MB on first run.
        try:
            self.model = SentenceTransformer('clip-ViT-B-32')
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.model = None

    async def sync_client(self, app_name: str, client_id: int, store_id: int = None, limit: int = 10, fresh_start: bool = False): 
        logger.info(f"Starting sync for client: {app_name}, store: {store_id}, limit: {limit}, fresh_start: {fresh_start}")
        
        # 1. Get Credentials
        stores = await admin_client.get_shopify_credentials(app_name)
        if not stores:
            logger.warning(f"No storefronts found for {app_name}")
            return
            
        # If fresh start, force recreate collection immediately (clears DB)
        if fresh_start:
             milvus_service.ensure_collection(app_name, recreate=True)

        # Filter if store_id provided
        if store_id:
            stores = [s for s in stores if s.id == store_id]
            if not stores:
                logger.warning(f"Store {store_id} not found in client {app_name}")
                return

        for store in stores:
            try:
                # 2. Sync Logic per Store
                # For demo, just fetching recent 10 products. 
                # Real implementation: Use cursors/checkpoints from DB.
                shopify_client = ShopifyClient(store)
                products = shopify_client.get_products(limit=limit) # Use dynamic limit
                
                # --- DEDUPLICATION LOGIC ---
                # A. Collect all SKUs from this batch
                batch_skus = []
                for p in products:
                    for v in p.variants:
                        if v.sku:
                            batch_skus.append(v.sku)
                
                # B. Check which SKUs already exist in Milvus
                existing_skus = await milvus_service.check_existing_skus(app_name, batch_skus)
                logger.info(f"Store {store.name}: Checking {len(batch_skus)} SKUs. Found {len(existing_skus)} existing.")
                
                vectors_to_upsert = []
                
                for p in products:
                    # Get Main SKU (First variant)
                    main_sku = p.variants[0].sku if p.variants else None
                    if not main_sku:
                        continue # Skip products without SKU
                        
                    # C. Filter: If SKU exists, skip
                    if main_sku in existing_skus:
                        # logger.info(f"Skipping duplicate SKU: {main_sku}")
                        continue

                    for img in p.images:
                        if not img.src: continue
                        
                        # 3. Generate Embedding
                        embedding = self._generate_embedding_from_url(img.src)
                        if not embedding:
                            continue
                            
                        # 4. Prepare Vector
                        vectors_to_upsert.append({
                            "product_id": p.id,
                            "image_id": img.id,
                            "store_id": store.id,
                            "sku": main_sku, # Store SKU
                            "view_type": img.view_type, # 'unknown' default
                            "embedding": embedding
                        })
                
                # 5. Upsert to Milvus
                if vectors_to_upsert:
                    # If this is a breaking schema change (adding SKU), we might need to recreate collection once.
                    # For now, let's assume user manually drops or we handle via flag somewhere.
                    # Or we imply recreate=True if it fails? No, explicit is better.
                    # We'll pass recreate=False by default.
                    await milvus_service.upsert_vectors(app_name, vectors_to_upsert)
                    logger.info(f"Upserted {len(vectors_to_upsert)} images for store {store.name}")
                    
            except Exception as e:
                logger.error(f"Error syncing store {store.name}: {e}")

            except Exception as e:
                logger.error(f"Error syncing store {store.name}: {e}")

    async def sync_product(self, app_name: str, store_id: int, product_id: int):
        """
        Syncs a single product for a specific store.
        """
        logger.info(f"Syncing single product {product_id} for store {store_id} ({app_name})")
        
        # 1. Get Creds & Store
        stores = await admin_client.get_shopify_credentials(app_name)
        target_store = next((s for s in stores if s.id == store_id), None)
        
        if not target_store:
            logger.error(f"Store {store_id} not found")
            return
            
        try:
            # 2. Fetch from Shopify
            shopify_client = ShopifyClient(target_store)
            product = shopify_client.get_product(product_id)
            
            if not product:
                logger.warning(f"Product {product_id} not found in Shopify")
                return

            # 3. Process (Simplified Logic compared to bulk)
            # We don't need to check existing SKUs if we assume this is an intentional overwrite/update.
            # But we should still respect the Schema.
            
            vectors_to_upsert = []
            main_sku = product.variants[0].sku if product.variants else None
            
            if main_sku:
                for img in product.images:
                    if not img.src: continue
                    
                    # Generate Embedding
                    embedding = self._generate_embedding_from_url(img.src)
                    if not embedding: continue
                    
                    vectors_to_upsert.append({
                        "product_id": product.id,
                        "image_id": img.id,
                        "store_id": target_store.id,
                        "sku": main_sku,
                        "view_type": img.view_type,
                        "embedding": embedding
                    })
            
            # 4. Upsert
            if vectors_to_upsert:
                await milvus_service.upsert_vectors(app_name, vectors_to_upsert)
                logger.info(f"Successfully synced product {product_id} with {len(vectors_to_upsert)} images")
                return True
            else:
                logger.warning("No vectors generated (No SKU or No Images)")
                return False
                
        except Exception as e:
            logger.error(f"Error syncing product {product_id}: {e}")
            raise e

    async def embed_image_url(self, url: str) -> List[float]:
        # Async wrapper
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._generate_embedding_from_url, url)

    def _generate_embedding_from_url(self, url: str) -> List[float]:
        try:
            import os
            logger.info(f"Generating embedding for URL: {url}")
            
            # OPTIMIZATION: Handle localhost/static urls OR relative paths as local files
            target_url = url
            
            # Case 1: Relative path /static/...
            if url.startswith("/static/"):
                 try:
                    split_path = url.split("/static/")[-1] 
                    local_path = os.path.join("app/static", split_path)
                    if os.path.exists(local_path):
                        target_url = local_path
                        logger.info(f"Resolved relative URL {url} to local path {target_url}")
                    else:
                        logger.warning(f"Constructed local path {local_path} does not exist for relative URL {url}")
                 except Exception as ex:
                    logger.error(f"Error parsing relative URL: {ex}")

            # Case 2: Absolute localhost URL
            elif "localhost" in url and "/static/" in url:
                # Extract relative path: http://localhost:8000/static/uploads/x.png -> app/static/uploads/x.png
                try:
                    split_path = url.split("/static/")[-1]
                    local_path = os.path.join("app/static", split_path)
                    if os.path.exists(local_path):
                        target_url = local_path
                        logger.info(f"Resolved localhost URL {url} to local path {target_url}")
                    else:
                        logger.warning(f"Constructed local path {local_path} does not exist for URL {url}")
                except Exception as ex:
                    logger.error(f"Error parsing localhost URL: {ex}")

            # Check for local file
            if os.path.exists(target_url):
                 logger.info(f"Opening local file: {target_url}")
                 image = Image.open(target_url)
            else:
                 # Helper to download and embed
                 logger.info(f"Downloading from network: {target_url}")
                 response = requests.get(target_url, stream=True, timeout=5)
                 response.raise_for_status()
                 image = Image.open(BytesIO(response.content))
            
            # SentenceTransformer Encode
            logger.info("Encoding image...")
            embedding = self.model.encode(image)
            logger.info("Encoding successful")
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Embedding error for {url}: {e}")
            return None

    def embed_text(self, text: str) -> List[float]:
        try:
            if not self.model:
                return None
            # encoding text
            embedding = self.model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Text embedding error: {e}")
            return None

sync_service = SyncService()
