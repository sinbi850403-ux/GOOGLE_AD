"""
Google Indexing API 일괄 색인 요청 모듈
- upload_log.json의 모든 URL을 Google에 색인 요청
- 새 글 업로드 시 자동 호출 (main.py 연동)

사전 설정 (1회):
  1. Google Cloud Console → Indexing API 활성화
  2. IAM → 서비스 계정 생성 → JSON 키 → config/service_account.json 저장
  3. Search Console → 설정 → 사용자 및 권한 → 서비스 계정 이메일 → 소유자 추가
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

SERVICE_ACCOUNT_FILE = Path(__file__).parent.parent / "config" / "service_account.json"
LOG_PATH             = Path(__file__).parent.parent / "logs" / "upload_log.json"
INDEX_LOG_PATH       = Path(__file__).parent.parent / "logs" / "index_log.json"

SCOPES = ["https://www.googleapis.com/auth/indexing"]
RATE_LIMIT_DELAY = 0.5   # 초 (분당 최대 600건 제한)


# ── 설정 확인 ───────────────────────────────────────────────────

def is_configured() -> bool:
    return SERVICE_ACCOUNT_FILE.exists()


# ── URL 수집 ────────────────────────────────────────────────────

def get_urls_from_log(only_new: bool = True) -> list[str]:
    """
    upload_log.json에서 URL 수집.
    only_new=True: 이미 색인 요청한 URL 제외
    """
    if not LOG_PATH.exists():
        return []

    with open(LOG_PATH, encoding="utf-8") as f:
        logs = json.load(f)

    # URL이 있고 draft/published 상태인 것만
    all_urls = list({
        e["url"] for e in logs
        if e.get("url") and e.get("status") in ("published", "draft")
    })

    if not only_new:
        return all_urls

    # 이미 요청한 URL 제외
    submitted = _load_index_log()
    return [u for u in all_urls if u not in submitted]


def _load_index_log() -> set:
    if not INDEX_LOG_PATH.exists():
        return set()
    try:
        with open(INDEX_LOG_PATH, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_index_log(urls: list[str]):
    existing = _load_index_log()
    merged   = list(existing | set(urls))
    INDEX_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)


# ── Indexing API 제출 ───────────────────────────────────────────

def submit_urls(urls: list[str], verbose: bool = True) -> dict:
    """
    URL 목록을 Google Indexing API에 제출.
    Returns: {"success": [...], "failed": [...]}
    """
    if not urls:
        if verbose:
            print("  [색인] 제출할 새 URL 없음")
        return {"success": [], "failed": []}

    if not is_configured():
        print("  [색인] config/service_account.json 없음 — 설정 방법: python src/indexing_submitter.py --setup")
        return {"success": [], "failed": urls}

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("  [색인] google-auth 패키지 필요: pip install google-auth google-api-python-client")
        return {"success": [], "failed": urls}

    creds   = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
    )
    service = build("indexing", "v3", credentials=creds)

    success_urls = []
    failed_urls  = []

    for i, url in enumerate(urls, 1):
        try:
            service.urlNotifications().publish(
                body={"url": url, "type": "URL_UPDATED"}
            ).execute()
            success_urls.append(url)
            if verbose:
                print(f"  [색인 {i}/{len(urls)}] OK: {url[:70]}")
        except Exception as e:
            failed_urls.append(url)
            if verbose:
                print(f"  [색인 {i}/{len(urls)}] FAIL: {e}")

        if i < len(urls):
            time.sleep(RATE_LIMIT_DELAY)

    # 성공한 URL만 로그에 기록 (다음 실행 시 중복 방지)
    if success_urls:
        _save_index_log(success_urls)

    if verbose:
        print(f"\n  [색인] 완료: {len(success_urls)}개 성공 / {len(failed_urls)}개 실패")

    return {"success": success_urls, "failed": failed_urls}


def submit_new_posts(post_urls: list[str]):
    """
    새로 업로드된 글 URL만 색인 요청 (main.py에서 호출)
    """
    # 이미 요청한 URL 제외
    submitted = _load_index_log()
    new_urls  = [u for u in post_urls if u and u not in submitted]

    if new_urls:
        print(f"\n[색인 요청] 새 글 {len(new_urls)}개 색인 요청 중...")
        submit_urls(new_urls)
    else:
        print("\n[색인 요청] 새 URL 없음 (이미 요청 완료)")


# ── CLI ─────────────────────────────────────────────────────────

def print_setup_guide():
    print("""
=== Google Indexing API 설정 가이드 (1회) ===

[ Step 1 ] Indexing API 활성화
  → https://console.cloud.google.com/apis/library/indexing.googleapis.com
  → '사용 설정' 클릭

[ Step 2 ] 서비스 계정 생성
  → https://console.cloud.google.com/iam-admin/serviceaccounts
  → '서비스 계정 만들기' → 이름 입력 (예: adbot-indexing)
  → '키 만들기' → JSON 선택 → 다운로드

[ Step 3 ] 키 파일 저장
  → 다운로드한 JSON 파일을 아래 경로에 저장:
     config/service_account.json

[ Step 4 ] Search Console 소유자 추가 (중요!)
  → https://search.google.com/search-console
  → 설정 → 사용자 및 권한 → '사용자 추가'
  → 서비스 계정 이메일 입력 (JSON 파일 안의 client_email 값)
  → 권한: 소유자

[ Step 5 ] 실행
  → python src/indexing_submitter.py

=============================================
""")


if __name__ == "__main__":
    import sys

    if "--setup" in sys.argv:
        print_setup_guide()
    elif "--all" in sys.argv:
        # 전체 URL (기존 요청 포함)
        urls = get_urls_from_log(only_new=False)
        print(f"전체 URL {len(urls)}개 색인 요청")
        submit_urls(urls)
    else:
        # 새 URL만
        if not is_configured():
            print_setup_guide()
        else:
            urls = get_urls_from_log(only_new=True)
            print(f"미제출 URL {len(urls)}개 색인 요청")
            submit_urls(urls)
