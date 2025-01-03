import requests
import json
from datetime import datetime

def test_api():
    BASE_URL = "http://localhost:8000"
    COOKIE = ""  # Reemplaza con tu cookie

    def log_response(endpoint, response):
        print(f"\n=== Testing {endpoint} ===")
        print(f"Status Code: {response.status_code}")
        try:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except:
            print(f"Response: {response.text}")

    # Test endpoints
    tests = [
        {
            "name": "Generate Song",
            "method": "POST",
            "endpoint": "/generate",
            "data": {
                "prompt": "Una canción de rock en español",
                "cookie": COOKIE,
                "custom": False,
                "tags": "Rock",
                "negative_tags": "pop",
                "instrumental": False,
                "title": None,
                "model": "chirp-v3-5"
            }
        },
        {
            "name": "Get Songs",
            "method": "GET",
            "endpoint": "/songs",
            "params": {"cookie": COOKIE}
        }
    ]

    results = []
    for test in tests:
        try:
            if test["method"] == "GET":
                response = requests.get(f"{BASE_URL}{test['endpoint']}", 
                                     params=test.get("params", {}))
            else:
                response = requests.post(f"{BASE_URL}{test['endpoint']}", 
                                      json=test.get("data", {}))
            
            log_response(test["name"], response)
            results.append({
                "test": test["name"],
                "success": response.status_code == 200,
                "status_code": response.status_code
            })
        except Exception as e:
            print(f"\nError en {test['name']}: {str(e)}")
            results.append({
                "test": test["name"],
                "success": False,
                "error": str(e)
            })

    # Resumen de resultados
    print("\n=== Test Summary ===")
    for result in results:
        status = "✅" if result.get("success") else "❌"
        print(f"{status} {result['test']}")

if __name__ == "__main__":
    test_api() 