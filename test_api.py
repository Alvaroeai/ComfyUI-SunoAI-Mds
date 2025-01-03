import requests
import json
from datetime import datetime

def test_api():
    BASE_URL = "http://localhost:8080"
    COOKIE = "_ga=GA1.1.2058410476.1732358938; ajs_anonymous_id=c9601089-a794-45e6-91cb-63983506feac; __stripe_mid=77e2ac00-3afa-416a-b3af-23041d67d1cd19aa18; _fbp=fb.1.1733336992502.55089847583659325; __client=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6ImNsaWVudF8ycEZQZERsUXVLN2MzRklFYVVSclByVld1TGYiLCJyb3RhdGluZ190b2tlbiI6InFsdTI5djRlZGltbTJncDU1YmFyajNmNzcwdHk3b294NjFvODB2ZTcifQ.Siok6459lJyQhb6Yn1vAcVwCRJVAXotxUHEvjm5TaXQ4xdkERd2FVxsfyXbJVfZyYryy0s1BAOyNwf-wtSCrqvoYxXkkGMu1-qWM80-srg8506A4CflNbnVnDxxTKm1puIvxOpkngZ6QwgGgI_TgP2MVpufZZKoxPQqTQi8AcW-fCbCE9-PCQ43G06KM3_1v4bIC6pF_xfT_7Hta3ww7ykVE5QVjGINpB4sCXN8WMuC3g8ziGy5-4vgDYn6NakWNnwWYBu09UEOpfN1MznK1rG3NCaDPCOFKBwAt1ntiiszdhuIv9uxB7_2db0NTmbb5JGaU0xk-kFC-8cTk_TSxJQ; __client_uat=1733495575; __client_uat_U9tcbTPE=1733495575; _gcl_au=1.1.613200802.1733661021; _tt_enable_cookie=1; _ttp=9PypPgSW-lx0_XPHKs6VujjHYXL.tt.1; mp_26ced217328f4737497bd6ba6641ca1c_mixpanel=%7B%22distinct_id%22%3A%20%22d6325d7e-704b-4f7c-bcb7-2d995802f0e2%22%2C%22%24device_id%22%3A%20%2219358a39d2d3ff-07669e9dea6c51-26011851-384000-19358a39d2d3ff%22%2C%22%24initial_referrer%22%3A%20%22%24direct%22%2C%22%24initial_referring_domain%22%3A%20%22%24direct%22%2C%22__mps%22%3A%20%7B%7D%2C%22__mpso%22%3A%20%7B%7D%2C%22__mpus%22%3A%20%7B%7D%2C%22__mpa%22%3A%20%7B%7D%2C%22__mpu%22%3A%20%7B%7D%2C%22__mpr%22%3A%20%5B%5D%2C%22__mpap%22%3A%20%5B%5D%2C%22%24user_id%22%3A%20%22d6325d7e-704b-4f7c-bcb7-2d995802f0e2%22%2C%22%24search_engine%22%3A%20%22google%22%7D; _cfuvid=3.3M3ZnlVdMWyQ_0G2toBL2aKwP06Y1fDK1ea4jbHSc-1735902446882-0.0.1.1-604800000; __cf_bm=KBhuyhXZT7SA1b5Hae6NrWqMKrwzEFFDR6EZ3XVzPhI-1735922118-1.0.1.1-s2yc58nf7f5JfWv8hGuiuAF9bdBzQJv8qN4r3Ak9yvwBzQq1mfAoq1uRVjaF1g4KGRLd58rg_nL1v8WjXUBk7w; _ga_7B0KEDD7XP=GS1.1.1735921214.50.1.1735922647.0.0.0"  # Reemplaza con tu cookie

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