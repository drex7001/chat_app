import shopify
import threading
from typing import List, Optional
from datetime import datetime
from app.domain.admin.client import StorefrontCreds
from app.domain.shopify.models import ShopifyProduct, ShopifyImage, ShopifyVariant

class ShopifyClient:
    def __init__(self, creds: StorefrontCreds):
        self.creds = creds
        self.shop_url = creds.shop_url
        self.access_token = creds.access_token
        
        # Shopify Python SDK setup (context manager style or session)
        self.session = shopify.Session(self.shop_url, "2024-01", self.access_token)
        
    def _activate_session(self):
        shopify.ShopifyResource.activate_session(self.session)
    
    def _clear_session(self):
        shopify.ShopifyResource.clear_session()

    def get_products(self, limit: int = 10, cursor: Optional[str] = None) -> List[ShopifyProduct]:
        """
        Fetch products using REST/GraphQL. 
        Note: The official python SDK uses REST by default for resources. 
        For efficiency/cursor, GraphQL is better, but REST is easier to start.
        """
        self._activate_session()
        try:
            # Using REST for now for simplicity
            kwargs = {'limit': limit}
            if cursor:
                kwargs['page_info'] = cursor
                
            products = shopify.Product.find(**kwargs)
            
            result = []
            for p in products:
                # Convert ShopifyResource to our Pydantic Model
                # Handles basics. 
                # Note: shopify types are dynamic.
                images = [
                    ShopifyImage(
                        id=img.id, 
                        product_id=getattr(img, 'product_id', p.id), 
                        position=getattr(img, 'position', 0), 
                        src=img.src, 
                        width=getattr(img, 'width', 0), 
                        height=getattr(img, 'height', 0),
                        alt=getattr(img, 'alt', None)
                    ) for img in p.images
                ]
                
                variants = [
                    ShopifyVariant(
                        id=v.id,
                        product_id=getattr(v, 'product_id', p.id),
                        title=getattr(v, 'title', ''),
                        price=getattr(v, 'price', '0.00'),
                        sku=getattr(v, 'sku', ''),
                        position=getattr(v, 'position', 0)
                    ) for v in p.variants
                ]

                sp = ShopifyProduct(
                    id=p.id,
                    title=p.title,
                    body_html=p.body_html,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                    vendor=p.vendor,
                    product_type=p.product_type,
                    status=getattr(p, 'status', 'active'),
                    images=images,
                    variants=variants
                )
                result.append(sp)
                
            return result
        finally:
            self._clear_session()

    def get_product(self, product_id: int) -> Optional[ShopifyProduct]:
        """
        Fetch single product by ID.
        Retries with 'ids' filter if direct lookup fails (common API quirk).
        """
        self._activate_session()
        try:
            try:
                # 1. Try Direct Lookup
                p = shopify.Product.find(product_id)
                if p:
                    return self._to_pydantic(p)
            except Exception as e:
                print(f"Direct lookup for {product_id} failed: {e}")
                
            try:
                # 2. Try Index with ID filter
                products = shopify.Product.find(ids=str(product_id))
                if products and len(products) > 0:
                    print(f"Fallback lookup found product {product_id}")
                    return self._to_pydantic(products[0])
            except Exception as ex:
                print(f"Fallback lookup for {product_id} failed: {ex}")
                import traceback
                traceback.print_exc()
                
            return None
        finally:
            self._clear_session()

    def get_updated_products_for_sync(self, since: datetime) -> List[ShopifyProduct]:
        """
        Fetch products updated after `since`.
        Iterates pages to get ALL changes.
        """
        self._activate_session()
        try:
            # REST API supports updated_at_min
            products = shopify.Product.find(updated_at_min=since.isoformat(), limit=250)
            
            # Simple conversion logic (DRY later)
            result = []
            for p in products:
                # ... same conversion ...
                # (Ideally refactor conversion to helper)
                 result.append(self._to_pydantic(p))
            
            # TODO: Handle pagination for ALL products
            return result
        finally:
            self._clear_session()

    def _to_pydantic(self, p) -> ShopifyProduct:
        # Helper to convert SDK object to Pydantic
        images = [
            ShopifyImage(
                id=img.id, 
                product_id=getattr(img, 'product_id', p.id), 
                position=getattr(img, 'position', 0), 
                src=img.src, 
                width=getattr(img, 'width', 0), 
                height=getattr(img, 'height', 0),
                alt=getattr(img, 'alt', None)
            ) for img in p.images
        ]
        variants = [
            ShopifyVariant(
                id=v.id, 
                product_id=getattr(v, 'product_id', p.id), 
                title=getattr(v, 'title', ''), 
                price=getattr(v, 'price', '0.00'), 
                sku=getattr(v, 'sku', ''), 
                position=getattr(v, 'position', 0)
            ) for v in p.variants
        ]
        return ShopifyProduct(
            id=p.id, 
            title=p.title, 
            body_html=getattr(p, 'body_html', ''), 
            created_at=p.created_at, 
            updated_at=p.updated_at, 
            vendor=p.vendor, 
            product_type=p.product_type, 
            status=getattr(p, 'status', 'active'), 
            images=images, 
            variants=variants
        )
