"""
SEO 향상 모듈 - A급 SEO 자동 적용
1. 목차(TOC) 자동 생성 + H2 앵커 id 삽입
2. Article + FAQPage Schema.org JSON-LD
3. 관련 글 추천 섹션 (내부 링크)
"""

import re
import json
from datetime import date
from pathlib import Path

LOG_PATH  = Path(__file__).parent.parent / "logs" / "upload_log.json"
BLOG_NAME = "오늘의트렌드"
BLOG_URL  = "https://trend-today-kr.blogspot.com"


# ── 메인 진입점 ────────────────────────────────────────────────

def enhance(post: dict, keyword: str) -> dict:
    """
    post dict의 html_content를 A급 SEO 버전으로 강화.
    순서: TOC → 관련 글 → Schema JSON-LD
    """
    html = post["html_content"]

    # 1) H2 앵커 id 삽입 + TOC 생성
    html, toc_html = _make_toc(html)

    # 2) TOC를 첫 </p> 직후에 삽입
    html = _insert_after_first_p(html, toc_html)

    # 3) 관련 글 섹션 (하단)
    related = _get_related_posts(post.get("labels", []), post["title"])
    if related:
        html = html.rstrip() + "\n" + _build_related_section(related)

    # 4) Schema JSON-LD (최상단)
    schema_block = _build_schema(post, keyword, html)
    html = schema_block + "\n" + html

    post["html_content"] = html
    return post


# ── TOC ────────────────────────────────────────────────────────

def _make_toc(html: str) -> tuple[str, str]:
    """H2 태그에 id 삽입 + TOC HTML 반환"""
    counter   = [0]
    toc_items = []

    def add_anchor(m):
        counter[0] += 1
        attrs    = m.group(1) or ""
        inner    = m.group(2)
        text     = re.sub(r"<[^>]+>", "", inner).strip()
        anchor   = f"s{counter[0]}"
        toc_items.append((anchor, text))
        # id가 이미 있으면 교체, 없으면 추가
        if 'id=' in attrs:
            attrs = re.sub(r'id="[^"]*"', f'id="{anchor}"', attrs)
        else:
            attrs += f' id="{anchor}"'
        return f"<h2{attrs}>{inner}</h2>"

    html = re.sub(r"<h2([^>]*)>(.*?)</h2>", add_anchor, html, flags=re.DOTALL)

    if len(toc_items) < 2:
        return html, ""

    li_tags = "\n".join(
        f'    <li style="margin:5px 0;">'
        f'<a href="#{a}" style="color:#4f8ef7;text-decoration:none;">{t}</a></li>'
        for a, t in toc_items
    )

    toc = (
        '<nav style="background:#f8f9ff;border:1px solid #dde4ff;'
        'border-radius:8px;padding:16px 20px;margin:24px 0;">\n'
        '  <p style="font-weight:bold;color:#1a1a2e;margin:0 0 10px;font-size:1em;">목차</p>\n'
        f'  <ol style="margin:0;padding-left:20px;color:#333;font-size:0.95em;">\n'
        f'{li_tags}\n'
        '  </ol>\n'
        '</nav>'
    )
    return html, toc


def _insert_after_first_p(html: str, toc_html: str) -> str:
    """첫 번째 </p> 직후에 TOC 삽입"""
    if not toc_html:
        return html
    m = re.search(r"</p>", html)
    if m:
        pos = m.end()
        return html[:pos] + "\n" + toc_html + html[pos:]
    return toc_html + "\n" + html


# ── 관련 글 ────────────────────────────────────────────────────

def _get_related_posts(labels: list[str], title: str, limit: int = 3) -> list[dict]:
    """업로드 로그에서 같은 라벨 겹치는 최근 글 추출"""
    if not LOG_PATH.exists():
        return []
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            logs = json.load(f)
    except Exception:
        return []

    label_set = set(labels)

    def overlap(e: dict) -> int:
        if e.get("title") == title:
            return -1
        if not e.get("url"):
            return -1
        return len(set(e.get("labels", [])) & label_set)

    candidates = sorted(
        [e for e in logs if e.get("url") and e.get("title") != title],
        key=overlap,
        reverse=True,
    )
    return candidates[:limit]


def _build_related_section(posts: list[dict]) -> str:
    items = "\n".join(
        f'    <li style="margin:8px 0;">'
        f'<a href="{p["url"]}" style="color:#4f8ef7;text-decoration:none;font-weight:500;">'
        f'{p["title"]}</a></li>'
        for p in posts
        if p.get("url") and p.get("title")
    )
    if not items:
        return ""

    return (
        '\n<section style="background:#f0f4ff;border-radius:10px;'
        'padding:20px 24px;margin:36px 0;">\n'
        '  <h2 style="font-size:1.1em;font-weight:bold;color:#1a1a2e;margin:0 0 12px;">관련 글 추천</h2>\n'
        '  <ul style="list-style:disc;padding-left:20px;margin:0;">\n'
        f'{items}\n'
        '  </ul>\n'
        '</section>'
    )


# ── Schema.org ─────────────────────────────────────────────────

def _build_schema(post: dict, keyword: str, html: str) -> str:
    """Article + (FAQPage) JSON-LD 스크립트 태그 반환"""

    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline":      post["title"],
        "description":   post.get("meta_description", ""),
        "datePublished": date.today().isoformat(),
        "dateModified":  date.today().isoformat(),
        "author": {
            "@type": "Organization",
            "name": BLOG_NAME,
            "url":  BLOG_URL,
        },
        "publisher": {
            "@type": "Organization",
            "name": BLOG_NAME,
            "logo": {
                "@type": "ImageObject",
                "url": f"{BLOG_URL}/favicon.ico",
            },
        },
        "keywords": post.get("labels", []),
        "about": {"@type": "Thing", "name": keyword},
    }

    schemas = [article]

    faq_items = _extract_faq(html)
    if faq_items:
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q,
                    "acceptedAnswer": {"@type": "Answer", "text": a},
                }
                for q, a in faq_items
            ],
        }
        schemas.append(faq_schema)
        print(f"  [SEO] FAQPage 스키마 {len(faq_items)}개 질문 추가")

    return "\n".join(
        f'<script type="application/ld+json">\n'
        f'{json.dumps(s, ensure_ascii=False, indent=2)}\n'
        f'</script>'
        for s in schemas
    )


def _extract_faq(html: str) -> list[tuple[str, str]]:
    """HTML 내 '자주 묻는 질문' H2 섹션에서 Q&A 추출"""
    m = re.search(
        r'<h2[^>]*>.*?(?:자주 묻는 질문|FAQ).*?</h2>(.*?)(?=<h2|$)',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return []

    block = m.group(1)
    pairs = re.findall(
        r'<h3[^>]*>(.*?)</h3>\s*<p[^>]*>(.*?)</p>',
        block,
        re.DOTALL,
    )

    result = []
    for q_raw, a_raw in pairs:
        q = re.sub(r"<[^>]+>", "", q_raw).strip()
        a = re.sub(r"<[^>]+>", "", a_raw).strip()
        if q and a:
            result.append((q, a))

    return result[:5]
