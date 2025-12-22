import requests
try:
    r = requests.get("http://localhost:8000/health/")
    print(f"Health: {r.status_code}")
    print(r.text)
except Exception as e:
    print(e)
