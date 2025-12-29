"""
Tracking Service - Calls external order tracking API
"""
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings


# Status code to display name mapping
STATUS_CODES = {
    "5": "Not Approved",
    "10": "Approved",
    "20": "Available",
    "30": "Available",
    "35": "Added to Picklist",
    "40": "Added to Picklist",
    "50": "Picked",
    "55": "Picked",
    "58": "Picked",
    "60": "Picked",
    "70": "Packaging",
    "80": "Dispatched",
    "85": "Delivery Failed",
    "90": "Shipment Processing",
    "100": "Shipment Processing",
    "105": "Returned",
    "110": "Delivered",
}

# Category mapping for progress display
STATUS_CATEGORIES = {
    "5": "Approval Process",
    "10": "Processing",
    "20": "Processing",
    "30": "Processing",
    "35": "Processing",
    "40": "Processing",
    "50": "Processing",
    "55": "Processing",
    "58": "Processing",
    "60": "Processing",
    "70": "Packaging",
    "80": "Dispatched",
    "85": "Delivery Failed",
    "90": "Shipment Processing",
    "100": "Shipment Processing",
    "105": "Returned",
    "110": "Delivered",
}


class TrackingService:
    """Service for tracking orders via external API."""
    
    def __init__(self):
        self.base_url = settings.TRACKING_API_URL
    
    async def track_order(
        self, 
        app_name: str, 
        order_number: str, 
        contact: str, 
        tracking_key: str
    ) -> Dict[str, Any]:
        """
        Track an order using order number and customer contact.
        
        Args:
            app_name: The client/app identifier
            order_number: Order number to track
            contact: Customer email or phone
            tracking_key: Bearer token for API auth
        
        Returns:
            Tracking response dict or error dict
        """
        url = f"{self.base_url}/{app_name}"
        headers = {
            "Authorization": f"Bearer {tracking_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "order_number": order_number,
            "contact": contact
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "message": f"API error: {e.response.status_code}",
                "error": str(e)
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "message": "Failed to connect to tracking service",
                "error": str(e)
            }
    
    def format_tracking_response(self, response: Dict[str, Any]) -> str:
        """
        Format tracking API response into a customer-friendly plain text message.
        No markdown, warm and friendly tone, status-specific messaging.
        
        Args:
            response: The raw API response
            
        Returns:
            Customer-friendly status message
        """
        if not response.get("success"):
            error_msg = response.get('message', 'Unknown error')
            if "not found" in error_msg.lower():
                return "I couldn't find an order with those details. Could you please double-check your order number and the email/phone you used when placing the order?"
            return f"I'm having trouble looking up your order right now. Please try again in a moment, or let me connect you with our support team."
        
        order = response.get("order", {})
        if not order:
            return "I couldn't find any order details. Could you please verify your order number?"
        
        customer_name = order.get("customer_name", "").split()[0] if order.get("customer_name") else "there"
        order_number = order.get("order_number", "your order")
        
        # Analyze items to get overall status
        items = order.get("items", [])
        if not items:
            return f"Hi {customer_name}! I found your order {order_number} but couldn't retrieve the item details. Please try again or contact our support team."
        
        # Collect all item statuses
        item_statuses = []
        for item in items:
            timelines = item.get("timelines", [])
            if timelines:
                status_code = timelines[0].get("status_code", "")
                item_statuses.append({
                    "name": item.get("name", "Item"),
                    "qty": item.get("qty", "1"),
                    "status_code": status_code,
                    "category": timelines[0].get("category", ""),
                    "timeline": timelines[0]
                })
            else:
                item_statuses.append({
                    "name": item.get("name", "Item"),
                    "qty": item.get("qty", "1"),
                    "status_code": "",
                    "category": item.get("status", "Unknown"),
                    "timeline": {}
                })
        
        # Determine primary status (most common or most critical)
        status_codes = [s["status_code"] for s in item_statuses]
        primary_status = max(set(status_codes), key=status_codes.count) if status_codes else ""
        
        # Get shipment info
        shipments = order.get("shipments", {})
        courier_name = ""
        for awb, shipment in shipments.items():
            c_name = shipment.get("courier_name", "")
            if c_name and c_name.lower() != "internal":
                courier_name = c_name
                break
        
        # Build response based on status
        lines = []
        
        # Status-specific greeting and main message
        if primary_status == "110":  # Delivered
            lines.append(f"Hi {customer_name}!")
            lines.append("")
            lines.append(f"Great news! Your order {order_number} has been delivered successfully.")
            lines.append("")
            lines.append("We hope you love your purchase! If you have any questions about the items or need assistance, just let me know.")
            
        elif primary_status == "105":  # Returned
            lines.append(f"Hi {customer_name},")
            lines.append("")
            lines.append(f"Your order {order_number} has been marked as returned.")
            lines.append("")
            lines.append("If you have any questions about the return or need help with anything else, I'm here to assist!")
            
        elif primary_status == "85":  # Delivery Failed
            lines.append(f"Hi {customer_name},")
            lines.append("")
            lines.append(f"It looks like there was an issue delivering your order {order_number}.")
            lines.append("")
            lines.append("Our team will attempt delivery again soon. If you'd like to update your delivery details or have any questions, please let me know.")
            
        elif primary_status == "80":  # Dispatched
            lines.append(f"Hi {customer_name}!")
            lines.append("")
            lines.append(f"Your order {order_number} is on its way!")
            if courier_name:
                lines.append(f"It's being delivered by {courier_name}.")
            lines.append("")
            lines.append("You should receive it soon. I'll keep you updated on the delivery status!")
            
        elif primary_status in ["90", "100"]:  # Shipment Processing / Out for Delivery
            lines.append(f"Hi {customer_name}!")
            lines.append("")
            lines.append(f"Your order {order_number} is with the delivery partner and on its way to you!")
            if courier_name:
                lines.append(f"Courier: {courier_name}")
            lines.append("")
            lines.append("It should reach you very soon!")
            
        elif primary_status == "70":  # Packaging
            lines.append(f"Hi {customer_name}!")
            lines.append("")
            lines.append(f"Your order {order_number} is being packed with care!")
            lines.append("")
            lines.append("It will be dispatched shortly. I'll let you know once it's on the way.")
            
        elif primary_status in ["10", "20", "30", "35", "40", "50", "55", "58", "60"]:  # Processing stages
            lines.append(f"Hi {customer_name}!")
            lines.append("")
            lines.append(f"Your order {order_number} is being processed.")
            lines.append("")
            lines.append("Our team is working on it and it will be shipped soon. I'll keep you posted!")
            
        elif primary_status == "5":  # Not Approved / Pending
            lines.append(f"Hi {customer_name},")
            lines.append("")
            lines.append(f"Your order {order_number} is currently pending approval.")
            lines.append("")
            lines.append("Our team is reviewing it and you'll receive an update soon. If you have any questions, feel free to ask!")
            
        else:
            # Generic fallback
            lines.append(f"Hi {customer_name}!")
            lines.append("")
            lines.append(f"Here's the status of your order {order_number}:")
            lines.append("")
            for item in item_statuses:
                status_display = STATUS_CODES.get(item["status_code"], item["category"])
                lines.append(f"- {item['name']}: {status_display}")
            lines.append("")
            lines.append("Let me know if you need any other information!")
        
        # For multiple items with different statuses, add item breakdown
        unique_statuses = set(status_codes)
        if len(items) > 1 and len(unique_statuses) > 1:
            lines.append("")
            lines.append("Here's the status of each item:")
            for item in item_statuses:
                status_display = STATUS_CODES.get(item["status_code"], item["category"])
                lines.append(f"- {item['name']}: {status_display}")
        
        return "\n".join(lines)


# Singleton instance
tracking_service = TrackingService()
