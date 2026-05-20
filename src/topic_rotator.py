"""
토픽 로테이터 - 매일 다른 카테고리(재테크, AI, 트렌드 등) 글 생성 보장
"""

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROTATION_PATH = Path("logs/category_rotation.json")

# 카테고리별 키워드 풀 (트렌드 수집 실패 시 또는 다양성 보강용)
KEYWORD_POOL: dict[str, list[str]] = {
    "재테크/금융": [
        "2026 ETF 투자 초보 가이드", "미국 배당주 투자 방법",
        "적금 vs 주식 비교 분석", "부동산 소액 투자 방법",
        "연금저축 IRP 절세 전략", "달러 투자 환율 활용법",
        "코인 vs 주식 무엇이 유리할까", "신용점수 올리는 실전 방법",
        "퇴직금 현명하게 굴리는 법", "청약통장 점수 올리기",
        "재테크 초보 월 50만원 굴리기", "주식 배당금으로 월세 받는 법",
    ],
    "AI/IT": [
        "ChatGPT 업무 생산성 활용법", "AI 이미지 생성 툴 비교",
        "파이썬 자동화 입문 실전", "유튜브 AI 자동 편집 도구",
        "AI 글쓰기 도구 TOP 5 비교", "노코드로 앱 만드는 법",
        "AI 번역기 정확도 비교", "엑셀 데이터 분석 자동화",
        "스마트폰 AI 숨겨진 기능", "AI로 부업하는 현실적인 방법",
        "미드저니 vs 달리 비교", "GPT API 활용 자동화 봇 만들기",
    ],
    "트렌드/라이프": [
        "2026 여행 트렌드 총정리", "요즘 뜨는 카페 인테리어 스타일",
        "한달살기 여행지 추천 TOP 5", "디지털 노마드 현실 후기",
        "주 4일제 직장인 생활 변화", "미니멀 라이프 시작하는 법",
        "홈카페 만드는 비용 현실", "사이드허슬 아이디어 2026",
        "제로웨이스트 생활 실천법", "MZ세대 소비 트렌드 분석",
        "혼자 여행 안전하게 즐기기", "플리마켓 판매 시작 가이드",
    ],
    "건강/의료": [
        "직장인 점심시간 다이어트법", "수면의 질 높이는 7가지 방법",
        "영양제 과학적 조합 가이드", "홈트 30일 루틴 완성하기",
        "눈 피로 빠르게 회복하는 법", "장 건강 개선 식습관",
        "직장인 스트레스 해소 루틴", "혈압 낮추는 식단 가이드",
        "단백질 하루 섭취량 계산법", "비타민D 부족 증상과 해결법",
        "면역력 높이는 생활 습관", "체지방 줄이는 유산소 운동법",
    ],
    "교육/자기계발": [
        "독서 습관 30일 만들기 도전", "온라인 자격증 취득 비용 비교",
        "영어 독학 3개월 플랜 실전", "유튜브 채널 처음 시작하는 법",
        "블로그 수익화 단계별 가이드", "취업 포트폴리오 제작법",
        "노션으로 생산성 3배 올리기", "시간 관리 GTD 시스템 적용",
        "글쓰기 실력 빠르게 키우는 법", "온라인 강의 플랫폼 비교 2026",
        "자기계발 루틴 아침 1시간", "링크드인 프로필 최적화 방법",
    ],
    "맛집/푸드": [
        "생생정보통 오늘 맛집 위치 정리", "생생정보 방영 음식점 찾아가기",
        "6시 내고향 맛집 총정리", "전국맛자랑 출연 식당 위치",
        "백종원 골목식당 맛집 현재 운영 확인", "수요미식회 맛집 다시 보기",
        "생방송 오늘 저녁 맛집 정보", "2TV 생생정보 맛집 지도",
        "전국 3대 맛집 실제 후기", "줄서는 식당 예약 방법 정리",
        "숨은 노포 맛집 발굴 가이드", "TV 맛집 실망 vs 기대 이상 비교",
    ],
}

CATEGORY_ORDER = list(KEYWORD_POOL.keys())


def _load() -> dict:
    if not ROTATION_PATH.exists():
        return {"daily": {}, "used_keywords": []}
    with open(ROTATION_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    ROTATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ROTATION_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_today_categories(count: int) -> list[str]:
    """
    오늘 생성할 글의 카테고리 목록을 결정한다.
    최근 사용 횟수가 적은 카테고리를 우선 배정.
    """
    data = _load()
    today = str(date.today())

    if today in data.get("daily", {}):
        return data["daily"][today][:count]

    usage: dict[str, int] = defaultdict(int)
    for day_cats in data.get("daily", {}).values():
        for cat in day_cats:
            usage[cat] += 1

    sorted_cats = sorted(CATEGORY_ORDER, key=lambda c: usage[c])
    plan = [sorted_cats[i % len(sorted_cats)] for i in range(count)]

    data.setdefault("daily", {})[today] = plan
    _save(data)
    return plan


def get_diverse_keywords(count: int, trend_keywords: list[dict]) -> list[dict]:
    """
    트렌드 키워드 + 카테고리 로테이션을 결합해 다양한 키워드 목록 반환.
    트렌드 키워드가 특정 카테고리에 몰려 있을 때 폴백 키워드로 보완한다.
    """
    data = _load()
    used: list[str] = data.get("used_keywords", [])

    categories = get_today_categories(count)
    result: list[dict] = []

    # 카테고리별로 1개씩 배정
    for cat in categories:
        # 트렌드 키워드 중 해당 카테고리에 맞는 것 탐색
        matched = _match_trend_to_category(trend_keywords, cat, [r["keyword"] for r in result])
        if matched:
            result.append(matched)
        else:
            # 폴백: 풀에서 아직 안 쓴 키워드 선택
            kw = _pick_from_pool(cat, used + [r["keyword"] for r in result])
            result.append({"keyword": kw, "score": 50, "sources": ["pool"], "category": cat})

    return result[:count]


def mark_used(keywords: list[str]):
    """사용한 키워드를 기록해 재사용 방지"""
    data = _load()
    used = data.get("used_keywords", [])
    used.extend(keywords)
    data["used_keywords"] = used[-300:]
    _save(data)


# ── 내부 헬퍼 ──────────────────────────────────────────────────────────────

_CATEGORY_HINTS: dict[str, list[str]] = {
    "재테크/금융": ["주식", "ETF", "부동산", "코인", "적금", "대출", "보험", "재테크", "투자", "금융", "경제", "환율", "배당"],
    "AI/IT": ["AI", "챗GPT", "ChatGPT", "인공지능", "파이썬", "자동화", "앱", "스마트폰", "IT", "테크", "코딩", "디지털"],
    "트렌드/라이프": ["여행", "트렌드", "카페", "맛집", "라이프", "노마드", "미니멀", "홈", "플리마켓", "주 4일"],
    "건강/의료": ["다이어트", "운동", "건강", "영양제", "수면", "병원", "의료", "비타민", "면역", "단백질"],
    "교육/자기계발": ["자격증", "영어", "강의", "책", "독서", "공부", "취업", "포트폴리오", "유튜브", "블로그"],
    "맛집/푸드": ["맛집", "생생정보", "6시 내고향", "전국맛자랑", "백종원", "식당", "노포", "음식", "푸드", "맛있는", "줄서는", "수요미식회"],
}


def _match_trend_to_category(trends: list[dict], category: str, already: list[str]) -> dict | None:
    hints = _CATEGORY_HINTS.get(category, [])
    for t in trends:
        kw = t["keyword"]
        if kw in already:
            continue
        if any(h in kw for h in hints):
            return {**t, "category": category}
    return None


def _pick_from_pool(category: str, used: list[str]) -> str:
    pool = KEYWORD_POOL.get(category, [])
    for kw in pool:
        if kw not in used:
            return kw
    return pool[0] if pool else category
