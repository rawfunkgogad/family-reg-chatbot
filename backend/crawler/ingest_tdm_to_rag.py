import json
import asyncio
import sys
import argparse
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from rag.rag_service import RAGService

async def main():
    parser = argparse.ArgumentParser(description="TDM 지식 코퍼스 RAG 인덱싱 연동 스크립트")
    parser.add_argument(
        "--corpus",
        type=str,
        default="directives",
        choices=["directives", "portal", "all"],
        help="인덱싱 대상 코퍼스 ('directives': 대법원 예규/선례 278건, 'portal': 전자가족관계/생활법령 190건, 'all': 전체 통합)"
    )
    args = parser.parse_args()

    files_to_load = []
    if args.corpus in ["directives", "all"]:
        files_to_load.append(BACKEND_DIR / "data" / "corpus" / "scourt_family_directives_precedents.json")
    if args.corpus in ["portal", "all"]:
        files_to_load.append(BACKEND_DIR / "data" / "corpus" / "integrated_family_reg_tdm_corpus.json")

    all_docs = []
    for cf in files_to_load:
        if cf.exists():
            with open(cf, "r", encoding="utf-8") as f:
                docs = json.load(f)
                all_docs.extend(docs)
                print(f"[Ingest] Loaded {len(docs)} documents from {cf.name}")
        else:
            print(f"[Ingest Warning] File not found: {cf.name}")

    if not all_docs:
        print("No documents loaded.")
        return

    service = RAGService()
    await service.initialize()
    print(f"Current active corpus size: {len(service.corpus)} documents")

    print(f"Ingesting {len(all_docs)} documents into RAG system (bge-m3 embedding generation)...")
    result = await service.add_documents(all_docs)
    print(f"Successfully ingested {result} new chunks! New total corpus size: {len(service.corpus)} documents")

if __name__ == "__main__":
    asyncio.run(main())
