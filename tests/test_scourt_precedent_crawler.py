import json
from pathlib import Path
import openpyxl

BASE_DIR = Path(__file__).resolve().parent.parent
EXCEL_PATH = Path(r"C:\Users\rawfu\OneDrive\Desktop\Family_DSLM\예규 및 선례 목록.xlsx")
CORPUS_PATH = BASE_DIR / "backend" / "data" / "corpus" / "scourt_family_directives_precedents.json"

def test_excel_file_exists():
    assert EXCEL_PATH.exists(), f"엑셀 파일이 존재하지 않습니다: {EXCEL_PATH}"
    wb = openpyxl.load_workbook(str(EXCEL_PATH), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert len(rows) >= 278, f"예상 행 수(278건) 미만: {len(rows)}"

def test_corpus_file_and_schema():
    assert CORPUS_PATH.exists(), f"코퍼스 파일이 생성되지 않았습니다: {CORPUS_PATH}"
    assert CORPUS_PATH.stat().st_size > 1024, "코퍼스 파일 용량이 너무 작습니다."

    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        corpus = json.load(f)

    assert isinstance(corpus, list), "코퍼스는 JSON 리스트여야 합니다."
    assert len(corpus) > 0, "코퍼스가 비어 있습니다."

    ids = set()
    for idx, doc in enumerate(corpus):
        # 1. 필수 필드 검증
        for key in ["id", "title", "category", "source", "content", "metadata"]:
            assert key in doc, f"[{idx}] 필수 필드 '{key}' 누락"
            assert doc[key], f"[{idx}] 필드 '{key}'의 값이 비어 있음"

        # 2. ID 포맷 및 중복 검증
        doc_id = doc["id"]
        assert doc_id.startswith("SCOURT-DIR-") or doc_id.startswith("SCOURT-PREC-"), f"잘못된 ID 접두사: {doc_id}"
        assert doc_id not in ids, f"중복된 문서 ID 발견: {doc_id}"
        ids.add(doc_id)

        # 3. 카테고리 검증
        assert doc["category"] in ["가족관계등록예규", "가족관계등록선례"], f"잘못된 카테고리: {doc['category']}"

        # 4. 본문 길이 검증
        assert len(doc["content"]) >= 30, f"[{doc_id}] 본문 길이가 너무 짧음: {len(doc['content'])}"

        # 5. 메타데이터 무결성
        meta = doc["metadata"]
        assert "item_type" in meta
        assert "data_no" in meta
        assert "jis_srno" in meta

    print(f"\n[Test] Verified {len(corpus)} directives and precedents with 100% schema compliance!")

if __name__ == "__main__":
    test_excel_file_exists()
    test_corpus_file_and_schema()
