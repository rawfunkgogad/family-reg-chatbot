"""
전자가족관계등록시스템 고객센터 지식(161건)을 마스터 코퍼스 및 RAG 벡터 인덱스에 병합/임베딩
"""
import sys
import json
import asyncio
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from rag.rag_service import rag_service
from sync.corpus_sync_manager import corpus_sync_manager

async def ingest_efamily_knowledge():
    print("=== [Ingesting eFamily Customer Center Knowledge into RAG] ===")
    
    # 1. Load eFamily crawled documents
    efamily_file = backend_dir / "data" / "efamily_customer_center.json"
    if not efamily_file.exists():
        print(f"Error: {efamily_file} not found. Running crawler first...")
        from crawler.efamily_guide_crawler import run_efamily_crawler
        run_efamily_crawler()

    with open(efamily_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    norm_docs = corpus_sync_manager.normalize_efamily_customer_center(raw_data)
    print(f"[Ingest] Loaded {len(norm_docs)} normalized eFamily documents.")

    # 2. Initialize RAG service
    await rag_service.initialize()
    existing_ids = {str(d.get("id")) for d in rag_service.corpus}
    print(f"[Ingest] Current RAG corpus size: {len(rag_service.corpus)}")

    # 3. Check for updated documents (e.g. newly extracted attachment text)
    form_docs = [d for d in norm_docs if d.get("category") == "가족관계등록 신청서식"]
    updated_forms = []
    
    corpus_map = {str(d.get("id")): idx for idx, d in enumerate(rag_service.corpus)}
    
    for f_doc in form_docs:
        fid = str(f_doc.get("id"))
        if fid in corpus_map:
            idx = corpus_map[fid]
            if len(f_doc.get("content", "")) > len(rag_service.corpus[idx].get("content", "")):
                rag_service.corpus[idx] = f_doc
                updated_forms.append((idx, f_doc))

    if updated_forms:
        print(f"[Ingest] Re-embedding {len(updated_forms)} forms with newly extracted attachment text...")
        import httpx
        import numpy as np
        from rag.rag_service import CACHE_EMBEDDINGS_PATH, CACHE_METADATA_PATH
        async with httpx.AsyncClient(timeout=30.0) as client:
            for idx, doc in updated_forms:
                text_to_embed = rag_service._build_embedding_text(doc)
                emb = await rag_service._embed_single_text_with_retry(client, text_to_embed)
                rag_service.embeddings[idx] = np.array(emb, dtype=np.float32)
                
        np.save(CACHE_EMBEDDINGS_PATH, rag_service.embeddings)
        with open(CACHE_METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(rag_service.corpus, f, ensure_ascii=False, indent=2)
        print(f"[Ingest] Re-embedding completed and saved for {len(updated_forms)} forms.")

    # 4. Find completely new documents to add
    new_docs = [d for d in norm_docs if str(d.get("id")) not in existing_ids]
    if new_docs:
        print(f"[Ingest] Generating bge-m3 embeddings for {len(new_docs)} new docs...")
        added_count = await rag_service.add_documents(new_docs)
        print(f"[Ingest] Successfully added {added_count} documents to RAG index.")

    # 4. Update master_family_reg_knowledge_corpus.json
    print("[Ingest] Updating master knowledge corpus file...")
    master_corpus = corpus_sync_manager.build_integrated_corpus()
    with open(corpus_sync_manager.master_corpus_file, "w", encoding="utf-8") as f:
        json.dump(master_corpus, f, ensure_ascii=False, indent=2)
    print(f"[Ingest] Master corpus updated at {corpus_sync_manager.master_corpus_file} (Total: {len(master_corpus)} docs)")

    print(f"\n[SUCCESS] Total RAG corpus size now: {len(rag_service.corpus)} documents with verified embeddings.")

if __name__ == "__main__":
    asyncio.run(ingest_efamily_knowledge())
