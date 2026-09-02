import io
import sys
from pathlib import Path
from pypdf import PdfWriter

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from rag.document_parser import parse_pdf, chunk_text

def test_pdf_parsing():
    print("Testing PDF chunking logic...")
    sample_text = """
    【대법원 가족관계등록예규 제600호】
    등록기준지 변경절차에 관한 실무지침.
    제1조(목적) 본 지침은 사건본인이 등록기준지를 변경하고자 할 때의 심사 기준을 정함을 목적으로 한다.
    제2조(신고서류 심사) 시·구·읍·면의 장은 등록기준지 변경신고서 접수 시 사건본인의 신분증명서 및 가족관계증명서를 대조하여 일치 여부를 확인하여야 한다.
    제3조(전산 처리) 전자가족관계등록시스템에 등록기준지 변경사항을 입력하고 즉시 종전 관서에 변동사항을 전송 통보하여야 한다.
    """
    chunks = chunk_text(sample_text, chunk_size=150, overlap=30)
    print(f"-> Generated {len(chunks)} chunks from text:")
    for i, c in enumerate(chunks, 1):
        print(f"   [{i}] {c[:50]}...")

    assert len(chunks) > 0
    print("PDF Text Chunking Test Passed!")

if __name__ == "__main__":
    test_pdf_parsing()
