"""
Test script to verify tracking API is working correctly
"""
import asyncio
import httpx
import os
import sys

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Note: python-dotenv not installed, using environment variables only")

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_tracking_api():
    """Test the tracking API directly"""
    
    # Read tracking key from .env or use empty
    tracking_key = os.getenv("TRACKING_KEY", "")
    
    if not tracking_key:
        print("⚠️  TRACKING_KEY not found in environment")
        print("Please set TRACKING_KEY environment variable or check .env file")
        return
    
    # Test parameters
    app_name = "asimjofa"  # Change this to your app name
    order_number = "AJ1781509"
    contact = "shafaqzubair97@gmail.com"
    
    url = f"https://track.siardigital.com/api/track/{app_name}"
    headers = {
        "Authorization": f"Bearer {tracking_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "order_number": order_number,
        "contact": contact
    }
    
    print(f"🔍 Testing Tracking API")
    print(f"   URL: {url}")
    print(f"   Order: {order_number}")
    print(f"   Contact: {contact}")
    print(f"   Token: {tracking_key[:10]}..." if len(tracking_key) > 10 else f"   Token: {tracking_key}")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            print(f"📡 Response Status: {response.status_code}")
            print(f"📦 Response Body:")
            
            import json
            try:
                data = response.json()
                print(json.dumps(data, indent=2))
                
                # Check if successful
                if data.get("success"):
                    print("\n✅ API call successful!")
                    order = data.get("order", {})
                    items = order.get("items", [])
                    print(f"   Found {len(items)} items in order")
                    for item in items:
                        timelines = item.get("timelines", [])
                        if timelines:
                            status_code = timelines[0].get("status_code", "N/A")
                            category = timelines[0].get("category", "N/A")
                            print(f"   - {item.get('name', 'Unknown')}: Status Code={status_code}, Category={category}")
                else:
                    print(f"\n❌ API returned error: {data.get('message', 'Unknown error')}")
                    
            except:
                print(response.text)
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_tracking_api())
