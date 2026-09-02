import urllib.request
import json
import time

def test_clear_and_reset():
    print("1. 현재 문서 목록 확인...")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/admin/documents") as res:
        data = json.loads(res.read().decode('utf-8'))
        print(f"-> 초기 문서 수: {data.get('total')}건")

    print("\n2. DELETE /api/admin/documents (전체 삭제 실행)...")
    req = urllib.request.Request("http://127.0.0.1:8000/api/admin/documents")
    req.get_method = lambda: 'DELETE'
    with urllib.request.urlopen(req) as res:
        del_data = json.loads(res.read().decode('utf-8'))
        print(f"-> 전체 삭제 응답: {del_data}")
        assert del_data.get("remaining_docs") == 0

    # Verify count is 0
    with urllib.request.urlopen("http://127.0.0.1:8000/api/admin/documents") as res:
        data = json.loads(res.read().decode('utf-8'))
        print(f"-> 전체 삭제 후 조회 문서 수: {data.get('total')}건")
        assert data.get('total') == 0

    print("\n3. POST /api/admin/reset-default (기본 지식 복원)...")
    reset_req = urllib.request.Request(
        "http://127.0.0.1:8000/api/admin/reset-default",
        data=b"{}",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(reset_req) as res:
        reset_data = json.loads(res.read().decode('utf-8'))
        print(f"-> 기본 복원 응답: {reset_data}")
        assert reset_data.get("total_docs") == 14

    # Verify count is 14
    with urllib.request.urlopen("http://127.0.0.1:8000/api/admin/documents") as res:
        data = json.loads(res.read().decode('utf-8'))
        print(f"-> 기본 복원 후 조회 문서 수: {data.get('total')}건")
        assert data.get('total') == 14

    print("\n🎉 [전체 삭제 및 기본 복원 기능 전체 검증 성공!]")

if __name__ == "__main__":
    test_clear_and_reset()
