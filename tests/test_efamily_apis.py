import urllib.request
import json

def test_efamily_apis():
    print("Testing GET /api/efamily/services ...")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/efamily/services") as res:
        services = json.loads(res.read().decode('utf-8'))
        print(f"-> Services count: {len(services)}")
        assert len(services) == 6

    print("Testing GET /api/efamily/quick-faq ...")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/efamily/quick-faq") as res:
        faqs = json.loads(res.read().decode('utf-8'))
        print(f"-> Civil FAQs count: {len(faqs)}")
        assert len(faqs) == 6

    print("All e-Family APIs OK!")

if __name__ == "__main__":
    test_efamily_apis()
