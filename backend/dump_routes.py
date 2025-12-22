import requests
import json
try:
    r = requests.get("http://127.0.0.1:8000/debug-routes")
    print(json.dumps(r.json(), indent=2))
except Exception as e:
    print(e)
