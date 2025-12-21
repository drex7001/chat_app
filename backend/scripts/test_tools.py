import asyncio
import sys
import os

# Add backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv() # Load BEFORE imports

from app.domain.agents.definition import product_search_by_image
from app.services.sync_service import sync_service
from app.core.config import settings

print(f"DEBUG: MILVUS_URI is: {settings.MILVUS_URI}")
print(f"DEBUG: MILVUS_TOKEN is: {'*' * 5 if settings.MILVUS_TOKEN else 'None'}")

# Mock the Milvus service to avoid needing full DB stack if just testing embedding/download
# Or actually use the real one if we want full E2E tool test.
# Let's try to run the actual tool.

async def test_image_search():
    filename = "search.png" 
    url = f"http://localhost:8000/static/uploads/{filename}"
    
    print(f"Testing product_search_by_image logic with {url}")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # 1. Embed Image (Direct Call)
        print("1. Embedding Image...")
        vector = await sync_service.embed_image_url(url)
        if not vector:
            print("Error: Could not process image from URL.")
            return

        print(f"Embedding success. Vector length: {len(vector)}")
        
        # 2. Search Milvus
        print("2. Searching Milvus...")
        from app.services.milvus_service import milvus_service
        # Connect & Search
        milvus_service.check_connection()
        results = await milvus_service.search_image("sania", vector)
        
        print("--- Search Results ---")
        print(results)
        
        if not results:
            print("No results found.")
            return

        # 3. Get Details for Top Result
        top_hit = results[0]
        pid = top_hit['product_id']
        sid = top_hit['store_id']
        print(f"\n3. Fetching Details for Product {pid} from Store {sid}...")
        
        from app.domain.admin.client import admin_client
        from app.domain.shopify.client import ShopifyClient
        
        # Logic from get_product_details
        client_app_name = "sania" 
        stores = await admin_client.get_shopify_credentials(client_app_name)
        target_store = next((s for s in stores if s.id == int(sid)), None)
        
        if target_store:
            shopify_client = ShopifyClient(target_store)
            product = shopify_client.get_product(int(pid))
            
            if product:
                print("\n--- Shopify Product Details ---")
                print(f"Title: {product.title}")
                print(f"Status: {product.status}")
                prices = [v.price for v in product.variants]
                print(f"Price: {prices}")
                print(f"URL: https://{target_store.shop_url}/products/{product.id}")
            else:
                print("Product not found in Shopify.")
        else:
             print(f"Store {sid} not found in credentials.")

    except Exception as e:
        print(f"Caught exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == 'win32':
         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_image_search())
