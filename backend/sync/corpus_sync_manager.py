import os
import sys
import json
import time
import asyncio
import subprocess
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

KST = timezone(timedelta(hours=9))

class CorpusSyncManager:
    """
    대법원 사법정보공개포털(run_crawler.py) 및 법령체계도(run_law_hierarchy.py) 수집기 연동,
    지식 코퍼스 정규화, 마스터 코퍼스 동기화 및 00시/수동 현행화 관리자
    """
    def __init__(self):
        self.backend_dir = Path(__file__).resolve().parent.parent
        self.data_dir = self.backend_dir / "data"
        self.corpus_dir = self.data_dir / "corpus"
        self.corpus_dir.mkdir(parents=True, exist_ok=True)
        
        # 크롤러 탐색 (내장 번들 우선, 외부 스크래치 경로 fallback)
        self.bundled_crawler_dir = self.backend_dir / "crawler" / "scourt_crawler"
        self.external_crawler_dir = Path(r"C:\Users\rawfu\.gemini\antigravity-ide\scratch\scourt-crawler")
        
        self.master_corpus_file = self.corpus_dir / "master_family_reg_knowledge_corpus.json"
        self.sync_history_file = self.data_dir / "sync_history.json"
        
        # 동기화 진행 상태
        self.is_running = False
        self.current_stage = "대기 중"
        self.last_synced_at: Optional[str] = None
        self.last_error: Optional[str] = None
        self.last_counts: Dict[str, Any] = {}
        
        # 이력 로드
        self._load_history()

    def _load_history(self):
        if self.sync_history_file.exists():
            try:
                with open(self.sync_history_file, "r", encoding="utf-8") as f:
                    hist = json.load(f)
                    self.last_synced_at = hist.get("last_synced_at")
                    self.last_counts = hist.get("last_counts", {})
            except Exception as e:
                print(f"[SyncManager] Warning loading history: {e}")

    def _save_history(self, counts: Dict[str, Any], status: str = "success", error: Optional[str] = None):
        self.last_synced_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
        self.last_counts = counts
        self.last_error = error
        data = {
            "last_synced_at": self.last_synced_at,
            "status": status,
            "last_counts": counts,
            "error": error
        }
        try:
            with open(self.sync_history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SyncManager] Warning saving history: {e}")

    def get_crawler_dir(self) -> Path:
        """유효한 크롤러 디렉토리 반환"""
        if (self.bundled_crawler_dir / "run_crawler.py").exists():
            return self.bundled_crawler_dir
        if (self.external_crawler_dir / "run_crawler.py").exists():
            return self.external_crawler_dir
        return self.bundled_crawler_dir

    def get_output_dir(self) -> Path:
        """산출물 디렉토리 반환"""
        cdir = self.get_crawler_dir()
        out_dir = cdir / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def get_next_midnight_kst(self) -> str:
        """다음 00:00:00 KST 시각 문자열 계산"""
        now = datetime.now(KST)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return next_midnight.strftime("%Y-%m-%d %H:%M:%S KST")

    def get_status(self) -> Dict[str, Any]:
        """현재 동기화 상태 및 통계 반환"""
        return {
            "is_running": self.is_running,
            "current_stage": self.current_stage,
            "last_synced_at": self.last_synced_at or "동기화 이력 없음",
            "next_scheduled_sync": self.get_next_midnight_kst(),
            "last_counts": self.last_counts,
            "last_error": self.last_error,
            "crawler_dir": str(self.get_crawler_dir()),
            "master_corpus_exists": self.master_corpus_file.exists()
        }

    async def run_crawler_scripts(self) -> Dict[str, Any]:
        """
        run_law_hierarchy.py 및 run_crawler.py 서브프로세스 비동기 실행
        """
        crawler_dir = self.get_crawler_dir()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        # 1. 국가법령정보 법령체계도 수집 (run_law_hierarchy.py)
        self.current_stage = "1/2: 국가법령정보 법령체계도(모법·규칙·위임예규·특례법) 수집 중..."
        print(f"[SyncManager] {self.current_stage}")
        
        proc1 = await asyncio.create_subprocess_exec(
            sys.executable, "-X", "utf8", "run_law_hierarchy.py",
            cwd=str(crawler_dir),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout1, stderr1 = await proc1.communicate()
        if proc1.returncode != 0:
            err_msg = stderr1.decode("utf-8", errors="ignore")
            print(f"[SyncManager] Warning: run_law_hierarchy exited with code {proc1.returncode}: {err_msg[:200]}")

        # 2. 대법원 사법정보공개포털 예규·선례 수집 (run_crawler.py)
        self.current_stage = "2/2: 대법원 사법정보공개포털(예규 200건·선례 78건) 수집 중..."
        print(f"[SyncManager] {self.current_stage}")
        
        proc2 = await asyncio.create_subprocess_exec(
            sys.executable, "-X", "utf8", "run_crawler.py",
            cwd=str(crawler_dir),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout2, stderr2 = await proc2.communicate()
        if proc2.returncode != 0:
            err_msg = stderr2.decode("utf-8", errors="ignore")
            print(f"[SyncManager] Warning: run_crawler exited with code {proc2.returncode}: {err_msg[:200]}")

        return {"status": "crawlers_finished"}

    def normalize_rules(self, rules_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """family_rules.json (예규 200건) RAG 정규화"""
        docs = []
        for r in rules_data:
            data_no = str(r.get("data_no", "")).strip()
            title = r.get("title", "").strip()
            item_id = r.get("id")
            content_text = r.get("content_text", "").strip()
            promulgation_date = r.get("promulgation_date") or ""
            enforcement_date = r.get("enforcement_date") or ""
            status = r.get("status") or "현행"
            directory_path = r.get("directory_path") or []
            
            dir_str = " > ".join(directory_path) if directory_path else "가족관계등록예규"
            header = f"【가족관계등록예규 제{data_no}호】 {title}\n• 발령일자: {promulgation_date} | 시행일자: {enforcement_date} | 상태: {status}\n• 소관구분: {dir_str}\n\n"
            full_content = header + content_text
            
            docs.append({
                "id": f"SCOURT-DIR-{data_no}",
                "title": f"[가족관계등록예규 제{data_no}호] {title}",
                "category": "가족관계등록예규",
                "source": f"대법원 사법정보공개포털 (가족관계등록예규 제{data_no}호, JIS:{item_id})",
                "content": full_content,
                "created_at": int(time.time()),
                "file_name": "family_rules.json",
                "metadata": {
                    "item_type": "예규",
                    "data_no": data_no,
                    "raw_no": f"제{data_no}호",
                    "jis_id": item_id,
                    "promulgation_date": promulgation_date,
                    "enforcement_date": enforcement_date,
                    "status": status,
                    "directory_path": directory_path
                }
            })
        return docs

    def normalize_precedents(self, precedents_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """family_precedents.json (선례 78건) RAG 정규화"""
        docs = []
        for p in precedents_data:
            data_no = str(p.get("data_no", "")).strip()
            title = p.get("title", "").strip()
            item_id = p.get("id")
            content_text = p.get("content_text", "").strip()
            promulgation_date = p.get("promulgation_date") or ""
            status = p.get("status") or "현행"
            directory_path = p.get("directory_path") or []
            
            dir_str = " > ".join(directory_path) if directory_path else "가족관계등록선례"
            header = f"【가족관계등록선례 {data_no}】 {title}\n• 생산일자: {promulgation_date} | 상태: {status}\n• 소관구분: {dir_str}\n\n"
            full_content = header + content_text
            
            docs.append({
                "id": f"SCOURT-PREC-{data_no}",
                "title": f"[가족관계등록선례 {data_no}] {title}",
                "category": "가족관계등록선례",
                "source": f"대법원 사법정보공개포털 (가족관계등록선례 {data_no}, JIS:{item_id})",
                "content": full_content,
                "created_at": int(time.time()),
                "file_name": "family_precedents.json",
                "metadata": {
                    "item_type": "선례",
                    "data_no": data_no,
                    "jis_id": item_id,
                    "promulgation_date": promulgation_date,
                    "status": status,
                    "directory_path": directory_path
                }
            })
        return docs

    def normalize_law_hierarchy(self, hierarchy_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """family_law_hierarchy.json 법령체계도 정규화 (모법, 대법원규칙, 위임예규, 관련특례법)"""
        docs = []
        regulations = hierarchy_data.get("regulations", {})
        
        # 1. 모법 (가족관계의 등록 등에 관한 법률) 조문별 지식화
        root_act = regulations.get("root_act", {})
        root_name = root_act.get("statute_name", "가족관계의 등록 등에 관한 법률")
        root_articles = root_act.get("articles", [])
        
        for art in root_articles:
            art_no = art.get("article_no", "").strip()
            art_title = art.get("article_title", "").strip()
            art_content = art.get("content", "").strip()
            paragraphs = art.get("paragraphs", [])
            
            body_lines = [art_content]
            for p in paragraphs:
                p_no = p.get("paragraph_no", "")
                p_txt = p.get("content", "")
                body_lines.append(f"{p_no} {p_txt}".strip())
                for item in p.get("sub_items", []):
                    body_lines.append(f"  {item.get('item_no', '')} {item.get('content', '')}".strip())
                    
            full_body = "\n".join([line for line in body_lines if line.strip()]).strip()
            if not full_body or len(full_body) < 10:
                continue
                
            clean_art_no = art_no.replace(" ", "")
            title_str = f"[{root_name}] {art_no}" + (f" ({art_title})" if art_title else "")
            
            docs.append({
                "id": f"LAW-ACT-{clean_art_no}",
                "title": title_str,
                "category": "가족관계등록법",
                "source": f"국가법령정보공동활용 ({root_name})",
                "content": f"【{root_name} {art_no}】\n• 법령위계: 1단계 상위모법 (법률)\n\n{full_body}",
                "created_at": int(time.time()),
                "file_name": "family_law_hierarchy.json",
                "hierarchy_data": {
                    "statute_level": "법률",
                    "article_number": art_no,
                    "statute_name": root_name
                }
            })

        # 2. 하위규칙 (가족관계의 등록 등에 관한 규칙) 조문별 지식화
        sub_rule = regulations.get("subordinate_rule", {})
        sub_name = sub_rule.get("statute_name", "가족관계의 등록 등에 관한 규칙")
        sub_articles = sub_rule.get("articles", [])
        
        for art in sub_articles:
            art_no = art.get("article_no", "").strip()
            art_title = art.get("article_title", "").strip()
            art_content = art.get("content", "").strip()
            paragraphs = art.get("paragraphs", [])
            
            body_lines = [art_content]
            for p in paragraphs:
                p_no = p.get("paragraph_no", "")
                p_txt = p.get("content", "")
                body_lines.append(f"{p_no} {p_txt}".strip())
                for item in p.get("sub_items", []):
                    body_lines.append(f"  {item.get('item_no', '')} {item.get('content', '')}".strip())
                    
            full_body = "\n".join([line for line in body_lines if line.strip()]).strip()
            if not full_body or len(full_body) < 10:
                continue
                
            clean_art_no = art_no.replace(" ", "")
            title_str = f"[{sub_name}] {art_no}" + (f" ({art_title})" if art_title else "")
            
            docs.append({
                "id": f"LAW-RULE-{clean_art_no}",
                "title": title_str,
                "category": "가족관계등록규칙",
                "source": f"국가법령정보공동활용 ({sub_name})",
                "content": f"【{sub_name} {art_no}】\n• 법령위계: 2단계 하위 대법원규칙\n• 상위모법: {root_name}\n\n{full_body}",
                "created_at": int(time.time()),
                "file_name": "family_law_hierarchy.json",
                "hierarchy_data": {
                    "statute_level": "대법원규칙",
                    "article_number": art_no,
                    "statute_name": sub_name
                }
            })

        return docs

    def build_integrated_corpus(self) -> List[Dict[str, Any]]:
        """
        output 디렉토리의 크롤링 파일들과 기존 포털 지식을 결합하여 전체 마스터 코퍼스 빌드
        """
        out_dir = self.get_output_dir()
        rules_file = out_dir / "family_rules.json"
        prec_file = out_dir / "family_precedents.json"
        hierarchy_file = out_dir / "family_law_hierarchy.json"
        
        crawled_docs = []
        rules_count = 0
        prec_count = 0
        hier_count = 0

        # 1. 예규 로드
        if rules_file.exists():
            try:
                with open(rules_file, "r", encoding="utf-8") as f:
                    r_data = json.load(f)
                    norm_rules = self.normalize_rules(r_data)
                    crawled_docs.extend(norm_rules)
                    rules_count = len(norm_rules)
            except Exception as e:
                print(f"[SyncManager] Error loading rules: {e}")

        # 2. 선례 로드
        if prec_file.exists():
            try:
                with open(prec_file, "r", encoding="utf-8") as f:
                    p_data = json.load(f)
                    norm_prec = self.normalize_precedents(p_data)
                    crawled_docs.extend(norm_prec)
                    prec_count = len(norm_prec)
            except Exception as e:
                print(f"[SyncManager] Error loading precedents: {e}")

        # 3. 법령체계도 로드
        if hierarchy_file.exists():
            try:
                with open(hierarchy_file, "r", encoding="utf-8") as f:
                    h_data = json.load(f)
                    norm_hier = self.normalize_law_hierarchy(h_data)
                    crawled_docs.extend(norm_hier)
                    hier_count = len(norm_hier)
            except Exception as e:
                print(f"[SyncManager] Error loading law hierarchy: {e}")

        # 4. 기존 전자가족관계등록 포털 실무(73건) 및 생활법령(117건) 결합
        f_efamily = self.corpus_dir / "efamily_scourt_guide_corpus.json"
        f_easylaw = self.corpus_dir / "easylaw_family_reg_corpus.json"
        
        efamily_docs = []
        easylaw_docs = []
        if f_efamily.exists():
            try:
                with open(f_efamily, "r", encoding="utf-8") as f:
                    efamily_docs = json.load(f)
            except Exception:
                pass
        if f_easylaw.exists():
            try:
                with open(f_easylaw, "r", encoding="utf-8") as f:
                    easylaw_docs = json.load(f)
            except Exception:
                pass

        combined = crawled_docs + efamily_docs + easylaw_docs
        
        # ID 중복 제거 (최신 크롤링 데이터 우선)
        unique_docs = []
        seen_ids = set()
        for doc in combined:
            did = str(doc.get("id", ""))
            if did and did not in seen_ids:
                seen_ids.add(did)
                unique_docs.append(doc)

        print(f"[SyncManager] Integrated corpus: 예규 {rules_count}건, 선례 {prec_count}건, 법령체계 {hier_count}건, 포털 190건 = 총 {len(unique_docs)}건")
        return unique_docs

    async def sync(self, run_crawlers: bool = True) -> Dict[str, Any]:
        """
        전체 동기화 파이프라인 실행:
        1. (옵션) 수집기 2종 실행
        2. 최신 산출물 파싱 및 마스터 코퍼스 빌드
        3. master_family_reg_knowledge_corpus.json 저장
        4. RAG 서비스에 동기화 및 벡터 재임베딩
        """
        if self.is_running:
            return {
                "success": False,
                "message": "이미 지식 코퍼스 현행화가 진행 중입니다.",
                "status": self.get_status()
            }

        self.is_running = True
        self.last_error = None
        start_time = time.time()

        try:
            # 1. 크롤러 실행
            if run_crawlers:
                await self.run_crawler_scripts()

            # 2. 산출물 정규화 및 통합 코퍼스 빌드
            self.current_stage = "지식 코퍼스 정규화 및 마스터 데이터 병합 중..."
            print(f"[SyncManager] {self.current_stage}")
            new_corpus = self.build_integrated_corpus()

            if not new_corpus:
                raise RuntimeError("통합 코퍼스 생성 결과가 비어있습니다.")

            # 3. 마스터 코퍼스 파일 갱신
            with open(self.master_corpus_file, "w", encoding="utf-8") as f:
                json.dump(new_corpus, f, ensure_ascii=False, indent=2)

            # 4. RAG 서비스 인스턴스에 즉시 반영 및 임베딩 갱신
            self.current_stage = "RAG 서비스 벡터 임베딩 동기화 중..."
            print(f"[SyncManager] {self.current_stage}")
            
            from rag.rag_service import rag_service
            rag_service.corpus = new_corpus
            await rag_service._generate_and_save_corpus_embeddings()

            elapsed = round(time.time() - start_time, 1)
            counts = {
                "total_docs": len(new_corpus),
                "duration_sec": elapsed,
                "synced_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
            }
            self._save_history(counts=counts, status="success")
            self.current_stage = "현행화 완료"
            print(f"[SyncManager] Successfully synced {len(new_corpus)} documents in {elapsed}s.")

            return {
                "success": True,
                "message": f"지식 코퍼스 현행화가 성공적으로 완료되었습니다. (총 {len(new_corpus)}건, {elapsed}초 소요)",
                "counts": counts
            }

        except Exception as e:
            traceback.print_exc()
            err_str = str(e)
            self.last_error = err_str
            self.current_stage = f"오류 발생: {err_str[:80]}"
            self._save_history(counts={}, status="error", error=err_str)
            return {
                "success": False,
                "message": f"현행화 중 오류 발생: {err_str}",
                "error": err_str
            }
        finally:
            self.is_running = False

    async def ensure_default_knowledge(self):
        """
        서버 기동 시 기본 지식 등록:
        마스터 코퍼스 파일이 없거나 크롤러 최신 산출물이 반영되지 않은 경우 즉시 빌드 및 활성화
        """
        print("[SyncManager] Checking default knowledge corpus on startup...")
        out_dir = self.get_output_dir()
        has_outputs = (out_dir / "family_rules.json").exists() and (out_dir / "family_precedents.json").exists()

        if not self.master_corpus_file.exists() or (self.master_corpus_file.stat().st_size < 1000):
            print("[SyncManager] Master corpus not found. Building from crawler outputs...")
            if not has_outputs:
                print("[SyncManager] Outputs not found. Running crawler scripts first...")
                await self.run_crawler_scripts()
            new_corpus = self.build_integrated_corpus()
            with open(self.master_corpus_file, "w", encoding="utf-8") as f:
                json.dump(new_corpus, f, ensure_ascii=False, indent=2)
            print(f"[SyncManager] Initial master corpus created with {len(new_corpus)} documents.")
        else:
            print(f"[SyncManager] Master corpus verified ({self.master_corpus_file.stat().st_size/1024:.1f} KB).")

corpus_sync_manager = CorpusSyncManager()
