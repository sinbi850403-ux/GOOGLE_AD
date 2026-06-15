"""
정적 HTML 블로그 발행기
AdBot이 생성한 콘텐츠를 oneul-jangbu/public/blog/posts/*.html 로 저장
blog-manifest.json 및 sitemap.xml 자동 갱신
"""

import json
import re
import os
from pathlib import Path
from datetime import date, datetime
from slugify import slugify  # python-slugify


# ── 경로 설정 ────────────────────────────────────────────────────

_HERE   = Path(__file__).resolve().parent
_ROOT   = _HERE.parent
JANGBU  = Path(os.getenv("JANGBU_PATH", str(_ROOT.parent / "oneul-jangbu")))

BLOG_DIR     = JANGBU / "public" / "blog"
POSTS_DIR    = BLOG_DIR / "posts"
MANIFEST     = BLOG_DIR / "blog-manifest.json"
SITEMAP      = JANGBU / "public" / "sitemap.xml"
BASE_URL     = "https://xn--wh1bw0st1gbrb.kr"
LOG_PATH     = _ROOT / "logs" / "static_upload_log.json"


# ── 카테고리 → 블로그 태그 매핑 ─────────────────────────────────

_CAT_MAP = {
    "재테크/금융":   "절세꿀팁",
    "건강/의료":     "건강정보",
    "IT/테크":       "IT/테크",
    "여행/라이프":   "라이프",
    "교육/자기계발": "자기계발",
    "라이프스타일":  "매출관리",
}

_KEYWORD_CAT = {
    "부가세": "부가세/세금",
    "세금":   "부가세/세금",
    "절세":   "절세꿀팁",
    "배달":   "배달앱",
    "배민":   "배달앱",
    "쿠팡이츠": "배달앱",
    "카드수수료": "카드수수료",
    "포스":   "매출관리",
    "매출":   "매출관리",
    "사업자": "사업자등록",
    "직원":   "직원관리",
    "4대보험": "직원관리",
    "근로계약": "직원관리",
}

def resolve_category(keyword: str, original_cat: str) -> str:
    kw = keyword or ""
    for k, v in _KEYWORD_CAT.items():
        if k in kw:
            return v
    return _CAT_MAP.get(original_cat, "매출관리")


# ── 포스트 HTML 템플릿 ───────────────────────────────────────────

def _post_html(post: dict, slug: str, category: str) -> str:
    title   = post["title"]
    meta    = post["meta_description"]
    content = post["html_content"]
    labels  = post.get("labels", [])
    today   = date.today().strftime("%Y년 %m월 %d일")
    tags_html = " ".join(f'<a href="/blog/?tag={l}" class="tag">{l}</a>' for l in labels)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | 오늘장부 블로그</title>
  <meta name="description" content="{meta}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{meta}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{BASE_URL}/blog/posts/{slug}.html">
  <link rel="canonical" href="{BASE_URL}/blog/posts/{slug}.html">
  <link rel="icon" href="/icons/icon-192.png">
  <!-- Google AdSense -->
  <!-- <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX" crossorigin="anonymous"></script> -->
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans KR', sans-serif; background: #f8f9fa; color: #1a1a1a; line-height: 1.7; }}

    header {{ background: #fff; border-bottom: 1px solid #eee; position: sticky; top: 0; z-index: 100; }}
    .header-inner {{ max-width: 1100px; margin: 0 auto; padding: 0 20px; height: 60px; display: flex; align-items: center; justify-content: space-between; }}
    .logo {{ display: flex; align-items: center; gap: 8px; text-decoration: none; }}
    .logo-icon {{ width: 32px; height: 32px; background: #FF6B35; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: 900; font-size: 16px; }}
    .logo-text {{ font-size: 18px; font-weight: 800; color: #FF6B35; }}
    .logo-sub {{ font-size: 13px; color: #888; margin-left: 4px; }}
    .header-cta {{ background: #FF6B35; color: white; border: none; padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; text-decoration: none; }}

    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px; display: grid; grid-template-columns: 1fr 300px; gap: 40px; }}
    @media (max-width: 768px) {{ .wrap {{ grid-template-columns: 1fr; }} .sidebar {{ display: none; }} }}

    article {{ background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
    .article-head {{ padding: 32px 32px 24px; border-bottom: 1px solid #f0f0f0; }}
    .article-cat {{ font-size: 12px; font-weight: 700; color: #FF6B35; text-transform: uppercase; margin-bottom: 12px; }}
    .article-cat a {{ color: #FF6B35; text-decoration: none; }}
    .article-title {{ font-size: clamp(20px, 4vw, 28px); font-weight: 900; line-height: 1.4; color: #1a1a1a; margin-bottom: 16px; }}
    .article-meta {{ font-size: 13px; color: #aaa; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }}
    .article-body {{ padding: 32px; }}
    .article-body h2 {{ font-size: 20px; font-weight: 800; color: #1a1a1a; margin: 32px 0 14px; padding-bottom: 8px; border-bottom: 2px solid #FF6B35; }}
    .article-body h3 {{ font-size: 16px; font-weight: 700; color: #333; margin: 20px 0 10px; }}
    .article-body p {{ margin-bottom: 14px; color: #333; font-size: 15px; }}
    .article-body ul, .article-body ol {{ padding-left: 20px; margin-bottom: 14px; }}
    .article-body li {{ margin-bottom: 6px; color: #333; font-size: 15px; }}
    .article-body table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
    .article-body th {{ background: #FF6B35; color: white; padding: 10px 14px; text-align: left; }}
    .article-body td {{ padding: 10px 14px; border-bottom: 1px solid #f0f0f0; }}
    .article-body tr:nth-child(even) td {{ background: #fff8f5; }}
    .article-body img {{ width: 100%; border-radius: 12px; margin: 16px 0; }}
    .article-body strong {{ color: #1a1a1a; }}
    .article-body blockquote {{ background: #fff8f5; border-left: 4px solid #FF6B35; padding: 16px 20px; border-radius: 0 12px 12px 0; margin: 16px 0; font-style: italic; color: #555; }}

    .tags {{ padding: 20px 32px; border-top: 1px solid #f0f0f0; display: flex; gap: 8px; flex-wrap: wrap; }}
    .tag {{ background: #fff3ee; color: #FF6B35; border-radius: 20px; padding: 5px 12px; font-size: 12px; font-weight: 600; text-decoration: none; }}
    .tag:hover {{ background: #FF6B35; color: white; }}

    .ad-slot {{ background: #f0f0f0; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #bbb; font-size: 12px; min-height: 90px; margin: 24px 0; }}

    .cta-box {{ background: linear-gradient(135deg, #FF6B35, #ff8c42); border-radius: 20px; padding: 32px; text-align: center; color: white; margin-top: 24px; }}
    .cta-box h3 {{ font-size: 22px; font-weight: 900; margin-bottom: 10px; }}
    .cta-box p {{ font-size: 14px; opacity: 0.9; line-height: 1.6; margin-bottom: 20px; }}
    .cta-box a {{ background: white; color: #FF6B35; border-radius: 12px; padding: 13px 28px; font-weight: 800; font-size: 15px; text-decoration: none; display: inline-block; }}

    .nav-links {{ display: flex; gap: 16px; margin-top: 24px; }}
    .nav-back {{ color: #FF6B35; text-decoration: none; font-size: 14px; font-weight: 600; }}
    .nav-back::before {{ content: '← '; }}

    .sidebar-cta {{ background: linear-gradient(135deg, #FF6B35, #ff8c42); color: white; border-radius: 16px; padding: 24px; text-align: center; position: sticky; top: 80px; }}
    .sidebar-cta h3 {{ font-size: 16px; font-weight: 900; margin-bottom: 8px; }}
    .sidebar-cta p {{ font-size: 13px; opacity: 0.9; line-height: 1.5; margin-bottom: 16px; }}
    .sidebar-cta a {{ background: white; color: #FF6B35; border-radius: 8px; padding: 10px 20px; font-weight: 700; font-size: 14px; text-decoration: none; display: inline-block; }}

    footer {{ background: #1a1a1a; color: #888; padding: 40px 20px; margin-top: 60px; }}
    .footer-inner {{ max-width: 1100px; margin: 0 auto; }}
    .footer-links {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }}
    .footer-links a {{ color: #888; text-decoration: none; font-size: 13px; }}
    .footer-copy {{ font-size: 12px; }}
  </style>
</head>
<body>

<header>
  <div class="header-inner">
    <a href="/" class="logo">
      <div class="logo-icon">장</div>
      <span class="logo-text">오늘장부</span>
      <span class="logo-sub">블로그</span>
    </a>
    <a href="/" class="header-cta">무료로 시작하기</a>
  </div>
</header>

<div class="wrap">
  <main>
    <div class="nav-links">
      <a href="/blog/" class="nav-back">블로그 목록으로</a>
    </div>

    <!-- 상단 광고 -->
    <div class="ad-slot">광고 영역 (AdSense 승인 후 활성화)</div>

    <article>
      <div class="article-head">
        <div class="article-cat"><a href="/blog/">{category}</a></div>
        <h1 class="article-title">{title}</h1>
        <div class="article-meta">
          <span>오늘장부 편집팀</span>
          <span>{today}</span>
        </div>
      </div>

      <div class="article-body">
        {content}
      </div>

      <div class="tags">
        {tags_html}
      </div>
    </article>

    <!-- 본문 하단 광고 -->
    <div class="ad-slot">광고 영역 (AdSense 승인 후 활성화)</div>

    <div class="cta-box">
      <h3>매일 매출 기록, 30초면 끝!</h3>
      <p>카드·현금·네이버페이·카카오페이<br>8가지 결제수단을 한 화면에서 입력<br>부가세 예상액도 자동으로 계산해드려요</p>
      <a href="/">지금 무료로 시작하기 →</a>
    </div>
  </main>

  <aside class="sidebar">
    <div class="sidebar-cta">
      <h3>매일 매출 기록,<br>30초면 끝!</h3>
      <p>카드·현금·배달앱 한 번에<br>부가세 예상액도 자동 계산</p>
      <a href="/">무료로 시작하기</a>
    </div>
  </aside>
</div>

<footer>
  <div class="footer-inner">
    <div class="footer-links">
      <a href="/">서비스 홈</a>
      <a href="/blog/">블로그</a>
      <a href="/privacy">개인정보처리방침</a>
      <a href="/terms">이용약관</a>
    </div>
    <div class="footer-copy">© 2026 오늘장부. All rights reserved.</div>
  </div>
</footer>

</body>
</html>"""


# ── 매니페스트 읽기/쓰기 ─────────────────────────────────────────

def _load_manifest() -> list:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def _save_manifest(entries: list):
    MANIFEST.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 사이트맵 갱신 ────────────────────────────────────────────────

def _update_sitemap(entries: list):
    today = date.today().isoformat()
    urls = [f"""  <url>
    <loc>{BASE_URL}/</loc>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{BASE_URL}/login</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>{BASE_URL}/blog/</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>"""]

    for e in entries:
        urls.append(f"""  <url>
    <loc>{BASE_URL}/blog/posts/{e['slug']}.html</loc>
    <lastmod>{e.get('date', today)}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>""")

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += "\n".join(urls)
    xml += "\n</urlset>\n"
    SITEMAP.write_text(xml, encoding="utf-8")
    print(f"  사이트맵 갱신: {len(entries)}개 포스트")


# ── 로그 ────────────────────────────────────────────────────────

def _log(entries: list):
    LOG_PATH.parent.mkdir(exist_ok=True)
    existing = []
    if LOG_PATH.exists():
        try:
            existing = json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing.extend(entries)
    LOG_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 썸네일 추출 ─────────────────────────────────────────────────

def _extract_thumb(html: str) -> str | None:
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html)
    return m.group(1) if m else None


# ── 공개 API ─────────────────────────────────────────────────────

class StaticBlogPublisher:
    def __init__(self):
        POSTS_DIR.mkdir(parents=True, exist_ok=True)

    def publish(self, post: dict) -> dict | None:
        title    = post.get("title", "")
        keyword  = post.get("source_keyword", title)
        orig_cat = post.get("category", "라이프스타일")
        category = resolve_category(keyword, orig_cat)

        raw_slug = slugify(title, allow_unicode=False) or slugify(keyword, allow_unicode=False)
        slug     = raw_slug[:80] if raw_slug else f"post-{date.today().isoformat()}"

        html = _post_html(post, slug, category)
        out  = POSTS_DIR / f"{slug}.html"
        out.write_text(html, encoding="utf-8")

        thumb = _extract_thumb(post.get("html_content", ""))
        entry = {
            "slug":        slug,
            "title":       title,
            "description": post.get("meta_description", ""),
            "category":    category,
            "date":        date.today().isoformat(),
            "thumb":       thumb,
            "tags":        post.get("labels", []),
        }

        manifest = _load_manifest()
        if not any(e["slug"] == slug for e in manifest):
            manifest.append(entry)
            _save_manifest(manifest)
            _update_sitemap(manifest)

        print(f"  [정적발행] {out.name} ({category})")
        return entry

    def publish_batch(self, posts: list) -> list:
        results = []
        for p in posts:
            r = self.publish(p)
            if r:
                results.append(r)
        if results:
            _log([{"title": r["title"], "slug": r["slug"], "date": r["date"]} for r in results])
        return results

    @staticmethod
    def get_stats() -> dict:
        manifest = _load_manifest()
        return {"total": len(manifest), "last": manifest[-1]["date"] if manifest else None}


if __name__ == "__main__":
    print(f"Blog dir : {BLOG_DIR}")
    print(f"Posts dir: {POSTS_DIR}")
    print(f"Manifest : {MANIFEST}")
    stats = StaticBlogPublisher.get_stats()
    print(f"현재 발행 수: {stats['total']}개  마지막: {stats['last']}")
