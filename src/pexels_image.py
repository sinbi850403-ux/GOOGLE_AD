"""
Pexels API 이미지 검색
- 한국어 키워드 → 영어 검색어 변환
- 글 본문의 picsum.photos URL을 실제 관련 이미지로 교체
"""

import os
import re
import random
import requests
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PEXELS_SEARCH  = "https://api.pexels.com/v1/search"

# ── 한국어 카테고리 → 영어 검색어 매핑 ────────────────────────

_KW_MAP = {
    # 재테크/금융
    "주식": "stock market investment",
    "ETF": "ETF investment finance",
    "투자": "investment finance money",
    "코인": "cryptocurrency bitcoin",
    "비트코인": "bitcoin cryptocurrency",
    "부동산": "real estate property",
    "적금": "savings bank finance",
    "재테크": "personal finance money",
    "배당": "dividend investment",
    "환율": "currency exchange money",
    # AI/IT
    "AI": "artificial intelligence technology",
    "인공지능": "artificial intelligence robot",
    "ChatGPT": "AI chatbot computer",
    "챗GPT": "AI chatbot technology",
    "자동화": "automation technology computer",
    "노코드": "no code technology laptop",
    "파이썬": "python programming code",
    "앱": "mobile app smartphone",
    "유튜브": "youtube video content creator",
    "스마트폰": "smartphone mobile technology",
    # 건강/의료
    "다이어트": "diet healthy food weight loss",
    "운동": "exercise fitness workout",
    "건강": "health wellness lifestyle",
    "영양제": "supplements vitamins health",
    "수면": "sleep rest bedroom",
    "헬스": "gym fitness exercise",
    # 여행/라이프
    "여행": "travel vacation landscape",
    "맛집": "restaurant food delicious",
    "카페": "cafe coffee shop",
    "호텔": "hotel travel accommodation",
    "음식": "food cooking meal",
    "생생정보": "Korean food restaurant",
    "백종원": "Korean food restaurant cooking",
    # 교육/자기계발
    "영어": "english study education",
    "자격증": "certificate education study",
    "독서": "book reading study",
    "공부": "study education learning",
    "취업": "job career office",
    "블로그": "blog writing laptop",
}

_DEFAULT_QUERIES = [
    "business productivity office",
    "technology lifestyle modern",
    "korean lifestyle trend",
    "people working success",
    "finance money growth",
    "nature outdoor relaxing",
    "food cooking healthy",
    "education learning study",
]


def _to_english_query(keyword: str) -> str:
    """한국어 키워드를 Pexels 영어 검색어로 변환 (매칭 여러 개면 랜덤 선택)"""
    matched = [en for ko, en in _KW_MAP.items() if ko in keyword]
    if matched:
        return random.choice(matched)
    idx = hash(keyword) % len(_DEFAULT_QUERIES)
    return _DEFAULT_QUERIES[idx]


def fetch_images(keyword: str, count: int = 3) -> list[str]:
    """
    키워드 관련 Pexels 이미지 URL 목록 반환.
    API 키 없거나 실패 시 빈 리스트 반환.
    """
    if not PEXELS_API_KEY:
        return []

    query = _to_english_query(keyword)

    try:
        # 페이지를 넓게 랜덤 선택해 매번 다른 이미지 확보
        page = random.randint(1, 15)
        resp = requests.get(
            PEXELS_SEARCH,
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": count + 5, "page": page, "orientation": "landscape"},
            timeout=10,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])

        if not photos:
            # 빈 페이지면 1페이지로 재시도
            page = random.randint(1, 3)
            resp = requests.get(
                PEXELS_SEARCH,
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": query, "per_page": count + 5, "page": page, "orientation": "landscape"},
                timeout=10,
            )
            photos = resp.json().get("photos", [])

        # 가져온 사진 중 랜덤으로 섞어서 반환
        random.shuffle(photos)
        return [p["src"]["large2x"] for p in photos[:count]]
    except Exception as e:
        print(f"  [Pexels] 이미지 검색 실패: {e}")
        return []


def replace_picsum(html: str, keyword: str) -> str:
    """
    HTML 본문의 picsum.photos URL을 Pexels 실제 이미지로 교체.
    이미지 수만큼 Pexels에서 가져오고, 부족하면 원본 유지.
    """
    picsum_pattern = re.compile(r'https://picsum\.photos/[^\s"\']+')
    matches = picsum_pattern.findall(html)

    if not matches:
        return html

    images = fetch_images(keyword, count=len(matches))
    if not images:
        return html  # 실패 시 원본 유지

    result = html
    for i, picsum_url in enumerate(matches):
        if i < len(images):
            result = result.replace(picsum_url, images[i], 1)

    replaced = min(len(matches), len(images))
    print(f"  [Pexels] {replaced}개 이미지 교체 완료 ('{keyword}')")
    return result


# ── 테스트 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    kw = "ChatGPT 업무 생산성"
    print(f"검색어: {kw} → '{_to_english_query(kw)}'")
    urls = fetch_images(kw, count=3)
    if urls:
        for u in urls:
            print(f"  {u[:80]}...")
    else:
        print("  결과 없음 (PEXELS_API_KEY 확인)")
