"""
트렌드 키워드 수집 모듈
Google Trends + 네이버 DataLab 에서 실시간 인기 키워드 수집
"""

import os
import time
import random
import requests
from datetime import datetime, timedelta
from pytrends.request import TrendReq
from dotenv import load_dotenv

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")


class TrendCollector:
    def __init__(self):
        self.pytrends = TrendReq(hl="ko-KR", tz=540, timeout=(10, 30))

    # ──────────────────────────────────────────
    # Google Trends
    # ──────────────────────────────────────────

    def get_google_realtime_trends(self, limit: int = 20) -> list[dict]:
        """구글 실시간 검색어 트렌드 수집"""
        try:
            trending = self.pytrends.trending_searches(pn="south_korea")
            keywords = trending[0].tolist()[:limit]
            return [{"keyword": kw, "source": "google_realtime", "score": limit - i}
                    for i, kw in enumerate(keywords)]
        except Exception as e:
            print(f"[Google Trends 오류] {e}")
            return []

    def get_google_rising_trends(self, keyword: str) -> list[dict]:
        """특정 키워드 관련 급상승 검색어"""
        try:
            self.pytrends.build_payload([keyword], cat=0, timeframe="now 7-d", geo="KR")
            related = self.pytrends.related_queries()
            rising = related.get(keyword, {}).get("rising")
            if rising is None or rising.empty:
                return []
            return [{"keyword": row["query"], "source": "google_rising", "score": row["value"]}
                    for _, row in rising.head(10).iterrows()]
        except Exception as e:
            print(f"[Google Rising 오류] {e}")
            return []

    # ──────────────────────────────────────────
    # 네이버 DataLab
    # ──────────────────────────────────────────

    def get_naver_trends(self, keywords: list[str]) -> list[dict]:
        """네이버 DataLab 검색량 트렌드 수집"""
        if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
            print("[네이버] API 키 없음 - 건너뜀")
            return []

        url = "https://openapi.naver.com/v1/datalab/search"
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in keywords[:5]]

        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": "week",
            "keywordGroups": keyword_groups,
        }

        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(url, json=body, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for result in data.get("results", []):
                keyword = result["title"]
                # 최근 주 데이터 점수
                recent_ratio = result["data"][-1]["ratio"] if result["data"] else 0
                results.append({
                    "keyword": keyword,
                    "source": "naver_datalab",
                    "score": recent_ratio,
                })
            return sorted(results, key=lambda x: x["score"], reverse=True)
        except Exception as e:
            print(f"[네이버 DataLab 오류] {e}")
            return []

    # ──────────────────────────────────────────
    # 통합 수집 + 순위 산정
    # ──────────────────────────────────────────

    # 재테크 + AI 시드 키워드 (Google Trends 실패 시 fallback)
    SEED_KEYWORDS = [
        "ETF 투자 방법", "주식 배당주 추천", "ISA 계좌 개설", "연금저축 세액공제",
        "부동산 투자 초보", "비트코인 전망", "달러 환율 전망", "적금 금리 비교",
        "챗GPT 활용법", "AI 부업 방법", "클로드 사용법", "노코드 자동화",
        "AI 이미지 생성", "유튜브 AI 편집", "ChatGPT 프롬프트", "AI 수익화",
    ]

    def get_top_keywords(self, top_n: int = 5) -> list[dict]:
        """
        구글 + 네이버 트렌드를 합산해서 상위 키워드 반환
        반환 형태: [{"keyword": "...", "score": 100, "sources": [...]}]
        """
        print("트렌드 수집 시작...")
        google_trends = self.get_google_realtime_trends(limit=30)
        time.sleep(random.uniform(1.5, 3.0))  # rate limit 방지

        # Google Trends 실패 시 시드 키워드로 fallback
        if not google_trends:
            print("  Google Trends 실패 → 시드 키워드 사용")
            selected = random.sample(self.SEED_KEYWORDS, min(top_n, len(self.SEED_KEYWORDS)))
            return [{"keyword": kw, "score": 100 - i*5, "sources": ["seed"]} for i, kw in enumerate(selected)]

        # 구글 점수 정규화 (0~100)
        combined: dict[str, dict] = {}
        for item in google_trends:
            kw = item["keyword"]
            combined[kw] = {
                "keyword": kw,
                "score": item["score"] * 3,  # 구글 가중치 3배
                "sources": [item["source"]],
            }

        # 네이버 교차 검증
        google_kws = [item["keyword"] for item in google_trends[:15]]
        naver_results = self.get_naver_trends(google_kws[:5])
        for item in naver_results:
            kw = item["keyword"]
            if kw in combined:
                combined[kw]["score"] += item["score"]
                combined[kw]["sources"].append(item["source"])
            else:
                combined[kw] = {
                    "keyword": kw,
                    "score": item["score"],
                    "sources": [item["source"]],
                }

        # 정렬 후 상위 N개 반환
        ranked = sorted(combined.values(), key=lambda x: x["score"], reverse=True)
        top = ranked[:top_n]
        print(f"선택된 상위 키워드: {[k['keyword'] for k in top]}")
        return top


if __name__ == "__main__":
    collector = TrendCollector()
    keywords = collector.get_top_keywords(top_n=5)
    for kw in keywords:
        print(f"  [{kw['score']:.1f}] {kw['keyword']} ({', '.join(kw['sources'])})")
