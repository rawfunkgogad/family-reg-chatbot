import os
import json
import time
import asyncio
import httpx
from typing import AsyncGenerator, List, Dict, Any
from prompts.system_prompt import get_system_prompt
from rag.rag_service import rag_service
from optimization.cache_manager import cache_manager
from optimization.metrics_collector import metrics_collector

# Global Semaphore for Concurrent Request Limit (1) & Queue Tracker
llm_semaphore = asyncio.Semaphore(1)
waiting_queue_count = 0

BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://open.hasa.re.kr/v1")
API_KEY = os.environ.get("OPENAI_API_KEY", "sk-dev-Un5B6gafFJxVcRwGnw5AlT23wDGn1ooA")
DEFAULT_MODEL = "llama-3.3-70b"

def estimate_tokens(text: str) -> int:
    """한글/영문 토큰 수 근사치 계산 (한글 ~1.5자당 1토큰)"""
    return max(1, int(len(text) / 2.0))

async def stream_chat_completion(
    messages: List[Dict[str, str]], 
    temperature: float = 0.5, 
    max_tokens: int = 1200,
    use_rag: bool = True,
    mode: str = "unified",
    model: str = DEFAULT_MODEL,
    bypass_cache: bool = False
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    llama-3.3-70b 기본 채택, 인메모리 질의 캐시, 실시간 메트릭 지원 SSE 스트리밍
    """
    start_time = time.time()
    
    # 1. Extract latest user message
    last_user_query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_query = msg.get("content", "")
            break

    # 2. Check Query Cache (Instant return if hit and not bypassed)
    if use_rag and last_user_query and not bypass_cache:
        cached_result = cache_manager.get(last_user_query, mode, model)
        if cached_result:
            cached_content, cached_sources, cached_tokens = cached_result
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Notify frontend that this response is from high-speed cache
            yield {
                "type": "cache_status",
                "data": {
                    "is_cached": True,
                    "cached_tokens": cached_tokens,
                    "message": "⚡ 검증된 고속 캐시에서 0초 만에 즉시 반환된 답변입니다."
                }
            }
            
            if cached_sources:
                yield {"type": "sources", "data": cached_sources}
            
            yield {"type": "delta", "data": cached_content}
            
            # Record and yield cache metrics
            metrics_collector.record_request(
                model=model,
                mode=mode,
                latency_ms=latency_ms,
                prompt_tokens=estimate_tokens(last_user_query),
                completion_tokens=cached_tokens,
                cached=True
            )
            yield {
                "type": "metrics",
                "data": {
                    "latency_ms": latency_ms,
                    "prompt_tokens": estimate_tokens(last_user_query),
                    "completion_tokens": cached_tokens,
                    "total_tokens": estimate_tokens(last_user_query) + cached_tokens,
                    "model": model,
                    "cached": True
                }
            }
            return

    # If live generation (cache miss or bypass requested)
    yield {
        "type": "cache_status",
        "data": {
            "is_cached": False,
            "bypassed": bypass_cache
        }
    }

    # 3. Sliding Window: Limit history to last 6 turns
    windowed_history = messages[-6:] if len(messages) > 6 else messages

    # 4. RAG Retrieval (Top-5 rich context)
    system_prompt = get_system_prompt(counseling_mode=mode, user_query=last_user_query)
    retrieved_sources_for_client = []
    
    if use_rag and last_user_query:
        try:
            retrieved_docs = await rag_service.retrieve(last_user_query, top_k=5)
            if retrieved_docs:
                retrieved_sources_for_client = [
                    {
                        "id": d.get("id"),
                        "category": d.get("category"),
                        "source": d.get("source"),
                        "title": d.get("title"),
                        "content": d.get("content"),
                        "rerank_score": round(d.get("rerank_score", 0.0), 4),
                        "dense_similarity": round(d.get("dense_similarity", 0.0), 4),
                    }
                    for d in retrieved_docs
                ]
                yield {"type": "sources", "data": retrieved_sources_for_client}
                
                # Append structured RAG context to system prompt as internal background knowledge
                rag_context_str = "\n\n---\n[시스템 내부 참고 지식 (답변 작성 시 정확한 사실 근거로만 활용하고, 이 제목 태그는 최종 답변에 출력하지 마십시오)]:\n"
                for i, doc in enumerate(retrieved_docs, 1):
                    cat = doc.get("category", "일반")
                    src = doc.get("source", "법원 실무자료")
                    title = doc.get("title", "")
                    content = doc.get("content", "")
                    hierarchy = doc.get("hierarchy_data")
                    
                    hier_info = ""
                    if hierarchy:
                        hier_info = f" [법령위계: {hierarchy.get('statute_level')} / {hierarchy.get('article_number')}]"
                    
                    rag_context_str += f"참조근거 {i}. [{cat}] {title} ({src}){hier_info}\n{content}\n\n"
                
                system_prompt += rag_context_str
        except Exception as e:
            print(f"[RAG] Retrieval error: {e}")

    # 5. Build Final API Payload
    formatted_messages = [{"role": "system", "content": system_prompt}]
    for msg in windowed_history:
        if msg.get("role") in ["user", "assistant"]:
            formatted_messages.append({"role": msg["role"], "content": msg["content"]})
            
    # Max tokens (default 2500 for rich, well-structured output)
    adjusted_max_tokens = max_tokens if max_tokens and max_tokens >= 1500 else 2500
    
    payload = {
        "model": model,
        "messages": formatted_messages,
        "temperature": temperature,
        "max_tokens": adjusted_max_tokens,
        "stream": True
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    accumulated_response = ""
    prompt_tokens_est = sum(estimate_tokens(m["content"]) for m in formatted_messages)

    global waiting_queue_count
    is_queued = False
    
    # Check if semaphore is currently busy
    if llm_semaphore.locked():
        is_queued = True
        waiting_queue_count += 1
        pos = waiting_queue_count
        est_sec = pos * 3
        yield {
            "type": "queue_status",
            "data": {
                "waiting": True,
                "position": pos,
                "estimated_sec": est_sec,
                "message": f"⏳ 앞선 민원 상담을 처리 중입니다. 잠시만 기다려 주세요 (대기 순번: {pos}번, 예상: 약 {est_sec}초)..."
            }
        }

    try:
        async with llm_semaphore:
            if is_queued:
                waiting_queue_count = max(0, waiting_queue_count - 1)
                yield {
                    "type": "queue_status",
                    "data": {
                        "waiting": False,
                        "position": 0,
                        "message": "✨ 차례가 되었습니다. 답변 생성을 시작합니다."
                    }
                }

            async with httpx.AsyncClient(timeout=60.0) as client:
                # Retry loop for 429 concurrent limit
                max_retries = 3
                for attempt in range(max_retries + 1):
                    try:
                        async with client.stream("POST", f"{BASE_URL}/chat/completions", headers=headers, json=payload) as response:
                            if response.status_code == 429 and attempt < max_retries:
                                await asyncio.sleep(1.5 * (attempt + 1))
                                continue
                            if response.status_code != 200:
                                err_body = await response.aread()
                                yield {"type": "error", "data": f"API 오류 ({response.status_code}): {err_body.decode('utf-8')}"}
                                return

                            async for line in response.aiter_lines():
                                trimmed = line.strip()
                                if not trimmed:
                                    continue
                                if trimmed.startswith("data:"):
                                    data_str = trimmed[5:].strip()
                                    if data_str == "[DONE]":
                                        break
                                    try:
                                        chunk_json = json.loads(data_str)
                                        choices = chunk_json.get("choices", [])
                                        if choices:
                                            delta = choices[0].get("delta", {})
                                            content = delta.get("content")
                                            if content:
                                                accumulated_response += content
                                                yield {"type": "delta", "data": content}
                                    except Exception:
                                        pass
                            return
                    except Exception as e:
                        if attempt == max_retries:
                            yield {"type": "error", "data": f"\n\n[통신 오류]: {str(e)}"}
                            return
                        await asyncio.sleep(1.5 * (attempt + 1))
    finally:
        if is_queued and waiting_queue_count > 0:
            pass

    # 6. Post-processing: Latency, Tokens, Metrics & Cache Storage
    latency_ms = int((time.time() - start_time) * 1000)
    completion_tokens_est = estimate_tokens(accumulated_response)
    total_tokens_est = prompt_tokens_est + completion_tokens_est

    # Cache the result if valid response
    if accumulated_response and last_user_query:
        cache_manager.set(
            query=last_user_query,
            mode=mode,
            model=model,
            content=accumulated_response,
            sources=retrieved_sources_for_client,
            tokens=completion_tokens_est
        )

    # Record metrics
    metrics_collector.record_request(
        model=model,
        mode=mode,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens_est,
        completion_tokens=completion_tokens_est,
        cached=False
    )

    # Yield performance metrics to client
    yield {
        "type": "metrics",
        "data": {
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens_est,
            "completion_tokens": completion_tokens_est,
            "total_tokens": total_tokens_est,
            "model": model,
            "cached": False
        }
    }
