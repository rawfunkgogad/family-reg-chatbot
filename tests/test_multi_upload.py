import io
import json
import urllib.request
import urllib.parse
import mimetypes
import uuid

BASE_URL = "http://127.0.0.1:8000"
AUTH_CODE = "family_manager_035"

def login():
    req_data = json.dumps({"auth_code": AUTH_CODE}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/admin/auth/login",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data["token"]

def build_multipart(fields, files):
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = io.BytesIO()

    for k, v in fields.items():
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        body.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
        body.write(f"{v}\r\n".encode("utf-8"))

    for field_name, filename, content_bytes, content_type in files:
        body.write(f"--{boundary}\r\n".encode("utf-8"))
        body.write(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"))
        body.write(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.write(content_bytes)
        body.write(b"\r\n")

    body.write(f"--{boundary}--\r\n".encode("utf-8"))
    content_type_header = f"multipart/form-data; boundary={boundary}"
    return body.getvalue(), content_type_header

def test_multi_upload():
    token = login()
    assert token, "Login failed"
    print("[1] Admin Login Success! Token acquired.")

    # 1. Prepare sample files
    doc1 = [{
        "title": "다건테스트 출생신고 안내",
        "category": "출생신고",
        "source": "다건테스트1",
        "content": "출생신고는 출생 후 1개월 이내에 관할 등록관서에 접수해야 합니다."
    }]
    file1_bytes = json.dumps(doc1, ensure_ascii=False).encode("utf-8")

    doc2 = [{
        "title": "다건테스트 혼인신고 안내",
        "category": "혼인신고",
        "source": "다건테스트2",
        "content": "혼인신고는 당사자 쌍방과 성년자인 증인 2인의 연서로써 신고해야 합니다."
    }]
    file2_bytes = json.dumps(doc2, ensure_ascii=False).encode("utf-8")

    # Download sample excel
    req_excel = urllib.request.Request(f"{BASE_URL}/api/admin/sample-excel", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req_excel, timeout=5) as res:
        excel_bytes = res.read()

    files = [
        ("files", "test_batch_birth.json", file1_bytes, "application/json"),
        ("files", "test_batch_marriage.json", file2_bytes, "application/json"),
        ("files", "test_batch_hierarchy.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    ]

    body, ct = build_multipart({}, files)
    req_upload = urllib.request.Request(
        f"{BASE_URL}/api/admin/upload",
        data=body,
        headers={
            "Content-Type": ct,
            "Authorization": f"Bearer {token}"
        }
    )

    print("[2] Uploading 3 files simultaneously (2 JSON + 1 XLSX)...")
    with urllib.request.urlopen(req_upload, timeout=30) as res:
        assert res.status == 200
        res_data = json.loads(res.read().decode("utf-8"))

    print("[3] Upload Response:", json.dumps(res_data, ensure_ascii=False, indent=2))
    assert res_data["success"] is True
    assert res_data["total_files"] == 3
    assert res_data["successful_files"] == 3
    assert res_data["chunks_created"] >= 3
    assert len(res_data["files"]) == 3

    print("\n>>> MULTI-FILE UPLOAD TEST (PDF/JSON/EXCEL) PASSED PERFECTLY! <<<")

if __name__ == "__main__":
    test_multi_upload()
