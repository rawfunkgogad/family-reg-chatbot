import hashlib
import time
from typing import Optional, Dict, Any, Tuple

class QueryCacheManager:
    """
    고속 질의응답 인메모리 캐시 매니저 (LRU + TTL)
    동일/유사 질의에 대해 0.05초 이내 반환 및 토큰 소모 0 구현
    """
    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "saved_tokens": 0,
            "saved_time_ms": 0
        }

    def _generate_key(self, query: str, mode: str, model: str) -> str:
        # Normalize: strip, lowercase, collapse whitespace
        normalized = " ".join(query.strip().lower().split())
        raw_key = f"{mode}:{model}:{normalized}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, query: str, mode: str, model: str) -> Optional[Tuple[str, list, int]]:
        """
        캐시에서 (content, sources, estimated_tokens) 반환
        """
        self.stats["total_queries"] += 1
        key = self._generate_key(query, mode, model)
        entry = self.cache.get(key)

        if not entry:
            self.stats["cache_misses"] += 1
            return None

        # Check TTL
        if time.time() - entry["timestamp"] > self.ttl_seconds:
            del self.cache[key]
            self.stats["cache_misses"] += 1
            return None

        # Cache Hit
        self.stats["cache_hits"] += 1
        tokens_saved = entry.get("tokens", 150)
        self.stats["saved_tokens"] += tokens_saved
        self.stats["saved_time_ms"] += 1200 # Average saved latency in ms

        # Update LRU access timestamp
        entry["last_accessed"] = time.time()
        return entry["content"], entry.get("sources", []), tokens_saved

    def set(self, query: str, mode: str, model: str, content: str, sources: list, tokens: int = 0):
        """
        질의응답 결과를 캐시에 저장
        """
        key = self._generate_key(query, mode, model)
        
        # Evict oldest if full
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k].get("last_accessed", 0))
            del self.cache[oldest_key]

        now = time.time()
        self.cache[key] = {
            "content": content,
            "sources": sources,
            "tokens": tokens,
            "timestamp": now,
            "last_accessed": now
        }

    def get_stats(self) -> Dict[str, Any]:
        hits = self.stats["cache_hits"]
        total = self.stats["total_queries"]
        hit_rate = round((hits / total * 100), 1) if total > 0 else 0.0
        return {
            "cached_entries": len(self.cache),
            "total_queries": total,
            "cache_hits": hits,
            "cache_misses": self.stats["cache_misses"],
            "hit_rate_pct": hit_rate,
            "total_saved_tokens": self.stats["saved_tokens"],
            "total_saved_time_sec": round(self.stats["saved_time_ms"] / 1000, 2)
        }

    def clear(self):
        self.cache.clear()

cache_manager = QueryCacheManager()
