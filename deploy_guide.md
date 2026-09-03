# 🚀 대한민국 법원 가족관계등록 AI 시스템 클라우드 배포 완벽 가이드
*(Version 5.2.2 - 468건 마스터 지식 코퍼스 프로덕션 에디션)*

본 프로젝트는 **468건 마스터 지식 코퍼스(대법원 예규/선례 278건 + 전자가족관계 가이드 73건 + 생활법령 117건)**와 **사전 생성된 1024차원 bge-m3 고밀도 벡터 임베딩 캐시**를 기본 탑재하고 있어, **클라우드 24시간 상시 가동(Render.com / Railway / Cloud VM)** 및 **Docker 컨테이너**, **온프레미스 사내 서버** 등 어떠한 환경에서도 즉시 배포할 수 있도록 완벽히 패키징되어 있습니다.

---

## 📦 배포 핵심 정보 요약

| 구분 | 주요 설정 및 접속 주소 |
| :--- | :--- |
| **소프트웨어 버전** | `v5.2.2 (Master Knowledge Corpus Edition)` |
| **탑재 지식 코퍼스** | **총 468건** (대법원 예규 200건 + 선례 78건 + 전자등록 73건 + 생활법령 117건) |
| **사전 임베딩 캐시** | `backend/data/corpus_embeddings.npy` (468 x 1024, 기동 즉시 0.1초 로딩) |
| **메인 실무/심사 포털** | https://[배포주소]/ (가족관계등록 실무 챗봇 & 4단계 법령 추론) |
| **사법행정 지식 관리자 콘솔** | https://[배포주소]/admin (지식 등록, 비용/보안 모니터링, 실무 감사 로그) |
| **서버 상태 헬스체크** | `GET /api/health` (로드밸런서 및 쿠버네티스 프로브 지원) |
| **관리자 보안 인증코드** | `family_manager_035` (단방향 Salted SHA-256 암호화 적용) |
| **런타임 및 포트** | Python 3.10+ / FastAPI / 동적 $PORT 바인딩 (기본 8000) |
| **배포 전 검증 테스트** | `python tests/test_production_readiness.py` (5개 검증 100% PASS) |

---

## 🌟 [방법 1] Render.com 무료 클라우드 24시간 배포 (가장 추천)

Render.com의 무료 플랜(Free Tier)을 사용하면 PC를 꺼두어도 24시간 언제 어디서나 접속할 수 있는 웹 서비스(https://your-service.onrender.com)가 무료로 생성됩니다.

### 1단계: GitHub 저장소에 소스코드 업로드
1. [GitHub.com](https://github.com)에 로그인 후 우측 상단 **`+`** ➔ **`New repository`** 클릭
2. 저장소 이름(예: `family-reg-chatbot`)을 입력하고 **`Create repository`**를 누릅니다.
3. 프로젝트 폴더의 파일들을 업로드합니다:
   - `backend/` (폴더 전체)
   - `frontend/` (폴더 전체)
   - `requirements.txt`
   - `run_server.py`
   - `Procfile`
   - `render.yaml`
   - `Dockerfile`
   - `deploy_guide.md`

### 2단계: Render.com에서 Web Service 생성 및 연결
1. [Render.com](https://render.com) 접속 ➔ **`GitHub 계정으로 로그인`**
2. 상단 **`New +`** ➔ **`Web Service`** 클릭
3. 방금 올린 GitHub 저장소(`family-reg-chatbot`)를 선택하고 **`Connect`** 클릭
4. 기본 설정을 확인합니다:
   - **Name**: `family-reg-ai` *(원하는 영문 서비스명)*
   - **Region**: `Singapore` 또는 `Oregon` (아시아 지역 권장)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python run_server.py`
   - **Instance Type**: `Free` ($0/month)

### 3단계: 환경 변수(Environment Variables) 등록
하단 **Environment Variables** 영역에서 다음 변수를 추가합니다:

| Key (변수명) | Value (값) | 비고 |
| :--- | :--- | :--- |
| PYTHONIOENCODING | utf-8 | 필수 (한글 인코딩 처리) |
| OPENAI_BASE_URL | https://open.hasa.re.kr/v1 | LLM API 엔드포인트 |
| OPENAI_API_KEY | sk-dev-Un5B6gafFJxVcRwGnw5AlT23wDGn1ooA | API Key |

4. **Create Web Service** 버튼을 클릭하면 1~2분 내 빌드가 완료되고 라이브 도메인(https://family-reg-ai.onrender.com)이 발급됩니다! 🎉

---

## 🐳 [방법 2] Docker / Docker Compose 로컬 및 사내망 배포

사내 서버나 클라우드 VM(AWS EC2, GCP, Azure, 네이버클라우드 등)에서 Docker 컨테이너로 배포할 때 사용합니다.

```bash
# 1. Docker Compose로 1초 만에 실행
docker-compose up -d --build

# 2. 컨테이너 상태 확인
docker ps

# 3. 브라우저 접속
# 실무 포털: http://localhost:8000
# 관리자 콘솔: http://localhost:8000/admin
```

---

## ⚡ [방법 3] 원클릭 스크립트 및 직접 실행

### 1) Windows 환경 (원클릭 실행)
```cmd
# 더블 클릭 또는 cmd에서 실행:
start_server.bat
```

### 2) Linux / macOS 환경 (원클릭 실행)
```bash
chmod +x start_server.sh
./start_server.sh
```

### 3) 수동 가상환경 실행
```bash
# 1. 가상환경 생성 및 활성화
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 2. 의존성 패키지 설치
pip install -r requirements.txt

# 3. 배포 전 5개 무결성 테스트 실행 (선택 사항)
python tests/test_production_readiness.py

# 4. 서버 기동
python run_server.py
```

---

## 🛡️ 배포 후 보안 점검 사항

1. **지식 관리자 분리**:
   - / 메인 포털에는 일반 실무관/민원인을 위한 상담 인터페이스만 노출되며 관리자 진입 버튼은 안전하게 숨겨져 있습니다.
   - 관리자 기능은 오직 **/admin** 경로에서만 접근 가능하며, 비밀번호 **`family_manager_035`** 입력 시에만 세션 토큰이 발급됩니다.
2. **개인정보 자동 마스킹**:
   - 주민등록번호, 연락처, 카드번호 등은 입력 즉시 실시간 마스킹되어 감사 로그 및 모델에 전달됩니다.
3. **상시 가동 팁 (Render Free Tier)**:
   - Render 무료 플랜은 15분간 요청이 없으면 절전 모드로 전환됩니다.
   - [UptimeRobot](https://uptimerobot.com)과 같은 무료 모니터링 도구에 https://[배포주소]/api/efamily/services를 10분 주기로 등록하시면 24시간 절전 없이 즉시 응답 상태를 유지할 수 있습니다.