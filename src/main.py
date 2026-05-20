"""
AdBot 메인 오케스트레이터
실행 모드:
  python main.py              -> 트렌드 수집 -> 글 생성 -> 즉시 발행 (1회 실행)
  python main.py --draft      -> 초안 저장 (발행 안 함, 검토 후 발행)
  python main.py --count 3    -> 오늘 3개 글 생성
  python main.py --keyword "ETF 투자" -> 특정 키워드로 생성
  python main.py --daemon     -> 스케줄러 데몬 모드 (매일 자동 실행)
"""

import argparse
import json
import time
import schedule
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from trend_collector import TrendCollector
from content_generator import ContentGenerator
from blogger_uploader import BloggerUploader
from topic_rotator import get_diverse_keywords, mark_used
from coupang_affiliate import build_product_section

load_dotenv()

LOG_PATH = Path("logs/upload_log.json")

DEFAULT_POSTS_PER_DAY = int(os.getenv("POSTS_PER_DAY", "3"))
PUBLISH_DRAFT         = os.getenv("PUBLISH_AS_DRAFT", "false").lower() == "true"
POST_DELAY_SECONDS    = int(os.getenv("POST_DELAY_SECONDS", "15"))


def load_recent_titles(limit: int = 50) -> list[str]:
    if not LOG_PATH.exists():
        return []
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            logs = json.load(f)
        return [e["title"] for e in logs[-limit:] if "title" in e]
    except (json.JSONDecodeError, KeyError):
        return []


def _deduplicate_keywords(keywords: list[dict], recent_titles: list[str]) -> list[dict]:
    if not recent_titles:
        return keywords
    recent_text = " ".join(recent_titles).lower()

    def overlap(kw: str) -> int:
        return sum(recent_text.count(tok) for tok in kw.lower().split() if len(tok) > 1)

    return sorted(keywords, key=lambda k: overlap(k["keyword"]))


def run_pipeline(
    count: int = DEFAULT_POSTS_PER_DAY,
    draft: bool = PUBLISH_DRAFT,
    specific_keyword: str = None,
):
    print(f"\n{'='*60}")
    print(f"  AdBot 실행: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  목표 {count}개 | {'초안' if draft else '즉시 발행'}")
    print(f"{'='*60}\n")

    # ── 1단계: 키워드 수집 ──────────────────────
    print("[1/3] 트렌드 키워드 수집 중...")
    if specific_keyword:
        keywords = [{"keyword": specific_keyword, "score": 100, "sources": ["manual"]}]
    else:
        trend_kws = TrendCollector().get_top_keywords(top_n=count * 3)
        keywords  = get_diverse_keywords(count, trend_kws)
        keywords  = _deduplicate_keywords(keywords, load_recent_titles(limit=100))

    if not keywords:
        print("수집된 키워드 없음 - 종료")
        return

    for kw in keywords:
        cat = kw.get("category", "")
        print(f"  [{cat}] {kw['keyword']}" if cat else f"  {kw['keyword']}")

    # ── 2단계: 콘텐츠 생성 ──────────────────────
    print("\n[2/3] AI 콘텐츠 생성 중...")
    recent_titles = load_recent_titles()
    if recent_titles:
        print(f"  기존 {len(recent_titles)}개 제목 참조 (중복 방지)")
    posts = ContentGenerator().generate_batch(keywords, recent_titles=recent_titles)

    if not posts:
        print("생성된 포스트 없음 - 종료")
        return

    # ── 2.5단계: 쿠팡파트너스 상품 삽입 ────────
    for post in posts:
        section = build_product_section(post["source_keyword"])
        if section:
            post["html_content"] = post["html_content"].rstrip() + "\n" + section
            print(f"  [쿠팡] '{post['source_keyword']}' 추천상품 삽입")

    print(f"\n  {len(posts)}개 포스트 생성 완료")

    # ── 3단계: Blogger 업로드 ──────────────────
    print("\n[3/3] Blogger 업로드 중...")
    uploader = BloggerUploader()
    results  = uploader.upload_batch(posts, draft=draft, delay=POST_DELAY_SECONDS)

    if not specific_keyword:
        mark_used([p["source_keyword"] for p in posts])

    stats = uploader.get_upload_stats()
    print(f"\n{'='*60}")
    print(f"  완료! {len(results)}개 업로드 성공")
    print(f"  누적 발행: {stats['published']}개 | 초안: {stats['draft']}개")
    print(f"{'='*60}\n")


def run_scheduled():
    print("AdBot 스케줄러 시작 (매일 09:00, 15:00)")
    schedule.every().day.at("09:00").do(run_pipeline)
    schedule.every().day.at("15:00").do(run_pipeline)
    run_pipeline()
    while True:
        schedule.run_pending()
        time.sleep(60)


def main():
    parser = argparse.ArgumentParser(description="AdBot")
    parser.add_argument("--draft",   action="store_true")
    parser.add_argument("--count",   type=int, default=DEFAULT_POSTS_PER_DAY)
    parser.add_argument("--keyword", type=str, default=None)
    parser.add_argument("--daemon",  action="store_true")
    parser.add_argument("--stats",   action="store_true")
    args = parser.parse_args()

    if args.stats:
        stats = BloggerUploader().get_upload_stats()
        print(f"전체: {stats['total']}  발행: {stats['published']}  초안: {stats['draft']}  마지막: {stats['last_upload']}")
        return

    if args.daemon:
        run_scheduled()
    else:
        run_pipeline(count=args.count, draft=args.draft, specific_keyword=args.keyword)


if __name__ == "__main__":
    main()
