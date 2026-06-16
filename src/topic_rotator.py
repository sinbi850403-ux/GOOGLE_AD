"""
토픽 로테이터 - 7개 자영업 카테고리를 순서대로 1시간 간격 로테이션
카테고리 순서: 매출관리 → 부가세/세금 → 절세꿀팁 → 배달앱 → 카드수수료 → 사업자등록 → 직원관리
"""

import json
import os
from datetime import datetime
from pathlib import Path

ROTATION_PATH = Path("logs/category_rotation.json")

# ── 7개 블로그 카테고리 순환 순서 ────────────────────────────────
CATEGORY_ORDER = [
    "매출관리",
    "부가세/세금",
    "절세꿀팁",
    "배달앱",
    "카드수수료",
    "사업자등록",
    "직원관리",
]

# ── 카테고리별 키워드 풀 ─────────────────────────────────────────
KEYWORD_POOL: dict[str, list[str]] = {
    "매출관리": [
        "카페 사장님 매출 관리 엑셀 vs 앱 비교",
        "음식점 하루 매출 정리 가장 쉬운 방법",
        "포스(POS) 기기 선택 방법 및 비용 비교 2026",
        "소상공인 매출 분석 무료 도구 TOP 5",
        "배달앱 매출과 홀 매출 한 번에 관리하는 법",
        "카페 원가 계산법 음료별 마진 분석",
        "음식점 사장님 재고 관리 실전 방법",
        "편의점 매출 관리 자동화하는 방법",
        "매장 매출 목표 설정과 달성 전략",
        "소규모 음식점 일일 마감 정산 방법",
        "카드 매출 현금 매출 통합 관리 노하우",
        "배달앱별 정산 주기와 매출 관리 팁",
        "주말 vs 평일 매출 패턴 분석법",
        "시간대별 매출 분석으로 인건비 줄이기",
        "월별 매출 리포트 만드는 방법",
    ],
    "부가세/세금": [
        "자영업자 부가세 신고 완전 정복 초보 가이드",
        "간이과세자 부가세 신고 방법 2026년 기준",
        "일반과세자 부가세 신고 실수 안 하는 법",
        "음식점 부가세 면세 vs 과세 항목 구분",
        "카드 매출 부가세 계산 방법 완전 정리",
        "배달앱 부가세 처리 방법 플랫폼별 정리",
        "홈택스 부가세 신고 순서대로 따라하기",
        "부가세 환급 받는 조건과 신청 방법",
        "자영업자 종합소득세 신고 처음이라면",
        "사업 경비 인정 항목 완전 정리",
        "세금계산서 발행 방법과 주의사항",
        "현금영수증 발행 의무와 미발행 과태료",
        "부가세 예정 신고 vs 확정 신고 차이",
        "간이과세 기준금액 2026년 바뀐 점",
        "음식점 의제매입세액 공제 방법",
    ],
    "절세꿀팁": [
        "자영업자 절세 방법 사업 경비 처리 완전 가이드",
        "소상공인 놓치면 손해인 세금 공제 항목",
        "카드단말기 렌탈비 경비 처리 가능할까",
        "자영업자 퇴직연금 개인 IRP 절세 활용법",
        "노란우산공제 가입하면 얼마나 절세될까",
        "음식점 인테리어 비용 경비 처리 방법",
        "가족 직원 고용으로 절세하는 방법과 주의점",
        "사업용 차량 경비 처리 완전 가이드",
        "소상공인 세금우대 저축 상품 총정리",
        "자영업자 건강보험료 줄이는 방법",
        "간이과세자로 전환 시 절세 효과 계산",
        "배달앱 수수료 전액 경비 처리 방법",
        "임대료 경비 처리 조건과 주의사항",
        "소상공인 지원금 2026 신청 방법 총정리",
        "자영업자 연말정산 절세 전략",
    ],
    "배달앱": [
        "배달의민족 수수료 구조 완전 분석 2026",
        "쿠팡이츠 vs 배민 수수료 비교 어떤 게 유리할까",
        "요기요 수수료 정책 2026년 최신 정리",
        "배달앱 별점 관리 사장님 실전 노하우",
        "배달앱 광고비 아끼면서 주문 늘리는 법",
        "배달 포장 용기 비용 절감하는 방법",
        "배달앱 3사 동시 입점 장단점 분석",
        "배달앱 메뉴 사진 잘 찍는 방법 실전 팁",
        "배달앱 리뷰 관리 사장님 대처법",
        "배달앱 없이 자체 배달 시스템 구축하기",
        "카카오 주문하기 입점 방법과 수수료",
        "배달앱 프리미엄 광고 효과 있을까",
        "배달 최소 주문금액 설정 전략",
        "배달앱 정산 지연 문제 해결 방법",
        "배달앱 가입비 없이 시작하는 방법",
    ],
    "카드수수료": [
        "음식점 카드 수수료 줄이는 방법 5가지",
        "카드 수수료율 업종별 우대 적용 방법 2026",
        "영세 소상공인 카드 수수료 우대 신청하기",
        "제로페이 도입하면 수수료 얼마나 줄까",
        "네이버페이 카카오페이 수수료 비교 분석",
        "카드단말기 종류별 수수료 비교",
        "QR코드 결제 도입 비용과 수수료",
        "카드 수수료 연간 얼마나 내는지 계산법",
        "수수료 우대 받는 연매출 기준 정리",
        "현금 결제 유도 합법적으로 하는 방법",
        "배달앱 결제 수수료 vs 홀 카드 수수료 비교",
        "카드 수수료 환급 받는 방법",
        "간이과세자 카드 수수료 처리 방법",
        "신용카드 vs 체크카드 가맹점 수수료 차이",
        "무인 결제 키오스크 수수료 분석",
    ],
    "사업자등록": [
        "음식점 사업자 등록 순서대로 따라하기",
        "개인사업자 vs 법인 어떤 게 유리할까",
        "간이과세자 vs 일반과세자 선택 기준",
        "카페 창업 사업자 등록 준비물 총정리",
        "음식점 영업신고 절차와 준비 서류",
        "사업자 등록 후 꼭 해야 할 일 체크리스트",
        "편의점 창업 비용 수익 현실적인 분석",
        "카페 창업 실패하는 이유 TOP 7 예방법",
        "휴업 폐업 신고 방법과 주의사항",
        "공동대표 사업자 등록 방법과 주의점",
        "배달 전문점 사업자 등록 특이사항",
        "프랜차이즈 창업 vs 독립 창업 비교",
        "사업자 등록 전에 꼭 알아야 할 것들",
        "네이버 플레이스 노출 잘 되는 방법 2026",
        "음식점 위생 등급 받으면 뭐가 좋을까",
    ],
    "직원관리": [
        "음식점 직원 채용 근로계약서 작성법",
        "자영업자 4대보험 얼마나 내야 할까 실제 계산",
        "알바생 주휴수당 계산 방법 완전 정리",
        "최저시급 2026년 기준 아르바이트 급여 계산",
        "직원 연차 계산 방법 소상공인 가이드",
        "음식점 아르바이트 야간수당 계산법",
        "4대보험 가입 기준 시간제 직원 정리",
        "직원 퇴직금 계산 방법과 지급 시기",
        "가족 고용 시 4대보험 처리 방법",
        "직원 해고 절차 합법적으로 하는 방법",
        "소규모 사업장 취업규칙 작성 방법",
        "알바 결근 지각 급여 공제 방법",
        "직원 식대 복리후생비 경비 처리",
        "산재보험 소상공인 적용 범위와 신청",
        "고용보험 일용직 신고 방법",
    ],
}

# ── 카테고리 힌트 (트렌드 키워드 매칭용) ─────────────────────────
_CATEGORY_HINTS: dict[str, list[str]] = {
    "매출관리":   ["매출", "포스", "POS", "정산", "마진", "원가", "재고"],
    "부가세/세금": ["부가세", "세금", "종합소득세", "홈택스", "세금계산서", "현금영수증"],
    "절세꿀팁":   ["절세", "경비", "공제", "노란우산", "IRP", "세금 줄이기"],
    "배달앱":     ["배달", "배민", "쿠팡이츠", "요기요", "배달앱", "배달의민족"],
    "카드수수료": ["카드수수료", "수수료", "제로페이", "단말기", "결제"],
    "사업자등록": ["사업자", "창업", "영업신고", "폐업", "휴업", "프랜차이즈"],
    "직원관리":   ["직원", "알바", "아르바이트", "4대보험", "주휴수당", "퇴직금", "최저시급"],
}


# ── 현재 시각 기반 카테고리 결정 (1시간 간격 로테이션) ─────────────

def get_current_category() -> str:
    """현재 시각의 시(hour)를 7로 나눈 나머지로 카테고리 결정"""
    hour = datetime.now().hour
    return CATEGORY_ORDER[hour % len(CATEGORY_ORDER)]


def _load() -> dict:
    if not ROTATION_PATH.exists():
        return {"used_keywords": []}
    try:
        with open(ROTATION_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"used_keywords": []}


def _save(data: dict):
    ROTATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ROTATION_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_diverse_keywords(count: int, trend_keywords: list[dict]) -> list[dict]:
    """
    오늘 아직 발행 안 한 카테고리 중 순서대로 선택.
    스케줄러가 매 시각 count=1로 호출하면 해당 시각 카테고리 반환.
    """
    data = _load()
    used: list[str] = data.get("used_keywords", [])
    today = datetime.now().strftime("%Y-%m-%d")
    posted_today: list[str] = data.get("posted_today", {}).get(today, [])

    # 오늘 아직 안 올린 카테고리를 순서 유지하며 선택
    remaining = [c for c in CATEGORY_ORDER if c not in posted_today]
    if not remaining:
        remaining = CATEGORY_ORDER  # 하루치 다 올렸으면 처음부터

    result: list[dict] = []
    for i in range(count):
        cat = remaining[i % len(remaining)]
        matched = _match_trend_to_category(trend_keywords, cat, [r["keyword"] for r in result])
        if matched:
            result.append(matched)
        else:
            kw = _pick_from_pool(cat, used + [r["keyword"] for r in result])
            result.append({"keyword": kw, "score": 50, "sources": ["pool"], "category": cat})

    return result[:count]


def mark_used(keywords: list[str], categories: list[str] = None):
    data  = _load()
    today = datetime.now().strftime("%Y-%m-%d")

    used = data.get("used_keywords", [])
    used.extend(keywords)
    data["used_keywords"] = used[-500:]

    if categories:
        posted = data.setdefault("posted_today", {})
        posted.setdefault(today, []).extend(categories)
        # 오래된 날짜 정리 (최근 7일만 유지)
        data["posted_today"] = {k: v for k, v in posted.items()
                                if k >= datetime.now().strftime("%Y-%m-%") or True}

    _save(data)


# ── 내부 헬퍼 ────────────────────────────────────────────────────

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
    unused = [kw for kw in pool if kw not in used]
    if not unused:
        unused = pool  # 전부 썼으면 처음부터 재사용
    if not unused:
        return category
    run_id = os.getenv("GITHUB_RUN_ID", "0")
    offset = int(run_id) % len(unused) if run_id.isdigit() else 0
    return unused[offset]
