@echo off
chcp 65001 >nul
echo ===================================================================
echo  [대한민국 법원 가족관계등록 실무 AI 어시스턴트 프로덕션 서버]
echo  - 지식 코퍼스: 468건 마스터 에디션 (대법원 예규/선례 278건 + 포털 가이드 190건)
echo  - 임베딩 모델: bge-m3 (1024차원 사전 임베딩 캐시 탑재)
echo ===================================================================

set HOST=0.0.0.0
set PORT=8000
set PYTHONIOENCODING=utf-8

if exist "venv\Scripts\activate.bat" (
    echo [Info] 가상환경(venv)을 활성화합니다...
    call venv\Scripts\activate.bat
)

echo [Info] 서버 시작 중... (접속 주소: http://localhost:8000)
python run_server.py
pause
