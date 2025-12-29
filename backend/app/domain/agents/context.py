from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class ClientContext:
    """
    Context passed to all agent tools during a run.
    This enables tools to access client-specific information without hardcoding.
    """
    app_name: str  # Client's external_id (e.g., "sania", "momina", etc.)
    policies: Dict[str, Any] = field(default_factory=dict)  # {documents: [{name, content}], rules: {}}
    
    # Customer information (for order tracking)
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
    
    # Order information (latest order if available)
    order_number: Optional[str] = None
    order_data: Optional[Dict[str, Any]] = None
    
    # Tracking API key (loaded from client config)
    tracking_key: Optional[str] = None

