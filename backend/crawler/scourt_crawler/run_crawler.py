import os
import sys
import json
import time

# Ensure src can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scourt_api import ScourtAPIClient
from src.crawler import ScourtCrawler

def progress_printer(idx: int, total: int, title: str):
    percent = (idx / total) * 100 if total > 0 else 0
    short_title = (title[:40] + '..') if len(title) > 42 else title
    print(f"\r[{idx:3d}/{total:3d}] ({percent:5.1f}%) 수집 중: {short_title:<45}", end='', flush=True)

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "output")
    checkpoint_dir = os.path.join(base_dir, "checkpoints")
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    print("=" * 70)
    print("대법원 사법정보공개포털 가족관계등록예규 및 선례 자동 수집기")
    print("=" * 70)
    print(f"산출물 저장 디렉토리: {output_dir}\n")
    
    start_total_time = time.time()
    client = ScourtAPIClient(delay_sec=0.15, timeout_sec=15)
    crawler = ScourtCrawler(client=client, checkpoint_dir=checkpoint_dir)
    
    # ----------------------------------------------------
    # 1. 가족관계등록예규 수집 (현행만)
    # ----------------------------------------------------
    print("▶ [1/2] 가족관계등록예규 (현행) 수집 시작...")
    rules_start = time.time()
    rules = crawler.crawl_dataset(
        target_type="rules",
        current_only=True,
        on_progress=progress_printer
    )
    print() # new line
    rules_elapsed = time.time() - rules_start
    print(f"✓ 가족관계등록예규 수집 완료: 총 {len(rules)}건 ({rules_elapsed:.1f}초 소요)")
    
    rules_file = os.path.join(output_dir, "family_rules.json")
    with open(rules_file, 'w', encoding='utf-8') as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
    rules_size_mb = os.path.getsize(rules_file) / (1024 * 1024)
    print(f"  - 저장 완료: {rules_file} ({rules_size_mb:.2f} MB)")
    
    # ----------------------------------------------------
    # 2. 가족관계등록선례 수집 (전체)
    # ----------------------------------------------------
    print("\n▶ [2/2] 가족관계등록선례 수집 시작...")
    precedents_start = time.time()
    precedents = crawler.crawl_dataset(
        target_type="precedents",
        current_only=False, # 선례는 전체 78건
        on_progress=progress_printer
    )
    print() # new line
    precedents_elapsed = time.time() - precedents_start
    print(f"✓ 가족관계등록선례 수집 완료: 총 {len(precedents)}건 ({precedents_elapsed:.1f}초 소요)")
    
    precedents_file = os.path.join(output_dir, "family_precedents.json")
    with open(precedents_file, 'w', encoding='utf-8') as f:
        json.dump(precedents, f, ensure_ascii=False, indent=2)
    precedents_size_mb = os.path.getsize(precedents_file) / (1024 * 1024)
    print(f"  - 저장 완료: {precedents_file} ({precedents_size_mb:.2f} MB)")
    
    # ----------------------------------------------------
    # 3. 요약 메타데이터 저장
    # ----------------------------------------------------
    summary = {
        "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_rules": len(rules),
        "total_precedents": len(precedents),
        "files": {
            "rules": "family_rules.json",
            "precedents": "family_precedents.json"
        },
        "sample_rule": {
            "title": rules[0]["title"] if rules else None,
            "data_no": rules[0]["data_no"] if rules else None
        },
        "sample_precedent": {
            "title": precedents[0]["title"] if precedents else None,
            "data_no": precedents[0]["data_no"] if precedents else None
        }
    }
    summary_file = os.path.join(output_dir, "data_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        
    total_elapsed = time.time() - start_total_time
    print("\n" + "=" * 70)
    print(f"모든 수집 작업이 성공적으로 완료되었습니다! (총 소요 시간: {total_elapsed:.1f}초)")
    print(f"  - 예규: {len(rules)}건 -> family_rules.json")
    print(f"  - 선례: {len(precedents)}건 -> family_precedents.json")
    print("=" * 70)

if __name__ == "__main__":
    main()
