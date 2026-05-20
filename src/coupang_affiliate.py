"""
쿠팡파트너스 오픈 API 클라이언트
- 키워드로 상품 검색
- 블로그용 추천상품 HTML 섹션 생성
"""

import os
import hmac
import hashlib
import urllib.parse
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

COUPANG_ACCESS_KEY = os.getenv("COUPANG_ACCESS_KEY", "")
COUPANG_SECRET_KEY = os.getenv("COUPANG_SECRET_KEY", "")

BASE_URL    = "https://api-gateway.coupang.com"
SEARCH_PATH = "/v2/providers/affiliate_open_api/apis/openapi/products/search"


# ── HMAC 인증 ──────────────────────────────────────────────────

def _make_headers(method: str, path: str, query: str) -> dict:
    """쿠팡파트너스 HMAC-SHA256 인증 헤더 생성"""
    dt = datetime.now(timezone.utc).strftime("%y%m%d%H%M%S")
    message   = dt + method + path + query
    signature = hmac.new(
        COUPANG_SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "Authorization": (
            f"CEA algorithm=HmacSHA256, access-key={COUPANG_ACCESS_KEY},"
            f" signed-date={dt}, signature={signature}"
        ),
        "Content-Type": "application/json;charset=UTF-8",
    }


# ── 상품 검색 ──────────────────────────────────────────────────

def search_products(keyword: str, limit: int = 4) -> list[dict]:
    """
    키워드로 쿠팡 상품 검색
    반환: [{"name": ..., "price": ..., "image": ..., "url": ...}, ...]
    API 키 없으면 빈 리스트 반환 (AdSense만 동작)
    """
    if not COUPANG_ACCESS_KEY or not COUPANG_SECRET_KEY:
        return []

    params = {"keyword": keyword, "limit": limit, "subId": ""}
    query  = urllib.parse.urlencode(params)

    try:
        resp = requests.get(
            f"{BASE_URL}{SEARCH_PATH}?{query}",
            headers=_make_headers("GET", SEARCH_PATH, query),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        return [
            {
                "name":  item.get("productName", ""),
                "price": item.get("productPrice", 0),
                "image": item.get("productImage", ""),
                "url":   item.get("productUrl", ""),
            }
            for item in data.get("data", {}).get("productData", [])
            if item.get("productUrl")
        ]
    except Exception as e:
        print(f"  [쿠팡] 검색 실패: {e}")
        return []


# ── 블로그용 추천상품 HTML 섹션 ────────────────────────────────

def build_product_section(keyword: str) -> str:
    """
    키워드 관련 쿠팡 추천상품 HTML 반환.
    API 키 없거나 결과 없으면 빈 문자열 반환.
    """
    products = search_products(keyword, limit=4)
    if not products:
        return ""

    items_html = ""
    for p in products:
        price_str = f"{int(p['price']):,}원" if p["price"] else ""
        img_tag   = (
            f'<img src="{p["image"]}" alt="{p["name"]}"'
            ' style="width:100px;height:100px;object-fit:cover;border-radius:6px;">'
            if p["image"] else ""
        )
        items_html += f"""
    <li style="display:flex;gap:14px;align-items:center;padding:12px 0;border-bottom:1px solid #f0e0c0;">
      <a href="{p['url']}" target="_blank" rel="noopener sponsored">{img_tag}</a>
      <div>
        <a href="{p['url']}" target="_blank" rel="noopener sponsored"
           style="font-weight:bold;color:#c00500;text-decoration:none;font-size:15px;">{p['name']}</a>
        <p style="margin:5px 0 0;color:#555;font-size:14px;">{price_str}</p>
      </div>
    </li>"""

    return f"""
<section style="background:#fff9f0;border:2px solid #ffd9a0;border-radius:10px;padding:20px 24px;margin:36px 0;">
  <h2 style="color:#c00500;margin:0 0 12px;font-size:18px;">&#x1F6D2; 관련 추천 상품 (쿠팡)</h2>
  <ul style="list-style:none;padding:0;margin:0;">
    {items_html}
  </ul>
  <p style="font-size:11px;color:#aaa;margin:14px 0 0;">
    ※ 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.
  </p>
</section>"""


# ── 테스트 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    kw = "비트코인 하드웨어 지갑"
    print(f"검색: {kw}")
    products = search_products(kw)
    if products:
        for p in products:
            print(f"  - {p['name']} / {p['price']:,}원")
            print(f"    {p['url'][:60]}...")
    else:
        print("  결과 없음 (COUPANG_ACCESS_KEY / SECRET_KEY 를 .env 에 추가하세요)")
