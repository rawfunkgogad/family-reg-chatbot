import os
import json
import asyncio
import httpx
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from rag.corpus_data import CORPUS_DOCS

API_KEY = os.environ.get("OPENAI_API_KEY", "sk-dev-Un5B6gafFJxVcRwGnw5AlT23wDGn1ooA")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://open.hasa.re.kr/v1")
EMBEDDING_MODEL = "bge-m3"
RERANK_MODEL = "bge-reranker-v2-m3"
AGENT_MODEL = "qwen3-coder"

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_EMBEDDINGS_PATH = DATA_DIR / "corpus_embeddings.npy"
CACHE_METADATA_PATH = DATA_DIR / "corpus_metadata.json"

class RAGService:
    def __init__(self):
        self.corpus: List[Dict[str, Any]] = list(CORPUS_DOCS)
        self.embeddings: Optional[np.ndarray] = None
        self.headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }

    async def initialize(self):
        """임베딩 캐시 로드 또는 신규 임베딩 생성"""
        if CACHE_EMBEDDINGS_PATH.exists() and CACHE_METADATA_PATH.exists():
            try:
                self.embeddings = np.load(CACHE_EMBEDDINGS_PATH)
                with open(CACHE_METADATA_PATH, "r", encoding="utf-8") as f:
                    self.corpus = json.load(f)
                print(f"[RAG] Loaded cached embeddings for {len(self.corpus)} docs.")
                return
            except Exception as e:
                print(f"[RAG] Failed to load cache, regenerating: {e}")

        await self._generate_and_save_corpus_embeddings()

    async def _embed_single_text_with_retry(self, client: httpx.AsyncClient, text: str, max_retries: int = 4) -> List[float]:
        """429/동시 요청 한도 발생 시 자동 재시도하는 임베딩 헬퍼"""
        for attempt in range(max_retries):
            try:
                res = await client.post(
                    f"{BASE_URL}/embeddings",
                    headers=self.headers,
                    json={
                        "model": EMBEDDING_MODEL,
                        "input": text
                    }
                )
                if res.status_code == 200:
                    return res.json()["data"][0]["embedding"]
                elif res.status_code in [429, 503] or "concurrent_limit" in res.text:
                    wait_time = 1.5 * (attempt + 1)
                    await asyncio.sleep(wait_time)
                else:
                    print(f"[RAG] Embedding error ({res.status_code}): {res.text[:100]}")
                    break
            except Exception as e:
                print(f"[RAG] Embedding exception: {e}")
                await asyncio.sleep(1.0)
        return [0.0] * 1024

    def _build_embedding_text(self, doc: Dict[str, Any]) -> str:
        """단순 텍스트뿐만 아니라 조문, 섹션 헤딩, 이웃 맥락 힌트를 포함한 풍부한 임베딩 텍스트 구성"""
        category = doc.get('category', '')
        title = doc.get('title', '')
        source = doc.get('source', '')
        content = doc.get('content', '')
        
        parts = [f"[{category}] {title}"]
        
        sec = doc.get('section_heading')
        if sec:
            parts.append(f"주제: {sec}")
            
        arts = doc.get('detected_articles')
        if arts and isinstance(arts, list) and len(arts) > 0:
            parts.append(f"관련조문: {', '.join(arts)}")
            
        parts.append(f"출처: {source}")
        
        # 이전/다음 청크 힌트가 있으면 임베딩에 약한 맥락 반영
        prev_hint = doc.get('prev_chunk_preview')
        next_hint = doc.get('next_chunk_preview')
        
        body = content
        if prev_hint:
            body = f"...(이전문맥: {prev_hint})\n{body}"
        if next_hint:
            body = f"{body}\n...(후속문맥: {next_hint})..."
            
        parts.append(body)
        return "\n".join(parts)

    async def _generate_and_save_corpus_embeddings(self):
        """전체 지식 코퍼스에 대해 bge-m3 임베딩 생성 후 로컬 저장"""
        print(f"[RAG] Generating embeddings for {len(self.corpus)} documents using {EMBEDDING_MODEL}...")
        vectors = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for doc in self.corpus:
                text_to_embed = self._build_embedding_text(doc)
                emb = await self._embed_single_text_with_retry(client, text_to_embed)
                vectors.append(emb)

        self.embeddings = np.array(vectors, dtype=np.float32)
        np.save(CACHE_EMBEDDINGS_PATH, self.embeddings)
        with open(CACHE_METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(self.corpus, f, ensure_ascii=False, indent=2)
        print(f"[RAG] Successfully cached {len(vectors)} embeddings.")

    async def add_documents(self, new_docs: List[Dict[str, Any]]) -> int:
        """관리자가 업로드한 신규 문서들을 임베딩하고 기존 인덱스에 병합"""
        if not new_docs:
            return 0

        if self.embeddings is None:
            await self.initialize()

        print(f"[RAG] Adding and embedding {len(new_docs)} new documents...")
        new_vectors = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for doc in new_docs:
                text_to_embed = self._build_embedding_text(doc)
                emb = await self._embed_single_text_with_retry(client, text_to_embed)
                new_vectors.append(emb)

        new_v_array = np.array(new_vectors, dtype=np.float32)

        # Merge corpus and embeddings
        if self.embeddings is None or len(self.embeddings) == 0:
            self.embeddings = new_v_array
            self.corpus = list(new_docs)
        else:
            self.embeddings = np.vstack([self.embeddings, new_v_array])
            self.corpus.extend(new_docs)

        # Save to disk
        np.save(CACHE_EMBEDDINGS_PATH, self.embeddings)
        with open(CACHE_METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(self.corpus, f, ensure_ascii=False, indent=2)

        print(f"[RAG] Total corpus now: {len(self.corpus)} documents.")
        return len(new_docs)

    async def delete_document(self, doc_id: str) -> bool:
        """특정 문서 ID 삭제 및 임베딩 인덱스 갱신"""
        if self.embeddings is None:
            await self.initialize()

        found_idx = -1
        for idx, doc in enumerate(self.corpus):
            if str(doc.get("id")) == str(doc_id):
                found_idx = idx
                break

        if found_idx == -1:
            return False

        # Remove from corpus and embeddings
        self.corpus.pop(found_idx)
        if self.embeddings is not None and len(self.embeddings) > 0:
            self.embeddings = np.delete(self.embeddings, found_idx, axis=0)

        # Save to disk
        np.save(CACHE_EMBEDDINGS_PATH, self.embeddings)
        with open(CACHE_METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(self.corpus, f, ensure_ascii=False, indent=2)

        print(f"[RAG] Deleted document {doc_id}. Remaining: {len(self.corpus)}")
        return True

    async def clear_all_documents(self) -> bool:
        """등록된 모든 RAG 지식 문서 및 임베딩 인덱스 전체 삭제"""
        self.corpus = []
        self.embeddings = None
        
        # Save empty state to disk
        if CACHE_EMBEDDINGS_PATH.exists():
            try:
                CACHE_EMBEDDINGS_PATH.unlink()
            except Exception:
                pass
                
        with open(CACHE_METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

        print("[RAG] Cleared all documents and embeddings.")
        return True

    async def reset_to_default(self) -> int:
        """기본 탑재 코퍼스로 지식 베이스 초기화 및 재임베딩"""
        self.corpus = list(CORPUS_DOCS)
        await self._generate_and_save_corpus_embeddings()
        return len(self.corpus)

    async def reindex_all(self) -> int:
        """전체 코퍼스 재임베딩"""
        if not self.corpus:
            return 0
        await self._generate_and_save_corpus_embeddings()
        return len(self.corpus)

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """전체 등록 문서 목록 반환"""
        return self.corpus

    def get_grouped_files(self) -> List[Dict[str, Any]]:
        """
        코퍼스를 원본 파일/문서 단위로 그룹화하여 반환
        (PDF 파일별, JSON 파일별, 수기 등록별, 기본 코퍼스별)
        """
        groups: Dict[str, Dict[str, Any]] = {}

        for doc in self.corpus:
            doc_id = str(doc.get("id", ""))
            group_key = doc.get("group_id")

            # Infer group key and file metadata if not explicitly tagged
            if not group_key:
                if doc_id.startswith("PDF-"):
                    parts = doc_id.split("-")
                    group_key = f"PDF-{parts[1]}" if len(parts) >= 2 else "PDF-GROUP"
                elif doc_id.startswith("JSON-"):
                    parts = doc_id.split("-")
                    group_key = f"JSON-{parts[1]}" if len(parts) >= 2 else "JSON-GROUP"
                elif doc_id.startswith("EXCEL-"):
                    parts = doc_id.split("-")
                    group_key = f"EXCEL-{parts[1]}" if len(parts) >= 2 else "EXCEL-GROUP"
                elif doc_id.startswith("MANUAL-"):
                    group_key = "MANUAL-GROUP"
                else:
                    group_key = "BUILTIN-CORPUS"

            if group_key not in groups:
                # Infer file name & type
                file_name = doc.get("file_name")
                if not file_name:
                    if group_key == "BUILTIN-CORPUS":
                        file_name = "전자가족관계등록시스템 & 대법원 예규·선례 기본 코퍼스"
                        file_type = "BUILTIN"
                    elif group_key == "MANUAL-GROUP":
                        file_name = "관리자 수기 직접 등록 지식"
                        file_type = "MANUAL"
                    elif group_key.startswith("PDF-"):
                        src = doc.get("source", "")
                        file_name = src.split(" (제")[0] if " (제" in src else (doc.get("title", "PDF 문서").split("]")[0].strip("[") + ".pdf")
                        file_type = "PDF"
                    elif group_key.startswith("JSON-"):
                        file_name = doc.get("source", "JSON 데이터")
                        file_type = "JSON"
                    elif group_key.startswith("EXCEL-"):
                        file_name = doc.get("source", "상하위 법령 엑셀 데이터").split(" (행")[0]
                        file_type = "EXCEL"
                    else:
                        file_name = doc.get("source", "기타 문서")
                        file_type = "DOC"
                else:
                    if file_name.lower().endswith((".xlsx", ".xls")):
                        file_type = "EXCEL"
                    elif file_name.lower().endswith(".pdf"):
                        file_type = "PDF"
                    elif file_name.lower().endswith(".json"):
                        file_type = "JSON"
                    else:
                        file_type = "DOC"

                groups[group_key] = {
                    "file_id": group_key,
                    "file_name": file_name,
                    "file_type": file_type,
                    "category": doc.get("category", "일반실무"),
                    "chunks_count": 0,
                    "total_chars": 0,
                    "created_at": doc.get("created_at", 0),
                    "chunks": []
                }

            content = doc.get("content", "")
            groups[group_key]["chunks_count"] += 1
            groups[group_key]["total_chars"] += len(content)
            
            # Append chunk detail
            groups[group_key]["chunks"].append({
                "id": doc.get("id"),
                "title": doc.get("title", ""),
                "source": doc.get("source", ""),
                "category": doc.get("category", ""),
                "page_number": doc.get("page_number"),
                "chunk_index": doc.get("chunk_index"),
                "hierarchy_data": doc.get("hierarchy_data"),
                "char_length": len(content),
                "preview": content[:120] + ("..." if len(content) > 120 else ""),
                "content": content
            })

        # Return sorted list (newest first, builtin at the end)
        result = list(groups.values())
        result.sort(key=lambda x: (x["file_id"] != "BUILTIN-CORPUS", x["created_at"]), reverse=True)
        return result

    async def delete_file_group(self, group_id: str) -> Dict[str, Any]:
        """특정 파일/문서 그룹에 속한 모든 청크 일괄 삭제"""
        if not self.corpus:
            return {"deleted_count": 0, "remaining_docs": 0}

        target_indices = []
        for idx, doc in enumerate(self.corpus):
            doc_id = str(doc.get("id", ""))
            doc_group = doc.get("group_id")
            
            # Match by group_id or prefix
            is_match = False
            if doc_group and doc_group == group_id:
                is_match = True
            elif group_id == "BUILTIN-CORPUS" and not doc_id.startswith(("PDF-", "JSON-", "EXCEL-", "MANUAL-")):
                is_match = True
            elif group_id == "MANUAL-GROUP" and doc_id.startswith("MANUAL-"):
                is_match = True
            elif group_id.startswith("PDF-") and doc_id.startswith(group_id):
                is_match = True
            elif group_id.startswith("JSON-") and doc_id.startswith(group_id):
                is_match = True
            elif group_id.startswith("EXCEL-") and doc_id.startswith(group_id):
                is_match = True

            if is_match:
                target_indices.append(idx)

        if not target_indices:
            return {"deleted_count": 0, "remaining_docs": len(self.corpus)}

        # Filter corpus
        keep_indices = [i for i in range(len(self.corpus)) if i not in target_indices]
        self.corpus = [self.corpus[i] for i in keep_indices]

        # Filter embeddings
        if self.embeddings is not None and len(self.embeddings) > 0:
            if keep_indices:
                self.embeddings = self.embeddings[keep_indices]
                np.save(CACHE_EMBEDDINGS_PATH, self.embeddings)
            else:
                self.embeddings = None
                if CACHE_EMBEDDINGS_PATH.exists():
                    try:
                        CACHE_EMBEDDINGS_PATH.unlink()
                    except Exception:
                        pass

        # Save metadata
        with open(CACHE_METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(self.corpus, f, ensure_ascii=False, indent=2)

        deleted_count = len(target_indices)
        print(f"[RAG] Deleted file group '{group_id}' ({deleted_count} chunks). Remaining: {len(self.corpus)}")
        return {
            "deleted_count": deleted_count,
            "remaining_docs": len(self.corpus)
        }

    async def get_query_embedding(self, query: str) -> Optional[np.ndarray]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                res = await client.post(
                    f"{BASE_URL}/embeddings",
                    headers=self.headers,
                    json={
                        "model": EMBEDDING_MODEL,
                        "input": query
                    }
                )
                if res.status_code == 200:
                    emb = res.json()["data"][0]["embedding"]
                    return np.array(emb, dtype=np.float32)
            except Exception as e:
                print(f"[RAG] Query embedding failed: {e}")
        return None

    async def dense_search(self, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
        """1단계: bge-m3 코사인 유사도 검색"""
        if self.embeddings is None:
            await self.initialize()

        if not self.corpus or self.embeddings is None or len(self.embeddings) == 0:
            return []

        query_vec = await self.get_query_embedding(query)
        if query_vec is None:
            return self.corpus[:top_k]

        # Cosine similarity
        norm_corpus = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        norm_query = np.linalg.norm(query_vec)
        norm_corpus = np.where(norm_corpus == 0, 1e-10, norm_corpus)
        if norm_query == 0:
            norm_query = 1e-10

        sims = np.dot(self.embeddings, query_vec) / (norm_corpus.flatten() * norm_query)
        actual_k = min(top_k, len(self.corpus))
        top_indices = np.argsort(sims)[::-1][:actual_k]

        results = []
        for idx in top_indices:
            doc_copy = dict(self.corpus[idx])
            doc_copy["dense_similarity"] = float(sims[idx])
            results.append(doc_copy)
        return results

    async def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 4) -> List[Dict[str, Any]]:
        """2단계: bge-reranker-v2-m3 정밀 리랭킹"""
        if not candidates:
            return []

        doc_texts = [
            f"[{c.get('category', '')}] {c.get('title', '')}\n출처: {c.get('source', '')}\n내용: {c.get('content', '')}"
            for c in candidates
        ]

        rerank_url = "https://open.hasa.re.kr/rerank"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                res = await client.post(
                    rerank_url,
                    headers=self.headers,
                    json={
                        "model": RERANK_MODEL,
                        "query": query,
                        "documents": doc_texts
                    }
                )
                if res.status_code == 200:
                    rerank_data = res.json()
                    scored_results = rerank_data.get("results", [])
                    
                    reranked_docs = []
                    for item in scored_results:
                        idx = item["index"]
                        score = item["relevance_score"]
                        matched_doc = dict(candidates[idx])
                        matched_doc["rerank_score"] = float(score)
                        reranked_docs.append(matched_doc)
                    
                    reranked_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
                    return reranked_docs[:top_k]
                else:
                    print(f"[RAG] Rerank API returned status {res.status_code}: {res.text}")
            except Exception as e:
                print(f"[RAG] Rerank exception: {e}")

    def _find_sibling_chunk(self, group_id: str, chunk_index: int) -> Optional[Dict[str, Any]]:
        """동일 문서 그룹 내의 인접(이전/다음) 청크 탐색"""
        if not group_id or chunk_index < 1:
            return None
        for doc in self.corpus:
            if doc.get("group_id") == group_id and doc.get("chunk_index") == chunk_index:
                return doc
        return None

    async def retrieve(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """2단계 통합 검색 (임베딩 검색 -> 리랭킹) 및 이웃 맥락 자동 확장(Parent-Child Context Extension)"""
        dense_candidates = await self.dense_search(query, top_k=8)
        reranked_docs = await self.rerank(query, dense_candidates, top_k=top_k)

        # 각 검색 결과에 대해 동일 문서 내 이웃 맥락(전후 문맥) 자동 결합
        for doc in reranked_docs:
            group_id = doc.get("group_id")
            chunk_idx = doc.get("chunk_index")

            if group_id and isinstance(chunk_idx, int) and chunk_idx >= 1:
                prev_chunk = self._find_sibling_chunk(group_id, chunk_idx - 1)
                next_chunk = self._find_sibling_chunk(group_id, chunk_idx + 1)

                expanded_parts = []
                if prev_chunk:
                    prev_text = prev_chunk.get("content", "").strip()
                    if prev_text:
                        expanded_parts.append(f"[이전 연결 문맥]\n... {prev_text[-160:]}")

                expanded_parts.append(f"[핵심 발췌 본문]\n{doc.get('content', '')}")

                if next_chunk:
                    next_text = next_chunk.get("content", "").strip()
                    if next_text:
                        expanded_parts.append(f"[후속 연결 문맥]\n{next_text[:160]} ...")

                doc["expanded_content"] = "\n\n".join(expanded_parts)
            else:
                doc["expanded_content"] = doc.get("content", "")

        return reranked_docs

    async def execute_web_agent(self, query: str, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """/v1/agent/chat 웹 검색 에이전트 실행"""
        messages = []
        if history:
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
        else:
            messages.append({"role": "user", "content": query})

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                res = await client.post(
                    f"{BASE_URL}/agent/chat",
                    headers=self.headers,
                    json={
                        "model": AGENT_MODEL,
                        "messages": messages
                    }
                )
                if res.status_code == 200:
                    return res.json()
                else:
                    return {
                        "answer": f"웹 에이전트 호출 중 오류가 발생했습니다. (상태 코드: {res.status_code})",
                        "steps": [],
                        "sources": []
                    }
            except Exception as e:
                return {
                    "answer": f"웹 에이전트 실행 실패: {str(e)}",
                    "steps": [],
                    "sources": []
                }

rag_service = RAGService()
