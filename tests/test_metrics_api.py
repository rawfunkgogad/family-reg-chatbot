import urllib.request
import json

def test_metrics_api():
    print("Testing GET /api/metrics/stats ...")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/metrics/stats") as res:
        data = json.loads(res.read().decode('utf-8'))
        print("-> Metrics data:", json.dumps(data, ensure_ascii=False, indent=2))
        assert "cache" in data
        assert "metrics" in data

    print("\nTesting POST /api/cache/clear ...")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/cache/clear",
        data=b"{}",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        del_data = json.loads(res.read().decode('utf-8'))
        print("-> Cache clear response:", del_data)
        assert del_data.get("success") is True

    print("\nAll Metrics API tests passed successfully!")

if __name__ == "__main__":
    test_metrics_api()
