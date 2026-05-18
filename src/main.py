"""
AdBot 메인 오케스트레이터
실행 모드:
  python main.py              → 트렌드 수집 → 글 생성 → 즉시 발행 (1회 실행)
  python main.py --draft      → 초안 저장 (발행 안 함, 검토 후 발행)
  python main.py --count 3    → 오늘 3개 글 생성
  python main.py --keyword "ETF 투자" → 특정 키워드로 생성
  python main.py --daemon     → 스케줄러 데몬 모드 (매일 자동 실행)
"""

import argparse
import time
import schedule
import os
from datetime import datetime
from dotenv import load_dotenv

from trend_collector import TrendCollector
from content_generator import ContentGenerator
from blogger_uploader import BloggerUploader

load_dotenv()

# 하루 생성 글 수 (애드센스 승인 전: 1~3개, 승인 후: 3~5개)
DEFAULT_POSTS_PER_DAY = int(os.getenv("POSTS_PER_DAY", "3"))
PUBLISH_DRAFT = os.getenv("PUBLISH_AS_DRAFT", "false").lower() == "true"
POST_DELAY_SECONDS = int(os.getenv("POST_DELAY_SECONDS", "15"))


def run_pipeline(
    count: int = DEFAULT_POSTS_PER_DAY,
    draft: bool = PUBLISH_DRAFT,
    specific_keyword: str = None,
):
    """
    전체 파이프라인: 트렌드 수집 → 콘텐츠 생성 → 업로드
    """
    print(f"\n{'='*60}")
    print(f"  AdBot 실행 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  목표 글 수: {count} | 모드: {'초안' if draft else '즉시 발행'}")
    print(f"{'='*60}\n")

    # ── 1단계: 키워드 수집 ──────────────────────
    print("[1/3] 트렌드 키워드 수집 중...")

    if specific_keyword:
        keywords = [{"keyword": specific_keyword, "score": 100, "sources": ["manual"]}]
    else:
        collector = TrendCollector()
        keywords = collector.get_top_keywords(top_n=count * 2)  # 여유분 수집
        keywords = keywords[:count]

    if not keywords:
        print("수집된 키워드 없음 - 종료")
        return

    print(f"  키워드: {[k['keyword'] for k in keywords]}\n")

    # ── 2단계: 콘텐츠 생성 ──────────────────────
    print("[2/3] AI 콘텐츠 생성 중...")
    generator = ContentGenerator()
    posts = generator.generate_batch(keywords)

    if not posts:
        print("생성된 포스트 없음 - 종료")
        return

    print(f"  {len(posts)}개 포스트 생성 완료\n")

    # ── 3단계: Blogger 업로드 ──────────────────
    print("[3/3] Blogger 업로드 중...")
    uploader = BloggerUploader()
    results = uploader.upload_batch(posts, draft=draft, delay=POST_DELAY_SECONDS)

    # ── 완료 요약 ──────────────────────────────
    stats = uploader.get_upload_stats()
    print(f"\n{'='*60}")
    print(f"  완료! {len(results)}개 업로드 성공")
    print(f"  누적 발행: {stats['published']}개 | 초안: {stats['draft']}개")
    print(f"{'='*60}\n")


def run_scheduled():
    """스케줄러 데몬 - 매일 오전 9시, 오후 3시 실행"""
    print("AdBot 스케줄러 시작...")
    print("  실행 시간: 매일 09:00, 15:00 (KST)")

    schedule.every().day.at("09:00").do(run_pipeline)
    schedule.every().day.at("15:00").do(run_pipeline)

    # 시작 즉시 1회 실행
    run_pipeline()

    while True:
        schedule.run_pending()
        time.sleep(60)


def main():
    parser = argparse.ArgumentParser(description="AdBot - 애드센스 자동 블로그 봇")
    parser.add_argument("--draft", action="store_true", help="초안으로 저장 (발행 안 함)")
    parser.add_argument("--count", type=int, default=DEFAULT_POSTS_PER_DAY, help="생성할 글 수")
    parser.add_argument("--keyword", type=str, default=None, help="특정 키워드 지정")
    parser.add_argument("--daemon", action="store_true", help="스케줄러 데몬 모드")
    parser.add_argument("--stats", action="store_true", help="업로드 통계 보기")
    args = parser.parse_args()

    if args.stats:
        uploader = BloggerUploader()
        stats = uploader.get_upload_stats()
        print(f"업로드 통계:")
        print(f"  전체: {stats['total']}개")
        print(f"  발행: {stats['published']}개")
        print(f"  초안: {stats['draft']}개")
        print(f"  마지막 업로드: {stats['last_upload']}")
        return

    if args.daemon:
        run_scheduled()
    else:
        run_pipeline(
            count=args.count,
            draft=args.draft,
            specific_keyword=args.keyword,
        )


if __name__ == "__main__":
    main()
