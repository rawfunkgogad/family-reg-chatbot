import asyncio
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional

KST = timezone(timedelta(hours=9))

def get_seconds_until_next_midnight_kst() -> float:
    """한국표준시(KST, UTC+9) 기준 다음 자정(00:00:00)까지 남은 초 계산"""
    now = datetime.now(KST)
    tomorrow = now.date() + timedelta(days=1)
    midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, tzinfo=KST)
    diff = (midnight - now).total_seconds()
    return max(1.0, diff)

async def daily_midnight_sync_task():
    """
    매일 00:00 KST에 자동으로 대법원 예규·선례 및 법령체계도 수집기를 실행하여
    지식 코퍼스를 현행화하는 백그라운드 상시 워커 태스크
    """
    from .corpus_sync_manager import corpus_sync_manager
    print("[Scheduler] Daily midnight (00:00 KST) corpus sync scheduler initialized.")

    while True:
        try:
            wait_sec = get_seconds_until_next_midnight_kst()
            next_midnight_str = (datetime.now(KST) + timedelta(seconds=wait_sec)).strftime("%Y-%m-%d %H:%M:%S KST")
            print(f"[Scheduler] Next automatic sync scheduled at: {next_midnight_str} (in {wait_sec/3600:.2f} hours)")

            # 자정까지 대기
            await asyncio.sleep(wait_sec)

            print(f"[Scheduler] Midnight reached! [{datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')}] Starting automatic knowledge corpus sync...")
            result = await corpus_sync_manager.sync(run_crawlers=True)
            print(f"[Scheduler] Midnight sync completed: {result.get('message')}")

            # 연달아 즉시 재실행되는 것을 방지하기 위해 10초 대기
            await asyncio.sleep(10)

        except asyncio.CancelledError:
            print("[Scheduler] Daily midnight sync scheduler task cancelled.")
            break
        except Exception as e:
            print(f"[Scheduler] Error during scheduled sync: {e}")
            traceback.print_exc()
            # 오류 발생 시 10분 대기 후 루프 지속
            await asyncio.sleep(600)

_scheduler_task: Optional[asyncio.Task] = None

def start_daily_midnight_scheduler():
    """스케줄러 백그라운드 태스크 시작"""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(daily_midnight_sync_task())
        print("[Scheduler] Started daily midnight sync background task.")
    return _scheduler_task
