"""
Claude API 블로그 글 생성기
- JSON 완전 제거: 파싱 오류 원천 차단
- 매일 다른 글쓰기 각도(앵글) 자동 로테이션
- 실패 시 자동 재시도 (최대 3회)
"""

import os
import re
import hashlib
import anthropic
from datetime import date
from dotenv import load_dotenv
from pexels_image import replace_picsum
from seo_enhancer import enhance as seo_enhance

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
BLOG_LANGUAGE  = os.getenv("BLOG_LANGUAGE", "ko")

# ── 카테고리 감지 ──────────────────────────────────────────────

_CATEGORY_MAP = {
    "재테크/금융":   ["주식", "ETF", "적금", "대출", "보험", "코인", "부동산", "비트코인", "투자", "펀드", "배당", "코스피", "코스닥", "지수"],
    "건강/의료":     ["다이어트", "영양제", "운동", "건강", "질병", "헬스", "체중", "수면", "비타민"],
    "IT/테크":       ["AI", "인공지능", "스마트폰", "노트북", "앱", "소프트웨어", "ChatGPT", "자동화"],
    "여행/라이프":   ["여행", "맛집", "호텔", "항공", "숙소", "관광"],
    "교육/자기계발": ["자격증", "영어", "온라인강의", "책", "독서", "공부", "취업", "이직"],
    "자영업/매출관리": ["자영업", "사장님", "부가세", "카드수수료", "배달앱", "배민", "쿠팡이츠", "포스", "소상공인", "폐업", "간이과세", "종합소득세", "근로계약", "4대보험", "카페 창업", "편의점 창업"],
}

def detect_category(keyword: str) -> str:
    for cat, kws in _CATEGORY_MAP.items():
        if any(k in keyword for k in kws):
            return cat
    return "라이프스타일"


# ── 매일 다른 글쓰기 각도 ─────────────────────────────────────

_ANGLES = [
    ("초보자 완전 정복",
     "처음 시작하는 사람 눈높이에서 A부터 Z까지 쉽게 설명하세요. 전문 용어는 반드시 풀어쓰고, 실제로 겪는 막막함을 해소해주는 구체적인 첫 단계부터 안내하세요. 직접 해본 사람만 알 수 있는 실전 팁을 반드시 포함하세요."),
    ("실전 사례 분석",
     "현실적인 사례와 구체적 수치를 중심으로 작성하세요. 실제로 일어날 법한 상황을 생생하게 묘사하고, 독자가 '이건 나 얘기다'라고 느끼게 하세요. 결과까지 수치로 보여주고, 그 과정에서 배운 교훈을 솔직하게 서술하세요."),
    ("오해와 진실",
     "이 주제에 대해 인터넷에 퍼진 잘못된 정보나 흔한 오해 5가지를 먼저 나열하고 각각 반박하세요. '왜 그 오해가 생겼는지'까지 설명하고, 실제 전문가나 현장의 입장을 정확히 전달하세요."),
    ("비용·손익 완전 계산",
     "숫자와 계산식을 적극 활용하세요. 실제 비용, 예상 효과, 리스크를 표 형식으로 정리하고 독자가 자신의 상황에 직접 대입해볼 수 있는 계산 방식을 제시하세요. 놓치기 쉬운 숨겨진 비용이나 절감 포인트를 반드시 포함하세요."),
    ("현장 전문가 핵심 노하우",
     "실제 현장에서 수년간 쌓인 경험 기반의 실용 노하우를 전달하세요. 교과서에 없는, 실제로 써봐야 아는 팁과 '이건 절대 하면 안 된다'는 경고도 함께 주세요. 각 팁마다 구체적인 이유와 효과를 설명하세요."),
    ("최신 변화 대응 가이드",
     "최근 바뀐 제도·환경·트렌드를 분석하고, 독자가 지금 당장 어떻게 대응해야 하는지 단계별로 제시하세요. '예전엔 이랬는데 지금은 이렇다'는 변화 포인트를 명확히 짚고, 대응하지 않으면 어떤 손해가 생기는지도 경고하세요."),
    ("실수 예방 완전 가이드",
     "실제로 많은 사람이 저지르는 실수 TOP 5를 중심으로 작성하세요. 각 실수가 얼마나 흔한지, 왜 생기는지, 어떤 결과를 낳는지, 어떻게 예방하는지를 현실적으로 설명하세요. 독자가 '나도 저럴 뻔했다'고 느끼게 하세요."),
]

def pick_angle(keyword: str) -> tuple:
    """키워드 + 오늘 날짜 조합으로 각도 결정 → 매일 자동 변경"""
    seed = keyword + str(date.today())
    idx  = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(_ANGLES)
    return _ANGLES[idx]


# ── 구분자 기반 파싱 (JSON 완전 제거) ─────────────────────────

SEP = "###"

def _extract(raw: str, tag: str) -> str | None:
    pattern = rf"{re.escape(SEP)}{tag}{re.escape(SEP)}\s*(.*?)\s*(?={re.escape(SEP)}|\Z)"
    m = re.search(pattern, raw, re.DOTALL)
    return m.group(1).strip() if m else None

def sanitize_slug(raw: str | None) -> str | None:
    """모델이 준 슬러그를 URL 에 넣어도 안전한 형태로 정리한다.
    영문·숫자·하이픈만 남기므로 한글이 섞여 오면 그 부분은 사라진다."""
    if not raw:
        return None
    s = raw.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > 60:
        s = s[:60].rstrip("-")
    # 너무 짧으면 키워드가 안 담긴 것이라 쓰지 않는다(그럴 바엔 기존 동작).
    return s if len(s) >= 8 else None


def parse_response(raw: str) -> dict | None:
    title  = _extract(raw, "TITLE")
    meta   = _extract(raw, "META")
    labels = _extract(raw, "LABELS")
    html   = _extract(raw, "HTML")

    if not all([title, meta, labels, html]):
        return None

    return {
        "title":            title,
        # 없으면 None — 업로더가 종전 방식으로 처리한다(주소만 나빠질 뿐 발행은 된다).
        "slug":             sanitize_slug(_extract(raw, "SLUG")),
        "meta_description": meta,
        "labels":           [l.strip() for l in labels.split(",") if l.strip()],
        "html_content":     html,
    }


# ── 프롬프트 빌더 ─────────────────────────────────────────────

def build_prompt(keyword: str, category: str, recent_titles: list[str] = None) -> str:
    lang = "반드시 한국어로 작성하세요." if BLOG_LANGUAGE == "ko" else "Write in English."
    angle_name, angle_inst = pick_angle(keyword)
    year = date.today().year

    avoid = ""
    if recent_titles:
        avoid = (
            "\n[절대 금지] 아래 기존 제목과 동일하거나 유사한 주제·제목 사용 금지:\n"
            + "\n".join(f"  - {t}" for t in recent_titles[-20:])
            + "\n"
        )

    return f"""당신은 {category} 분야에서 10년 이상 현장 경험을 쌓은 전문가이자, 실제로 독자에게 도움이 되는 블로그를 운영 중인 작가입니다.
{lang}

오늘 글의 주제: {keyword}
글쓰기 방향: [{angle_name}] — {angle_inst}
{avoid}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 핵심 원칙: 구글 애드센스 승인을 받을 수 있는 고품질 콘텐츠를 작성하세요.
- 누구나 쓸 수 있는 일반적인 정보 ❌ → 현장에서만 알 수 있는 실질적 정보 ✅
- "~할 수 있습니다" 식의 막연한 서술 ❌ → 구체적 수치·사례·단계 ✅
- 1~2줄짜리 단락 나열 ❌ → 맥락이 연결되는 깊이 있는 분석 ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[제목 — 독자가 클릭할 수밖에 없는 제목]
- [{angle_name}] 관점이 명확히 드러나는 제목
- 숫자 또는 {year} 포함, 45자 이내
- 독자의 현실적인 고민이나 궁금증을 정확히 짚는 표현 사용
- 절대 금지: "완벽정리", "총정리", "알아보겠습니다" 같은 진부한 표현

[본문 구조 — 독자가 끝까지 읽는 글]
① 도입 (150자 이상): 독자가 겪는 구체적인 상황을 묘사하며 시작 → "이 글이 나를 위한 글"이라는 확신을 줄 것
② 본문: 단순 나열 금지. 정보 → 이유 → 실제 적용 방법 → 주의점의 흐름으로 깊이 있게 서술
③ 각 H2 섹션은 최소 250자 이상의 실질적 내용 포함
④ 숫자·비율·금액·기간 등 구체적 수치를 최소 10개 이상 사용
⑤ 마지막 H2: "자주 묻는 질문 (FAQ)" — 독자가 실제로 궁금해할 질문 3개 + 상세 답변

[HTML 작성 조건]
- 순수 텍스트 기준 최소 2500자 이상
- H2 섹션 6개 이상, 각 H2 아래 H3 2개 이상
- 각 H2 섹션 직후 이미지 삽입: <img src="https://picsum.photos/800/450?random=숫자" alt="섹션 내용 설명" style="width:100%;max-width:800px;border-radius:8px;margin:16px 0 20px">
- 중요한 수치나 팁은 <blockquote> 또는 강조 박스로 시각화
- 단계별 내용은 <ol>, 체크리스트는 <ul>로 구조화

[슬러그]
한글 제목은 Blogger가 슬러그 생성 시 전부 버림 → 영문 SEO 슬러그 직접 제공
소문자·하이픈만, 4~7단어, 60자 이내
예) 소상공인 부가세 신고 방법 → small-business-vat-filing-guide-{year}

[출력 형식 엄수 — 이 형식 외 다른 텍스트 절대 금지]
{SEP}TITLE{SEP}
제목을 여기에
{SEP}SLUG{SEP}
english-slug-here
{SEP}META{SEP}
검색 결과에 표시될 설명 (독자가 클릭하고 싶게, 150자 이내)
{SEP}LABELS{SEP}
태그1,태그2,태그3,태그4,태그5
{SEP}HTML{SEP}
HTML 본문 전체를 여기에
{SEP}END{SEP}"""


# ── 생성기 ────────────────────────────────────────────────────

class ContentGenerator:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        self.model  = "claude-sonnet-4-6"

    def generate(self, keyword: str, recent_titles: list[str] = None) -> dict | None:
        category   = detect_category(keyword)
        angle_name = pick_angle(keyword)[0]
        print(f"  생성: '{keyword}' [{angle_name}] ({category})")

        prompt = build_prompt(keyword, category, recent_titles)

        for attempt in range(3):
            try:
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=8192,
                    messages=[{"role": "user", "content": prompt}],
                )

                raw  = resp.content[0].text
                post = parse_response(raw)

                if post is None:
                    print(f"  시도 {attempt+1}: 형식 불일치, 재시도...")
                    continue

                text_len = len(re.sub(r"<[^>]+>", "", post["html_content"]))
                if text_len < 1500:
                    print(f"  시도 {attempt+1}: 본문 짧음 ({text_len}자), 재시도...")
                    continue

                # Pexels 이미지로 교체
                post["html_content"] = replace_picsum(post["html_content"], keyword)

                # SEO 강화 (TOC + 관련글 + Schema)
                post = seo_enhance(post, keyword)

                print(f"  완료: '{post['title']}' ({text_len}자)")
                return post

            except Exception as e:
                print(f"  시도 {attempt+1} 오류: {e}")

        print(f"  [실패] '{keyword}' 3회 시도 후 포기")
        return None

    def generate_batch(self, keywords: list[dict], recent_titles: list[str] = None) -> list[dict]:
        results    = []
        all_titles = list(recent_titles or [])
        for kw_data in keywords:
            keyword = kw_data["keyword"]
            post    = self.generate(keyword, recent_titles=all_titles)
            if post:
                post["source_keyword"] = keyword
                post["trend_score"]    = kw_data.get("score", 0)
                all_titles.append(post["title"])
                results.append(post)
        return results


if __name__ == "__main__":
    gen = ContentGenerator()
    result = gen.generate("비트코인 투자")
    if result:
        print(f"\n제목: {result['title']}")
        print(f"앵글: {pick_angle('비트코인 투자')[0]}")
        print(f"메타: {result['meta_description']}")
        print(f"태그: {result['labels']}")
        print(f"본문: {len(result['html_content'])}자")
