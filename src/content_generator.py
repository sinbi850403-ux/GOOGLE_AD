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

load_dotenv()

CLAUDE_API_KEY  = os.getenv("CLAUDE_API_KEY")
BLOG_LANGUAGE   = os.getenv("BLOG_LANGUAGE", "ko")
ADSENSE_CLIENT  = os.getenv("ADSENSE_CLIENT", "ca-pub-2764893290310463")
ADSENSE_SLOT    = os.getenv("ADSENSE_SLOT", "")

# ── AdSense 광고 삽입 ─────────────────────────────────────────

_ADSENSE_UNIT = """\
<div style="margin:24px 0;text-align:center;">
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="{client}"
     data-ad-slot="{slot}"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>"""

_ADSENSE_AUTO = """\
<div style="margin:24px 0;text-align:center;">
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="{client}"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>"""

def _build_ad_unit() -> str:
    if ADSENSE_SLOT:
        return _ADSENSE_UNIT.format(client=ADSENSE_CLIENT, slot=ADSENSE_SLOT)
    return _ADSENSE_AUTO.format(client=ADSENSE_CLIENT)

def inject_adsense(html: str) -> str:
    """H2 태그 사이마다 AdSense 광고 단위를 삽입 (2번째, 4번째 H2 이후)."""
    if not ADSENSE_CLIENT:
        return html
    ad = _build_ad_unit()
    h2_positions = [m.start() for m in re.finditer(r"<h2[\s>]", html, re.IGNORECASE)]
    # 2번째, 4번째 H2 이후에 광고 삽입 (삽입 위치 오프셋 누적)
    insert_after = {1, 3}  # 0-indexed
    offset = 0
    for i, pos in enumerate(h2_positions):
        if i in insert_after:
            # 해당 H2 블록의 </h2> 뒤를 찾아 광고 삽입
            close = html.find("</h2>", pos + offset)
            if close == -1:
                continue
            insert_at = close + len("</h2>") + offset
            html = html[:insert_at] + "\n" + ad + html[insert_at:]
            offset += len(ad) + 1
    return html


# ── 카테고리 감지 ──────────────────────────────────────────────

_CATEGORY_MAP = {
    "재테크/금융":   ["주식", "ETF", "적금", "대출", "보험", "코인", "부동산", "비트코인", "투자", "펀드", "배당"],
    "건강/의료":     ["다이어트", "영양제", "운동", "건강", "질병", "헬스", "체중", "수면", "비타민"],
    "IT/테크":       ["AI", "인공지능", "스마트폰", "노트북", "앱", "소프트웨어", "ChatGPT", "자동화"],
    "여행/라이프":   ["여행", "맛집", "호텔", "항공", "카페", "숙소", "관광"],
    "교육/자기계발": ["자격증", "영어", "온라인강의", "책", "독서", "공부", "취업", "이직"],
}

def detect_category(keyword: str) -> str:
    for cat, kws in _CATEGORY_MAP.items():
        if any(k in keyword for k in kws):
            return cat
    return "라이프스타일"


# ── 매일 다른 글쓰기 각도 ─────────────────────────────────────

_ANGLES = [
    ("초보자 완전 정복",
     "처음 시작하는 사람을 위해 A부터 Z까지 쉽게 설명하세요. 전문 용어는 반드시 풀어쓰고, 첫 단계부터 순서대로 안내하세요."),
    ("실전 사례 분석",
     "실제 사례와 구체적 수치를 중심으로 작성하세요. '누군가가 실제로 이렇게 했다'는 스토리텔링 구조로 독자의 공감을 이끌어내세요."),
    ("오해와 진실",
     "이 주제에 대한 흔한 오해 5가지를 먼저 나열하고 각각 반박하세요. '사람들이 틀리게 알고 있는 것'을 교정하는 형식으로 쓰세요."),
    ("비용 vs 수익 완전 분석",
     "숫자와 계산식을 적극 활용하세요. 실제 비용, 예상 수익, ROI, 리스크를 표 형식으로 정리하고 독자가 직접 계산해볼 수 있게 하세요."),
    ("전문가 7가지 핵심 팁",
     "현장 전문가 시각에서 대부분의 사람이 모르는 실용 팁 7가지를 엄선하세요. 각 팁마다 '왜 효과적인가'를 반드시 설명하세요."),
    ("최신 트렌드 전망",
     "최근 변화와 올해 트렌드를 분석하세요. 통계·연구 결과를 인용하고, 독자가 지금 당장 어떻게 대응해야 하는지 명확히 제시하세요."),
    ("실수 피하는 법",
     "초보자가 가장 많이 저지르는 실수 TOP 5를 중심으로 작성하세요. 각 실수의 원인, 결과, 예방법을 구체적으로 설명하세요."),
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

def _parse_labels(raw_labels: str) -> list[str]:
    """쉼표·개행·불릿 등 다양한 형식으로 출력된 라벨을 파싱"""
    # 전각 쉼표(，) → 반각 쉼표
    text = raw_labels.replace("，", ",").replace("、", ",")
    # 불릿/번호 리스트(-, *, 1.) → 쉼표 구분으로 통일
    text = re.sub(r"[\-\*\d]+[\.\)]\s*", ",", text)
    # 개행 → 쉼표
    text = text.replace("\n", ",")
    result = [l.strip().lstrip("-*").strip() for l in text.split(",") if l.strip().lstrip("-*").strip()]
    return result[:7]  # 최대 7개


def parse_response(raw: str) -> dict | None:
    title  = _extract(raw, "TITLE")
    meta   = _extract(raw, "META")
    labels = _extract(raw, "LABELS")
    html   = _extract(raw, "HTML")

    if not all([title, meta, html]):
        return None

    parsed_labels = _parse_labels(labels) if labels else []

    return {
        "title":            title,
        "meta_description": meta,
        "labels":           parsed_labels,
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

    return f"""당신은 구글 애드센스 최적화 전문 블로그 작가입니다.
{lang}

키워드: {keyword}
카테고리: {category}
글쓰기 각도: [{angle_name}]
각도 설명: {angle_inst}
{avoid}
[작성 조건]
- 제목: [{angle_name}] 관점이 드러나는 독창적 제목, 숫자 또는 {year} 포함, 50자 이내
- 메타 설명: 검색 결과에 표시될 설명, 150자 이내
- 라벨: 관련 태그 5개, 쉼표로 구분
- 본문: 최소 1500자 HTML, H2 섹션 5개 이상, 각 H2 아래 H3 2개 이상
- 각 H2 섹션 시작 직후 반드시 이미지 태그 삽입: <img src="https://picsum.photos/800/450?random=1" alt="관련 이미지" style="width:100%;max-width:800px;border-radius:8px;margin:12px 0"> (random= 값은 섹션마다 다른 숫자 사용)
- 구체적 수치·예시·단계 포함, 마지막 섹션에서 독자 행동 유도

[출력 형식 엄수 — 이 형식 외 다른 텍스트 절대 금지]
{SEP}TITLE{SEP}
제목을 여기에
{SEP}META{SEP}
메타 설명을 여기에
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
                if text_len < 800:
                    print(f"  시도 {attempt+1}: 본문 짧음 ({text_len}자), 재시도...")
                    continue

                # 라벨 폴백: 파싱 실패 시 키워드+카테고리로 자동 생성
                if not post["labels"]:
                    year = str(date.today().year)
                    post["labels"] = [
                        keyword.replace(" ", ""),
                        category.replace("/", ""),
                        year + keyword.split()[0] if keyword.split() else year,
                        angle_name.replace(" ", ""),
                    ]
                    print(f"  라벨 폴백 적용: {post['labels']}")

                # Pexels 이미지로 교체
                post["html_content"] = replace_picsum(post["html_content"], keyword)

                # AdSense 광고 삽입
                post["html_content"] = inject_adsense(post["html_content"])

                print(f"  완료: '{post['title']}' ({text_len}자) | 태그: {len(post['labels'])}개")
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
