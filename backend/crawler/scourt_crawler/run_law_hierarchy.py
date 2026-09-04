import os
import sys
import json
import time

# Ensure src can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.open_law_api import OpenLawAPI
from src.law_normalizer import parse_law_service_response, parse_admrul_service_response

def extract_all_admrul(node):
    """
    체계도 트리에서 행정규칙(예규, 지침 등) 노드를 재귀적으로 추출
    """
    results = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "행정규칙":
                if isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        if isinstance(sub_v, list):
                            for item in sub_v:
                                results.append(item.get("기본정보", item))
                        elif isinstance(sub_v, dict):
                            results.append(sub_v.get("기본정보", sub_v))
            else:
                results.extend(extract_all_admrul(v))
    elif isinstance(node, list):
        for item in node:
            results.extend(extract_all_admrul(item))
    return results

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 70)
    print("국가법령정보 공동활용(open.law.go.kr) Open API 기반 법령체계도 수집기")
    print("인증키(OC): familylawapi")
    print("=" * 70)
    print(f"산출물 저장 디렉토리: {output_dir}\n")
    
    start_time = time.time()
    api = OpenLawAPI(oc="familylawapi", delay_sec=0.15)
    
    # ----------------------------------------------------
    # 1. 법령체계도 트리 조회 (MST: 257203)
    # ----------------------------------------------------
    print("▶ [1/4] 「가족관계의 등록 등에 관한 법률」 법령체계도 트리 조회 중...")
    stmd_raw = api.get_law_hierarchy(mst=257203)
    stmd = stmd_raw.get("법령체계도", {})
    
    base_info = stmd.get("기본정보", {})
    sub_laws_dict = stmd.get("상하위법", {})
    law_tree_node = sub_laws_dict.get("법률", {})
    
    # 하위 대법원규칙 정보 추출 (체계도상 '시행령' 또는 '시행규칙' 키에 위치)
    sub_rule_node = law_tree_node.get("시행령", {}) or law_tree_node.get("시행규칙", {})
    sub_rule_info = sub_rule_node.get("기본정보", {})
    
    # 위임 행정규칙(예규/지침) 목록 추출 및 중복 제거
    raw_adm_rules = extract_all_admrul(sub_laws_dict)
    seen_adm_ids = set()
    unique_adm_rules = []
    for adm in raw_adm_rules:
        adm_id = adm.get("행정규칙일련번호") or adm.get("행정규칙ID")
        if adm_id and adm_id not in seen_adm_ids:
            seen_adm_ids.add(adm_id)
            unique_adm_rules.append(adm)
            
    # 관련 특례법 목록
    con_laws = stmd.get("관련법령", {}).get("conlaw", [])
    if isinstance(con_laws, dict):
        con_laws = [con_laws]
        
    print(f"✓ 체계도 구조 파악 완료:")
    print(f"  - 모법: {base_info.get('법령명')} (MST: {base_info.get('법령일련번호')})")
    print(f"  - 하위규칙: {sub_rule_info.get('법령명')} (MST: {sub_rule_info.get('법령일련번호')})")
    print(f"  - 위임 행정규칙: 총 {len(unique_adm_rules)}건")
    print(f"  - 관련 특례법: 총 {len(con_laws)}건")
    
    # ----------------------------------------------------
    # 2. 모법 및 하위 대법원규칙 본문 상세 수집
    # ----------------------------------------------------
    print("\n▶ [2/4] 모법 및 하위 대법원규칙 본문 수집 중...")
    
    # 2-1. 모법 본문
    print(f"  수집 중: {base_info.get('법령명')}...", end='', flush=True)
    root_law_detail = api.get_law_detail(mst=int(base_info.get("법령일련번호", 257203)))
    parsed_root_law = parse_law_service_response(root_law_detail, hierarchy_info={"level": 1, "parent": None})
    print(f" 완료 (조문 {len(parsed_root_law['articles'])}개)")
    
    # 2-2. 하위 대법원규칙 본문
    print(f"  수집 중: {sub_rule_info.get('법령명')}...", end='', flush=True)
    sub_rule_detail = api.get_law_detail(mst=int(sub_rule_info.get("법령일련번호", 272659)))
    parsed_sub_rule = parse_law_service_response(sub_rule_detail, hierarchy_info={"level": 2, "parent": parsed_root_law["statute_name"]})
    print(f" 완료 (조문 {len(parsed_sub_rule['articles'])}개)")
    
    # ----------------------------------------------------
    # 3. 위임 행정규칙 (13건) 본문 수집
    # ----------------------------------------------------
    print(f"\n▶ [3/4] 위임 행정규칙 ({len(unique_adm_rules)}건) 본문 수집 중...")
    parsed_adm_rules = []
    for idx, meta in enumerate(unique_adm_rules, start=1):
        adm_id = meta.get("행정규칙일련번호") or meta.get("행정규칙ID")
        adm_name = meta.get("행정규칙명")
        print(f"\r  [{idx:2d}/{len(unique_adm_rules)}] 수집 중: {adm_name[:40]:<40}", end='', flush=True)
        try:
            adm_detail = api.get_admrul_detail(adm_id)
            parsed_adm = parse_admrul_service_response(
                adm_detail,
                meta_info=meta,
                hierarchy_info={"level": 3, "parent": parsed_sub_rule["statute_name"]}
            )
            parsed_adm_rules.append(parsed_adm)
        except Exception as e:
            print(f"\n  [경고] {adm_name} 수집 실패: {e}")
    print("\n✓ 위임 행정규칙 수집 완료")

    # ----------------------------------------------------
    # 4. 관련 특례법 (6건) 본문 수집
    # ----------------------------------------------------
    print(f"\n▶ [4/4] 체계도 관련 특례법 ({len(con_laws)}건) 본문 수집 중...")
    parsed_con_laws = []
    for idx, con in enumerate(con_laws, start=1):
        mst = int(con.get("법령일련번호"))
        law_name = con.get("법령명")
        print(f"\r  [{idx:2d}/{len(con_laws)}] 수집 중: {law_name[:40]:<40}", end='', flush=True)
        try:
            law_detail = api.get_law_detail(mst)
            parsed_con = parse_law_service_response(
                law_detail,
                hierarchy_info={"level": "관련법령", "parent": parsed_root_law["statute_name"]}
            )
            parsed_con_laws.append(parsed_con)
        except Exception as e:
            print(f"\n  [경고] {law_name} 수집 실패: {e}")
    print("\n✓ 관련 특례법 수집 완료")

    # ----------------------------------------------------
    # 5. 산출물 파일 저장
    # ----------------------------------------------------
    # 5-1. 모법 + 대법원규칙 (family_act_and_rule.json)
    act_rule_file = os.path.join(output_dir, "family_act_and_rule.json")
    with open(act_rule_file, 'w', encoding='utf-8') as f:
        json.dump([parsed_root_law, parsed_sub_rule], f, ensure_ascii=False, indent=2)
        
    # 5-2. 위임 행정규칙 (family_delegated_rules.json)
    delegated_file = os.path.join(output_dir, "family_delegated_rules.json")
    with open(delegated_file, 'w', encoding='utf-8') as f:
        json.dump(parsed_adm_rules, f, ensure_ascii=False, indent=2)

    # 5-3. 관련 특례법 (family_related_special_laws.json)
    special_file = os.path.join(output_dir, "family_related_special_laws.json")
    with open(special_file, 'w', encoding='utf-8') as f:
        json.dump(parsed_con_laws, f, ensure_ascii=False, indent=2)

    # 5-4. 전체 법령체계도 통합본 (family_law_hierarchy.json)
    all_hierarchy = {
        "metadata": {
            "source": "국가법령정보 공동활용 Open API (open.law.go.kr)",
            "api_key": "familylawapi",
            "root_statute": parsed_root_law["statute_name"],
            "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_regulations": 1 + 1 + len(parsed_adm_rules) + len(parsed_con_laws)
        },
        "tree_structure": {
            "level_1_root_act": parsed_root_law["statute_name"],
            "level_2_subordinate_rule": parsed_sub_rule["statute_name"],
            "level_3_delegated_administrative_rules": [r["statute_name"] for r in parsed_adm_rules],
            "related_special_acts": [r["statute_name"] for r in parsed_con_laws]
        },
        "regulations": {
            "root_act": parsed_root_law,
            "subordinate_rule": parsed_sub_rule,
            "delegated_administrative_rules": parsed_adm_rules,
            "related_special_acts": parsed_con_laws
        }
    }
    hierarchy_file = os.path.join(output_dir, "family_law_hierarchy.json")
    with open(hierarchy_file, 'w', encoding='utf-8') as f:
        json.dump(all_hierarchy, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"법령체계도 전수 수집이 성공적으로 완료되었습니다! (총 소요 시간: {elapsed:.1f}초)")
    print(f"  1. [통합 체계도] family_law_hierarchy.json ({os.path.getsize(hierarchy_file)/1024:.1f} KB)")
    print(f"  2. [모법+대법원규칙] family_act_and_rule.json ({os.path.getsize(act_rule_file)/1024:.1f} KB)")
    print(f"  3. [위임 행정규칙 13건] family_delegated_rules.json ({os.path.getsize(delegated_file)/1024:.1f} KB)")
    print(f"  4. [관련 특례법 6건] family_related_special_laws.json ({os.path.getsize(special_file)/1024:.1f} KB)")
    print("=" * 70)

if __name__ == "__main__":
    main()
