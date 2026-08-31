import io
import time
import re
from typing import List, Dict, Any, Optional
import openpyxl

def normalize_col_name(col: str) -> str:
    """컬럼명 정규화 (공백/특수문자 제거 및 소문자화)"""
    return re.sub(r'[\s_\-\[\]\(\)]', '', str(col)).lower()

def match_column_key(col_name: str) -> Optional[str]:
    """다양한 형태의 엑셀 헤더를 표준 필드명으로 지능형 매핑"""
    norm = normalize_col_name(col_name)
    
    if any(k in norm for k in ['업무', '주제', '대분류', '분야', '업무구분', '사건', '사안', '제목', '카테고리']):
        return 'domain'
    if any(k in norm for k in ['상위법', '법률', '상위법률', '근거법률', '모법', '법조항', '법률조항', '1단계']):
        return 'primary_law'
    if any(k in norm for k in ['대법원규칙', '하위규칙', '규칙', '시행규칙', '위임규칙', '규칙조항', '2단계']):
        return 'sub_rule'
    if any(k in norm for k in ['대법원예규', '예규', '행정예규', '처리지침', '업무처리지침', '지침', '예규번호', '3단계']):
        return 'directive'
    if any(k in norm for k in ['등록선례', '선례', '판례', '선례번호', '유권해석', '질의회신', '4단계']):
        return 'precedent'
    if any(k in norm for k in ['위임관계', '상하관계', '법리체계', '적용관계', '관계', '위임']):
        return 'relation'
    if any(k in norm for k in ['적용원칙', '우선순위', '판단기준', '실무요령', '비고', '주의사항', '해설', '판단', '요건']):
        return 'priority_rules'
    
    return None

def parse_excel_hierarchy(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    엑셀 파일(.xlsx, .xls)을 파싱하여 상하위 법률 위계 지식 객체 리스트로 변환
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    sheet = wb.active
    
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []

    # 1. 헤더 행 찾기 (첫 번째 비어있지 않은 행)
    header_row_idx = 0
    header_mapping = {}
    
    for idx, row in enumerate(rows):
        non_empty = [c for c in row if c is not None and str(c).strip()]
        if len(non_empty) >= 2: # 최소 2개 이상 컬럼이 있는 행을 헤더로 간주
            header_row_idx = idx
            for col_idx, cell_val in enumerate(row):
                if cell_val is not None:
                    matched_key = match_column_key(str(cell_val))
                    if matched_key:
                        header_mapping[col_idx] = matched_key
            break

    # Fallback: 매핑된 컬럼이 없으면 순서대로 기본 매핑
    if not header_mapping and len(rows) > 0:
        default_keys = ['domain', 'primary_law', 'sub_rule', 'directive', 'precedent', 'relation', 'priority_rules']
        for c_idx in range(min(len(rows[header_row_idx]), len(default_keys))):
            header_mapping[c_idx] = default_keys[c_idx]

    docs = []
    timestamp = int(time.time())
    group_id = f"EXCEL-{timestamp}"

    # 2. 데이터 행 파싱
    for row_idx, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 2):
        if not any(row):
            continue

        item_data = {
            'domain': '',
            'primary_law': '',
            'sub_rule': '',
            'directive': '',
            'precedent': '',
            'relation': '',
            'priority_rules': ''
        }

        # 셀 값 추출
        for col_idx, cell_val in enumerate(row):
            if col_idx in header_mapping and cell_val is not None:
                val_str = str(cell_val).strip()
                item_data[header_mapping[col_idx]] = val_str

        # 유효 데이터 확인
        domain = item_data['domain'] or f"가족관계등록 실무 #{row_idx}"
        primary = item_data['primary_law']
        sub_rule = item_data['sub_rule']
        directive = item_data['directive']
        precedent = item_data['precedent']
        relation = item_data['relation']
        priority = item_data['priority_rules']

        if not any([primary, sub_rule, directive, precedent, priority]):
            continue

        # 구조화된 법령 위계 컨텍스트 텍스트 생성
        content_lines = [
            f"📌 [업무 분야/주제]: {domain}",
            f"🏛️ [1단계 상위 법률(모법)]: {primary or '해당 법률 규정 참조'}",
            f"📜 [2단계 대법원규칙(위임규정)]: {sub_rule or '대법원규칙 관련 조항 참조'}",
            f"📖 [3단계 대법원 행정예규(집행지침)]: {directive or '관련 가족관계등록예규 참조'}",
            f"🔨 [4단계 등록선례(구체적 유권해석)]: {precedent or '관련 실무선례 참조'}",
        ]

        if relation:
            content_lines.append(f"🔗 [상하위 법령 위임 및 연계 관계]: {relation}")
        if priority:
            content_lines.append(f"⚖️ [실무 적용 원칙 및 우선순위]: {priority}")

        full_content = "\n".join(content_lines)
        doc_id = f"{group_id}-{row_idx}"

        # 법령 위계 체인 배열 구축
        hierarchy_chain = []
        if primary: hierarchy_chain.append({"tier": "법률", "title": primary})
        if sub_rule: hierarchy_chain.append({"tier": "규칙", "title": sub_rule})
        if directive: hierarchy_chain.append({"tier": "예규", "title": directive})
        if precedent: hierarchy_chain.append({"tier": "선례", "title": precedent})

        docs.append({
            "id": doc_id,
            "group_id": group_id,
            "file_name": filename,
            "category": "상하위법률체계",
            "source": f"{filename} (행 {row_idx})",
            "title": f"[{domain}] 법령 위계 체계 (법률-규칙-예규-선례)",
            "content": full_content,
            "hierarchy_data": {
                "domain": domain,
                "primary_law": primary,
                "sub_rule": sub_rule,
                "directive": directive,
                "precedent": precedent,
                "relation": relation,
                "priority_rules": priority,
                "chain": hierarchy_chain
            },
            "row_index": row_idx,
            "created_at": timestamp
        })

    return docs

def create_sample_hierarchy_excel() -> bytes:
    """가족관계등록 대표 실무 10종에 대한 표준 상하위 법률 관계 엑셀 템플릿 생성"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "상하위법률관계_표준체계"

    headers = [
        "업무구분(주제)",
        "1단계: 상위 법률(모법)",
        "2단계: 대법원규칙(위임)",
        "3단계: 대법원예규(집행지침)",
        "4단계: 등록선례(유권해석)",
        "상하위 위임 및 연계 관계",
        "실무 적용원칙 및 우선순위"
    ]
    ws.append(headers)

    sample_rows = [
        [
            "전산오기 직권정정",
            "가족관계의 등록 등에 관한 법률 제18조 제2항",
            "가족관계의 등록 등에 관한 규칙 제60조 제1항",
            "가족관계등록예규 제543호 (전산정보처리조직에 의한 사무처리지침)",
            "등록선례 제201503-2호 (전산이기 착오 정정절차)",
            "법률 제18조 제2항의 위임에 따라 규칙 제60조에서 간이직권정정 대상을 한정하고, 예규 제543호에서 전산 시스템 정정 절차를 규정함",
            "상위법 우선: 법률상 법원 허가 사항은 예규로 간이정정 불가. 전산오기 명백 시에만 법원 허가 없이 직권정정 가능"
        ],
        [
            "친생추정 및 친생부인의 소",
            "민법 제844조 (남편의 친생자의 추정), 가족관계등록법 제57조",
            "가족관계의 등록 등에 관한 규칙 제43조",
            "가족관계등록예규 제460호 (친생부인 판결에 따른 등록사무)",
            "등록선례 제201208-1호 (혼인종료 후 출생자의 출생신고)",
            "민법의 친생추정 규정이 실체법적 상위법이며, 가족관계등록법 및 예규는 판결 확정 후 공부 정리 절차를 규정함",
            "실체법 우선: 친생추정이 미치는 자녀는 법원의 친생부인 판결 없이 하위 예규로 다른 사람을 부로 신고할 수 없음"
        ],
        [
            "인터넷 가족관계증명서 발급 및 수수료",
            "가족관계의 등록 등에 관한 법률 제14조, 제15조",
            "가족관계의 등록 등에 관한 규칙 제19조, 제28조",
            "전자가족관계등록시스템 운영예규 제32호",
            "등록선례 제202102-4호 (온라인 증명서 교부 청구권자 범위)",
            "법 제14조에서 발급권자를 본인·배우자·직계혈족으로 엄격히 한정하고, 규칙 및 전산예규에서 인터넷 무료 발급 규정",
            "법률상 청구권자 엄격 제한: 형제자매는 법률상 본인 위임장 없이는 인터넷/방문 발급 모두 절대 불가"
        ],
        [
            "법원 개명허가 후 개명신고",
            "가족관계의 등록 등에 관한 법률 제99조 (개명신고의무)",
            "가족관계의 등록 등에 관한 규칙 제65조",
            "가족관계등록예규 제510호 (개명신고 사무처리지침)",
            "등록선례 제201804-1호 (전자 개명신고 수리 절차)",
            "가족관계등록법 제99조에 따라 가정법원 허가일로부터 1개월 이내 신고 의무 발생, 인터넷 전자신고 가능",
            "가정법원 개명허가 결정문 없이는 관서 직권이나 당사자 신고만으로 개명 수리 불가 (상위 법원 허가 필수)"
        ],
        [
            "외국인 부모 사이의 출생 신고",
            "국제사법 제45조, 국적법 제2조, 가족관계등록법 제44조",
            "가족관계의 등록 등에 관한 규칙 제51조",
            "가족관계등록예규 제488호 (외국인에 관한 가족관계등록사무처리지침)",
            "등록선례 제201911-3호 (부모 모두 외국인인 경우 출생등록 불가)",
            "국적법상 한국 국적을 취득하지 못하는 외국인 자녀는 가족관계등록부 창설 대상이 아님",
            "상위 국적법/가족관계등록법 우선: 부모 모두 외국인인 경우 한국 등록부에 출생신고를 수리할 수 없으며 본국 대사관 안내"
        ]
    ]

    for row in sample_rows:
        ws.append(row)

    # 컬럼 너비 자동 조정
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 50)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
