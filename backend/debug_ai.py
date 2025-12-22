import requests
import json

url = "http://127.0.0.1:8000/ai/message"

# Payload 1: Simple Text
payload_text = {
    "message_id": "debug-1",
    "thread_id": "debug-thread",
    "app_name": "sania",
    "client_external_id": "sania",
    "text": "Hello, debug test"
}

# Payload 2: Text + Fake Image
payload_image = {
    "message_id": "debug-2",
    "thread_id": "debug-thread",
    "app_name": "sania",
    "client_external_id": "sania",
    "text": "Check this image",
    "attachments": [{"url": "https://via.placeholder.com/150", "type": "image"}]
}

def test(name, p):
    print(f"--- Testing {name} ---")
    try:
        r = requests.post(url, json=p)
        print(f"Status: {r.status_code}")
        try:
            print(f"Response: {r.json()}")
        except:
            print(f"Raw Response: {r.text}")
    except Exception as e:
        print(f"Request failed: {e}")

test("Text Only", payload_text)
test("Text + Image", payload_image)
