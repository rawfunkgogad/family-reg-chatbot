import urllib.request
import json

def test_admin_api_endpoints():
    print("Testing GET /api/admin/documents ...")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/admin/documents") as res:
        data = json.loads(res.read().decode('utf-8'))
        print(f"-> Total documents returned: {data.get('total')}")
        assert data.get("total", 0) > 0

    print("Testing POST /api/admin/document (Manual direct insert) ...")
    req_body = {
        "category": "출생신고",
        "title": "테스트 법령 지식 등록",
        "source": "실무테스트 1호",
        "content": "본 지식은 관리자 실무 등록 기능 검증용 데이터입니다."
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/admin/document",
        data=json.dumps(req_body).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as res:
        res_data = json.loads(res.read().decode('utf-8'))
        doc_id = res_data.get("document", {}).get("id")
        print(f"-> Inserted Doc ID: {doc_id}, Total docs now: {res_data.get('total_corpus_docs')}")
        assert doc_id is not None

    print(f"Testing DELETE /api/admin/document/{doc_id} ...")
    del_req = urllib.request.Request(
        f"http://127.0.0.1:8000/api/admin/document/{doc_id}",
        headers={"Content-Type": "application/json"}
    )
    del_req.get_method = lambda: 'DELETE'
    with urllib.request.urlopen(del_req) as res:
        del_data = json.loads(res.read().decode('utf-8'))
        print(f"-> Delete result: {del_data}")
        assert del_data.get("success") is True

    print("\n All Admin Document Management API endpoints verified successfully!")

if __name__ == "__main__":
    test_admin_api_endpoints()
