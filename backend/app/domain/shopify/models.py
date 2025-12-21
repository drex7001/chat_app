from typing import List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

class ShopifyImage(BaseModel):
    id: int
    product_id: int
    position: int
    src: str
    alt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    updated_at: Optional[datetime] = None
    # Enhanced fields
    view_type: str = "unknown" 

class ShopifyVariant(BaseModel):
    id: int
    product_id: int
    title: str
    price: str
    sku: Optional[str] = None
    position: int
    inventory_policy: Optional[str] = None
    compare_at_price: Optional[str] = None
    option1: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    taxable: bool = True
    barcode: Optional[str] = None
    # image_id: Optional[int] = None # Can be null
    inventory_quantity: Optional[int] = None
    requires_shipping: bool = True

class ShopifyProduct(BaseModel):
    id: int
    title: str
    body_html: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    created_at: Optional[datetime] = None
    handle: Optional[str] = None
    updated_at: Optional[datetime] = None
    tags: Optional[str] = None
    status: str = "active"
    
    variants: List[ShopifyVariant] = []
    images: List[ShopifyImage] = []
    
    # Helpers
    @property
    def main_image(self) -> Optional[str]:
        if self.images:
            return self.images[0].src
        return None

class ProductListResponse(BaseModel):
    products: List[ShopifyProduct]
    next_cursor: Optional[str] = None
    previous_cursor: Optional[str] = None
