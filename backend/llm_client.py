import os
import json
import time
import asyncio
import httpx
from typing import AsyncGenerator, List, Dict, Any
from prompts.system_prompt import get_system_prompt
from rag.rag_service import rag_service
from rag.rig_engine import rig_engine, fact_checker, form_matcher
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
    use_rig: bool = True,
    mode: str = "unified",
    model: str = DEFAULT_MODEL,
    bypass_cache: bool = False
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    llama-3.3-70b 채택, RIG(국가법령정보센터 실시간 대조) 및 RLHF 모범 정답 연동 SSE 스트리밍
    """
    start_time = time.time()
    
    # 1. Extract latest user message & detect multi-turn context
    last_user_query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_query = msg.get("content", "")
            break

    user_turns = [m.get("content", "") for m in messages if m.get("role") == "user" and m.get("content")]
    is_multiturn = len(user_turns) > 1 or any(m.get("role") == "assistant" for m in messages)

    # In multi-turn dialogue, bypass single-query cache so the conversation can evolve dynamically
    if is_multiturn:
        bypass_cache = True

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

            # CoVe & Actionable Forms for cached response
            cached_audit = fact_checker.audit_response(cached_content, [], cached_sources or [], is_cached=True)
            yield {"type": "cove_audit", "data": cached_audit}

            matched_forms = form_matcher.match(last_user_query + " " + cached_content)
            if matched_forms:
                yield {"type": "action_forms", "data": matched_forms}
            
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

    # 3. Sliding Window: Limit history to last 10 turns
    windowed_history = messages[-10:] if len(messages) > 10 else messages

    # Synthesize contextual RAG search query if in multi-turn conversation
    rag_search_query = last_user_query
    if is_multiturn and len(user_turns) >= 2:
        prev_user_query = user_turns[-2]
        followup_cues = [
            "그럼", "그러면", "이때", "이 경우", "그렇다면", "또한", "그리고", "해당", "그", "이",
            "예외", "서류", "비용", "수수료", "어디", "언제", "누가", "어떻게", "대리인", "위임장",
            "가능", "안돼", "직접", "방문", "온라인", "발급", "신고", "과태료", "기간", "절차", "방법", "본인", "관할"
        ]
        if len(last_user_query) <= 50 or any(cue in last_user_query for cue in followup_cues):
            rag_search_query = f"{last_user_query} ({prev_user_query})"

    # 4. RAG Retrieval (Top-5 rich context)
    system_prompt = get_system_prompt(counseling_mode=mode, user_query=rag_search_query)
    retrieved_sources_for_client = []
    retrieved_docs = []
    
    if use_rag and rag_search_query:
        try:
            retrieved_docs = await rag_service.retrieve(rag_search_query, top_k=5)
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
                        "is_rlhf": d.get("is_rlhf", False)
                    }
                    for d in retrieved_docs
                ]
                yield {"type": "sources", "data": retrieved_sources_for_client}
                
                # Append structured RAG context to system prompt as internal background knowledge
                rag_context_str = "\n\n---\n[시스템 내부 참고 지식 (답변 작성 시 정확한 사실 근거로만 활용하고, 이 제목 태그는 최종 답변에 출력하지 마십시오)]:\n"
                has_rlhf_in_context = False
                for i, doc in enumerate(retrieved_docs, 1):
                    cat = doc.get("category", "일반")
                    src = doc.get("source", "법원 실무자료")
                    title = doc.get("title", "")
                    content = doc.get("expanded_content") or doc.get("content", "")
                    hierarchy = doc.get("hierarchy_data")
                    is_rlhf = doc.get("is_rlhf") or cat == "RLHF모범정답"
                    if is_rlhf:
                        has_rlhf_in_context = True
                    
                    hier_info = ""
                    if hierarchy:
                        hier_info = f" [법령위계: {hierarchy.get('statute_level')} / {hierarchy.get('article_number')}]"
                    
                    prefix_tag = "⭐ [심사관 공인 모범 정답] " if is_rlhf else ""
                    rag_context_str += f"참조근거 {i}. [{cat}] {prefix_tag}{title} ({src}){hier_info}\n{content}\n\n"
                
                # RLHF Alignment Enforcement Instruction
                if has_rlhf_in_context:
                    rag_context_str += (
                        "\n=======================================================\n"
                        "【⚖️ 법원 심사관 공인 모범 정답 (Gold Standard Alignment) 가드레일】\n"
                        "참조 근거에 현직 법원 심사관이 직접 검증한 [심사관 공인 모범 정답]이 포함되어 있습니다.\n"
                        "최종 답변 작성 시 이 모범 정답의 심사 결론, 수리 여부 판단, 필수 제출서류 목록을 최우선 사실로 100% 준수하십시오.\n"
                        "공인 모범 정답의 법적 결론과 모순되거나 배치되는 독자적 추론을 일체 금지합니다.\n"
                        "=======================================================\n\n"
                    )

                system_prompt += rag_context_str
        except Exception as e:
            print(f"[RAG] Retrieval error: {e}")

    # 4.5 RIG: Retrieval-Interleaved Generation (국가법령정보센터 실시간 원문 대조 루프)
    if use_rig and rag_search_query:
        try:
            yield {
                "type": "rig_step",
                "data": {
                    "step": "law_identify",
                    "message": "🔍 관련 법령 조문 쟁점 분석 및 국가법령정보센터 실시간 대조 중..."
                }
            }

            # Gather target text for statutory citation discovery (user query + RAG titles/previews)
            target_snippets = [rag_search_query]
            for d in retrieved_docs[:3]:
                target_snippets.append(d.get("title", "") + " " + d.get("content", "")[:300])
            combined_target = "\n".join(target_snippets)

            verified_laws = await rig_engine.verify_citations(combined_target)

            if verified_laws:
                for law_item in verified_laws:
                    yield {
                        "type": "rig_step",
                        "data": {
                            "step": "law_verify",
                            "law": law_item.get("statute_name"),
                            "article": law_item.get("article_no"),
                            "title": law_item.get("article_title"),
                            "tier": law_item.get("retrieval_tier"),
                            "url": law_item.get("law_url"),
                            "status": "verified",
                            "message": f"🏛️ {law_item.get('statute_name')} {law_item.get('article_no')} 국가법령정보센터 실시간 대조 완료 ({law_item.get('retrieval_tier')})"
                        }
                    }

                verified_context = rig_engine.format_verified_context(verified_laws)
                system_prompt += verified_context

                yield {
                    "type": "rig_step",
                    "data": {
                        "step": "law_grounded",
                        "message": f"✅ 총 {len(verified_laws)}개 현행 법률 조문 원문 실시간 검증 완료 (공식 법령 기반 답변 작성)"
                    }
                }
        except Exception as e:
            print(f"[RIG] Interleaved verification error: {e}")


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
                success = False
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
                            success = True
                            break
                    except Exception as e:
                        if attempt == max_retries:
                            yield {"type": "error", "data": f"\n\n[통신 오류]: {str(e)}"}
                            return
                        await asyncio.sleep(1.5 * (attempt + 1))
                if not success:
                    return
    finally:
        if is_queued and waiting_queue_count > 0:
            pass

    # 5.5 CoVe (Chain-of-Verification) Fact Check & Actionable Artifacts Binding
    audit_result = fact_checker.audit_response(
        accumulated_response,
        verified_laws=verified_laws if 'verified_laws' in locals() and verified_laws else [],
        retrieved_docs=retrieved_docs if 'retrieved_docs' in locals() and retrieved_docs else [],
        is_cached=False
    )
    yield {
        "type": "cove_audit",
        "data": audit_result
    }

    matched_forms = form_matcher.match(last_user_query + " " + accumulated_response)
    if matched_forms:
        yield {
            "type": "action_forms",
            "data": matched_forms
        }

    # 6. Post-processing: Latency, Tokens, Metrics & Cache Storage
    latency_ms = int((time.time() - start_time) * 1000)
    completion_tokens_est = estimate_tokens(accumulated_response)
    total_tokens_est = prompt_tokens_est + completion_tokens_est

    # Cache the result only for standalone single-turn queries to prevent context mismatch
    if accumulated_response and last_user_query and not is_multiturn and not bypass_cache:
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

    # Yield performance metrics to client with confidence score
    yield {
        "type": "metrics",
        "data": {
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens_est,
            "completion_tokens": completion_tokens_est,
            "total_tokens": total_tokens_est,
            "model": model,
            "cached": False,
            "confidence_score": audit_result.get("confidence_score", 95),
            "confidence_rating": audit_result.get("rating", "최고 신뢰 등급")
        }
    }

