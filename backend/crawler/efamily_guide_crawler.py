"""
대법원 전자가족관계등록시스템(efamily.scourt.go.kr) 고객센터 통합 수집기
수집 대상:
1. 자주 하는 질문 (FAQ) 112건 (bltnbordId=0000003)
2. 인터넷 증명서 발급 방법 안내 (guideCd=0000009001)
3. 인터넷 신고 방법 안내 (guideCd=0000009002)
4. 아포스티유 안내 (guideCd=0000009003)
5. 신청서 양식 다운로드 46건 (bltnbordId=0000005)
"""
import os
import sys
import json
import html
import re
import time
import httpx
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional

BASE_URL = "https://efamily.scourt.go.kr"
AJAX_URL = f"{BASE_URL}/cs/CsBltnWrtListAjax.do"
GUIDE_URL = f"{BASE_URL}/cs/CsBltnWrtGuide.do"
DOWN_URL = f"{BASE_URL}/cs/CsDownAtchfile.do"

OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "efamily_customer_center.json"
FORM_CACHE_DIR = OUTPUT_DIR / "form_templates"
FORM_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# scourt_crawler output mirror paths
MIRROR_DIRS = [
    Path(__file__).parent / "scourt_crawler" / "output",
    Path("C:/Users/rawfu/.gemini/antigravity-ide/scratch/scourt-crawler/output")
]

def clean_html_text(raw_html: str) -> str:
    """HTML 태그 제거 및 공백 정제, 특수문자 디코딩"""
    if not raw_html:
        return ""
    unescaped = html.unescape(raw_html)
    soup = BeautifulSoup(unescaped, "html.parser")
    # Replace breaks and paragraph tags with newlines
    for br in soup.find_all(["br", "p", "div", "li", "tr"]):
        br.append("\n")
    text = soup.get_text()
    # Normalize multiple newlines and spaces
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.split("\n")]
    clean_lines = [l for l in lines if l]
    return "\n".join(clean_lines)

def fetch_all_faq(client: httpx.Client) -> List[Dict[str, Any]]:
    """자주 하는 질문 (FAQ) 112건 전수 수집"""
    print("[eFamily Crawler] Fetching FAQ (bltnbordId=0000003)...")
    page = 1
    total_records = 0
    faq_items = []
    
    while True:
        try:
            res = client.post(
                AJAX_URL,
                data={
                    "bltnbordId": "0000003",
                    "inqType": "03",
                    "inqTrgt": "02",
                    "srvcFg": "00",
                    "pageIndex": str(page)
                },
                timeout=20.0
            )
            if res.status_code != 200:
                print(f"  [FAQ] Page {page} failed with status {res.status_code}")
                break
                
            data = res.json()
            if page == 1:
                total_records = data.get("paginationInfo", {}).get("totalRecordCount", 0)
                print(f"  [FAQ] Total records discovered: {total_records}")
                
            records = data.get("resultList", [])
            if not records:
                break
                
            for rec in records:
                bltn_id = rec.get("bltnId", "")
                srvc_nm = rec.get("srvcNm", "").strip()
                title = html.unescape(rec.get("bltnTitle", "")).strip()
                raw_cts = rec.get("bltnCts", "")
                clean_cts = clean_html_text(raw_cts)
                rgt_dtm = rec.get("rgtDtm", "")
                
                # Format registration date if present
                rgt_date_str = f"{rgt_dtm[:4]}-{rgt_dtm[4:6]}-{rgt_dtm[6:8]}" if len(rgt_dtm) >= 8 else ""
                category_prefix = f"[{srvc_nm}] " if srvc_nm else ""
                full_title = f"{category_prefix}{title}"
                
                content_parts = [
                    f"【질문】 {full_title}",
                    f"【분류】 {srvc_nm or '전자가족관계등록 일반'} | 등록일자: {rgt_date_str}",
                    "【답변 안내】",
                    clean_cts,
                    f"\n출처: 대법원 전자가족관계등록시스템 고객센터 자주하는질문 (문서ID: {bltn_id})"
                ]
                
                faq_doc = {
                    "id": f"EFAMILY-FAQ-{bltn_id}",
                    "category": "전자가족관계등록 FAQ",
                    "title": full_title,
                    "source": "대법원 전자가족관계등록시스템 고객센터 FAQ",
                    "content": "\n".join(content_parts),
                    "service_name": srvc_nm,
                    "question": title,
                    "answer": clean_cts,
                    "registered_date": rgt_date_str,
                    "url": f"{BASE_URL}/cs/CsBltnWrtList.do?bltnbordId=0000003"
                }
                faq_items.append(faq_doc)
                
            page += 1
            if len(faq_items) >= total_records or page > 25:
                break
            time.sleep(0.3)
        except Exception as e:
            print(f"  [FAQ] Error on page {page}: {e}")
            break
            
    print(f"  [FAQ] Successfully collected {len(faq_items)} FAQ items.")
    return faq_items

def fetch_all_guides(client: httpx.Client) -> List[Dict[str, Any]]:
    """사이트 이용안내 가이드 3종 수집"""
    print("[eFamily Crawler] Fetching Site Guides (0000009)...")
    guides_meta = [
        ("0000009001", "인터넷 증명서 발급 방법 안내", "가족관계등록부·제적부 인터넷 열람 및 발급 4단계 절차"),
        ("0000009002", "인터넷 신고 방법 안내", "출생·개명 등 대법원 인터넷 가족관계등록신고 5단계 절차"),
        ("0000009003", "아포스티유 안내", "외국공문서 인증 요구 폐지 협약(아포스티유) 개요 및 전자가족관계등록부 연계 발급")
    ]
    
    guide_items = []
    for guide_cd, title, summary in guides_meta:
        url = f"{GUIDE_URL}?bltnbordId=0000009&guideCd={guide_cd}&guideYn=Y"
        try:
            res = client.get(url, timeout=20.0)
            if res.status_code != 200:
                print(f"  [Guide] {title} failed ({res.status_code})")
                continue
                
            match = re.search(r'\$\("#contentSpan"\)\.html\((.*?)\);\s*\}\);', res.text, re.DOTALL)
            if match:
                raw_str = match.group(1).strip()
                if raw_str.startswith('"') and raw_str.endswith('"'):
                    inner_html = json.loads(raw_str)
                else:
                    inner_html = re.sub(r'^"|"$', '', raw_str).replace(r'\"', '"').replace(r'\/', '/')
                clean_text = clean_html_text(inner_html)
            else:
                clean_text = clean_html_text(res.text)
                
            content = f"【시스템 이용 가이드】 {title}\n【요약】 {summary}\n\n{clean_text}\n\n출처: 대법원 전자가족관계등록시스템 사이트이용안내 ({url})"
            
            guide_items.append({
                "id": f"EFAMILY-GUIDE-{guide_cd}",
                "category": "전자가족관계등록 시스템안내",
                "title": title,
                "source": "대법원 전자가족관계등록시스템 사이트이용안내",
                "content": content,
                "guide_code": guide_cd,
                "summary": summary,
                "url": url
            })
            print(f"  [Guide] Collected: {title} ({len(clean_text)} chars)")
            time.sleep(0.3)
        except Exception as e:
            print(f"  [Guide] Error fetching {title}: {e}")
            
    return guide_items

def download_form_attachment(client: httpx.Client, bltn_id: str, atch_id: str, atch_nm: str) -> Optional[Path]:
    """신청서 첨부파일 다운로드 및 로컬 캐싱"""
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', atch_nm)
    cached_path = FORM_CACHE_DIR / safe_name
    
    if cached_path.exists() and cached_path.stat().st_size > 100:
        return cached_path

    # Try extracting from form_templates.zip if available
    zip_path = FORM_CACHE_DIR.parent / "form_templates.zip"
    if zip_path.exists():
        try:
            import zipfile
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                for target_nm in (safe_name, atch_nm):
                    if target_nm in names:
                        FORM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                        zf.extract(target_nm, FORM_CACHE_DIR)
                        extracted = FORM_CACHE_DIR / target_nm
                        if extracted.exists():
                            return extracted
        except Exception as e:
            pass
        
    try:

        res = client.post(
            DOWN_URL,
            data={
                "bltnbordId": "0000005",
                "bltnId": bltn_id,
                "atchfileId": atch_id,
                "atchfileNm": atch_nm
            },
            timeout=25.0
        )
        if res.status_code == 200 and len(res.content) > 100:
            with open(cached_path, "wb") as f:
                f.write(res.content)
            return cached_path
        else:
            print(f"  [Form Down] Failed ({res.status_code}) for {atch_nm}")
    except Exception as e:
        print(f"  [Form Down] Error downloading {atch_nm}: {e}")
    return None

def extract_form_document_text(file_path: Path) -> Dict[str, Any]:
    """PDF 또는 HWP 서식 파일 본문 및 작성방법 추출"""
    ext = file_path.suffix.lower()
    res = {
        "page_count": 0,
        "full_text": "",
        "front_fields": "",
        "instructions": ""
    }
    
    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            pages = reader.pages
            res["page_count"] = len(pages)
            page_texts = []
            for p in pages:
                t = p.extract_text() or ""
                t_clean = clean_html_text(t)
                page_texts.append(t_clean)
                
            res["full_text"] = "\n\n".join(page_texts)
            if len(page_texts) >= 1:
                res["front_fields"] = page_texts[0]
            if len(page_texts) >= 2:
                res["instructions"] = "\n\n".join(page_texts[1:])
        except Exception as e:
            print(f"  [Form Extract] PDF extraction error for {file_path.name}: {e}")
            
    elif ext == ".hwp":
        try:
            import olefile
            if olefile.isOleFile(str(file_path)):
                ole = olefile.OleFileIO(str(file_path))
                if ole.exists("PrvText"):
                    raw = ole.openstream("PrvText").read()
                    text = raw.decode("utf-16le", errors="ignore")
                    text_clean = clean_html_text(text)
                    res["full_text"] = text_clean
                    res["front_fields"] = text_clean
                    res["page_count"] = 1
        except Exception as e:
            print(f"  [Form Extract] HWP extraction error for {file_path.name}: {e}")
            
    return res

def fetch_all_forms(client: httpx.Client) -> List[Dict[str, Any]]:
    """신청서 양식 다운로드 46건 전수 수집 및 첨부문서 기재요령 크롤링"""
    print("[eFamily Crawler] Fetching Application Forms and Attachments (bltnbordId=0000005)...")
    page = 1
    total_records = 0
    form_items = []
    
    while True:
        try:
            res = client.post(
                AJAX_URL,
                data={
                    "bltnbordId": "0000005",
                    "pageIndex": str(page)
                },
                timeout=20.0
            )
            if res.status_code != 200:
                print(f"  [Forms] Page {page} failed with status {res.status_code}")
                break
                
            data = res.json()
            if page == 1:
                total_records = data.get("paginationInfo", {}).get("totalRecordCount", 0)
                print(f"  [Forms] Total records discovered: {total_records}")
                
            records = data.get("resultList", [])
            if not records:
                break
                
            for rec in records:
                bltn_id = rec.get("bltnId", "")
                title = html.unescape(rec.get("bltnTitle", "")).strip()
                raw_cts = rec.get("bltnCts", "")
                clean_cts = clean_html_text(raw_cts)
                rgt_dtm = rec.get("rgtDtm", "")
                rgt_date_str = f"{rgt_dtm[:4]}-{rgt_dtm[4:6]}-{rgt_dtm[6:8]}" if len(rgt_dtm) >= 8 else ""
                
                atch_list = rec.get("atchfileList", [])
                file_names = []
                for atch in atch_list:
                    fn = atch.get("atchfileNm")
                    if fn:
                        file_names.append(fn)
                        
                files_str = "\n".join([f"- 첨부 서식: {fn}" for fn in file_names]) if file_names else "- 별도 첨부파일 없음 (안내문)"
                
                # Best attachment selection: prefer .pdf, then .hwp
                best_atch = None
                for atch in atch_list:
                    fn = atch.get("atchfileNm", "").lower()
                    if fn.endswith(".pdf"):
                        best_atch = atch
                        break
                if not best_atch:
                    for atch in atch_list:
                        fn = atch.get("atchfileNm", "").lower()
                        if fn.endswith(".hwp"):
                            best_atch = atch
                            break

                extracted = {"full_text": "", "front_fields": "", "instructions": ""}
                extracted_file_name = ""
                if best_atch and best_atch.get("atchfileId") and best_atch.get("atchfileNm"):
                    extracted_file_name = best_atch["atchfileNm"]
                    down_path = download_form_attachment(
                        client, bltn_id, best_atch["atchfileId"], best_atch["atchfileNm"]
                    )
                    if down_path:
                        extracted = extract_form_document_text(down_path)

                content_parts = [
                    f"【신청서식】 {title}",
                    f"【등록일자】 {rgt_date_str}",
                    "【제공 첨부파일 목록】",
                    files_str,
                    "\n【서식 개요 및 이용 안내】",
                    clean_cts if clean_cts else "해당 서식은 대한민국 법원 가족관계등록예규 및 규칙에 따른 표준 법정 서식입니다. 다운로드하여 신고서 작성 및 관서 제출용으로 활용하십시오.",
                ]
                
                if extracted.get("front_fields"):
                    content_parts.append("\n【서식 전면 주요 기재 항목】")
                    content_parts.append(extracted["front_fields"][:1500])
                    
                if extracted.get("instructions"):
                    content_parts.append("\n【서식 뒷면 상세 작성 방법 및 심사 안내】")
                    content_parts.append(extracted["instructions"][:2500])
                elif extracted.get("full_text") and not extracted.get("front_fields"):
                    content_parts.append("\n【서식 본문 전문 및 작성 안내】")
                    content_parts.append(extracted["full_text"][:2500])
                    
                content_parts.extend([
                    "\n【공식 다운로드 안내】",
                    f"대법원 전자가족관계등록시스템 고객센터 > 신청서 양식 다운로드 게시판에서 공식 파일을 직접 내려받으실 수 있습니다.",
                    f"공식 다운로드 게시판: {BASE_URL}/cs/CsBltnWrtList.do?bltnbordId=0000005"
                ])
                
                form_doc = {
                    "id": f"EFAMILY-FORM-{bltn_id}",
                    "category": "가족관계등록 신청서식",
                    "title": title,
                    "source": "대법원 전자가족관계등록시스템 신청서 양식 다운로드",
                    "content": "\n".join(content_parts),
                    "file_names": file_names,
                    "extracted_source_file": extracted_file_name,
                    "extracted_text_length": len(extracted.get("full_text", "")),
                    "has_attachment_text": bool(extracted.get("full_text")),
                    "registered_date": rgt_date_str,
                    "url": f"{BASE_URL}/cs/CsBltnWrtList.do?bltnbordId=0000005"
                }
                form_items.append(form_doc)
                
            page += 1
            if len(form_items) >= total_records or page > 15:
                break
            time.sleep(0.2)
        except Exception as e:
            print(f"  [Forms] Error on page {page}: {e}")
            break
            
    print(f"  [Forms] Successfully collected {len(form_items)} Form items (with attachment texts).")
    return form_items

def run_efamily_crawler() -> Dict[str, Any]:
    """고객센터 전체 크롤링 및 로컬 JSON 저장"""
    start_time = time.time()
    print("=================================================================")
    print(" [eFamily Customer Center Knowledge Crawler Started]")
    print(f" Target: {BASE_URL}")
    print("=================================================================")
    
    with httpx.Client(verify=False, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}) as client:
        faqs = fetch_all_faq(client)
        guides = fetch_all_guides(client)
        forms = fetch_all_forms(client)
        
    all_docs = faqs + guides + forms
    elapsed = round(time.time() - start_time, 2)
    
    result = {
        "metadata": {
            "source": "대법원 전자가족관계등록시스템 고객센터",
            "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_count": len(all_docs),
            "faq_count": len(faqs),
            "guide_count": len(guides),
            "form_count": len(forms),
            "elapsed_seconds": elapsed
        },
        "documents": all_docs
    }
    
    # Save main output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[eFamily Crawler] Saved {len(all_docs)} documents to {OUTPUT_FILE}")
    
    # Mirror outputs to scourt_crawler directories
    for m_dir in MIRROR_DIRS:
        try:
            m_dir.mkdir(parents=True, exist_ok=True)
            m_path = m_dir / "efamily_customer_center.json"
            with open(m_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[eFamily Crawler] Mirrored to {m_path}")
        except Exception as me:
            print(f"[eFamily Crawler] Mirror error to {m_dir}: {me}")
            
    print(f"=================================================================")
    print(f" [eFamily Crawler Completed in {elapsed}s] Total {len(all_docs)} items collected.")
    print("=================================================================")
    return result

if __name__ == "__main__":
    run_efamily_crawler()
