from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class ClientContext:
    """
    Context passed to all agent tools during a run.
    This enables tools to access client-specific information without hardcoding.
    """
    app_name: str  # Client's external_id (e.g., "sania", "momina", etc.)
    policies: Dict[str, Any] = field(default_factory=dict)  # {documents: [{name, content}], rules: {}}
    
    # Future fields can be added as needed:
    # ops_base_url: str = None  # For OPS API calls
    # crm_base_url: str = None  # For CRM API calls
