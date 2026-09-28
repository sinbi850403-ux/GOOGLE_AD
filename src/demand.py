"""검색 수요 측정 — 자동완성 기반. API 키가 필요 없다.

왜 이 방법인가:
네이버는 2026-07-31 부로 개발자센터의 검색·데이터랩 신규 발급을 중단했고,
새로 받으려면 네이버 클라우드 가입이 필요하다. 그 절차 없이 수요를 재려고
자동완성을 쓴다.

무엇을 재는가:
자동완성에 뜨는 문구는 사람들이 실제로 치는 검색어다. 네이버도 구글도
일정 횟수 이상 검색된 것만 제안한다. 그래서 제안 개수가 수요의 하한선이 된다.

실측으로 확인한 구분력(2026-09-28):
  배달앱 수수료        8개    주휴수당 계산      10개
  카드매출 입금일      4개    간이과세자 부가세  10개
  배달앱 실입금액 계산  0개    카드수수료 회계처리 0개
수요가 있는 것과 없는 것이 4~10 대 0 으로 갈린다.

더 중요한 쓸모:
제안 목록 자체가 "검색되는 것이 확인된 롱테일"이다. 예를 들어 '카드매출 입금일'
을 넣으면 '카드매출 입금일 보는법', '카드매출 입금일 추석' 이 나온다. 머리
키워드보다 구체적이라 경쟁이 얕으면서, 네이버가 제안했으니 수요는 증명돼 있다.
거르는 데 쓰기보다 후보를 캐는 데 쓰는 편이 낫다.

한계:
제안 개수는 순위나 절대 검색량이 아니다. 0개는 "아무도 안 찾는다"가 아니라
"제안 기준 미만"이라는 뜻이다. 순서는 대체로 검색량 순이라 앞쪽일수록 경쟁도
세다고 본다.
"""

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

NAVER_AC = "https://ac.search.naver.com/nx/ac"
GOOGLE_AC = "https://suggestqueries.google.com/complete/search"
TIMEOUT_SEC = 6
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)

# 이 봇은 Blogger(구글)에 쓴다. 경쟁하는 곳이 구글이므로 구글 자동완성을 본다.
DEFAULT_SOURCE = "google"

# 연속 호출 사이 최소 간격. 자동완성은 공개 엔드포인트라 예의를 지킨다.
_MIN_INTERVAL = 0.25
_last_call = 0.0
_memo: dict[tuple[str, str], list[str]] = {}


def _throttle():
    global _last_call
    gap = time.time() - _last_call
    if gap < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - gap)
    _last_call = time.time()


def _fetch(url: str) -> bytes | None:
    _throttle()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            return resp.read()
    except Exception as e:
        logger.warning(f"[수요] 자동완성 실패 ({type(e).__name__})")
        return None


def _naver(query: str) -> list[str]:
    url = (
        f"{NAVER_AC}?q={urllib.parse.quote(query)}"
        "&st=100&r_format=json&r_enc=UTF-8&q_enc=UTF-8&frm=nv"
    )
    raw = _fetch(url)
    if not raw:
        return []
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return []
    return [x[0] for group in (data.get("items") or []) for x in group if x and x[0]]


def _google(query: str) -> list[str]:
    url = f"{GOOGLE_AC}?client=firefox&hl=ko&gl=kr&q={urllib.parse.quote(query)}"
    raw = _fetch(url)
    if not raw:
        return []
    try:
        return json.loads(raw.decode("utf-8", "replace"))[1]
    except Exception:
        return []


def suggestions(query: str, source: str = DEFAULT_SOURCE) -> list[str]:
    """자동완성 제안 목록. 실패하면 빈 목록."""
    key = (source, query)
    if key in _memo:
        return _memo[key]
    out = (_google if source == "google" else _naver)(query)
    _memo[key] = out
    return out


def demand(query: str, source: str = DEFAULT_SOURCE) -> int:
    """수요 하한선. 제안이 많을수록 찾는 사람이 많다.

    긴 제목이면 앞 단어만 남겨 다시 묻는다(topic_suggestions 설명 참고).
    """
    return len(topic_suggestions(query, source)[0])


def _tokens(s: str) -> list[str]:
    return re.findall(r"[가-힣A-Za-z0-9]+", s or "")


def _words(s: str) -> int:
    return len(_tokens(s))


# 자동완성은 커뮤니티·불법 유통 관련 꼬리말을 자주 물고 온다. 글 주제로 쓸 수 없다.
_NOISE = ("디시", "더쿠", "인스티즈", "나무위키", "다시보기", "토렌트", "블라인드")


def _norm_for_prefix(s: str) -> str:
    """띄어쓰기를 지워 '카드매출 입금일' 과 '카드 매출 입금일' 을 같게 본다."""
    return re.sub(r"\s+", "", s or "")


def _clean(items: list[str]) -> list[str]:
    return [x for x in items if not any(n in x for n in _NOISE)]


def topic_suggestions(phrase: str, source: str = DEFAULT_SOURCE) -> tuple[list[str], str]:
    """주제 문구로 제안을 찾는다. (제안 목록, 실제로 물어본 문구)

    키워드 풀에 "카드 매출 현금 매출 통합 관리 노하우" 처럼 검색어가 아니라
    글 제목이 들어 있는 경우가 있다. 아무도 그렇게 검색하지 않으니 제안이
    0개로 나온다. 그때는 앞쪽 단어만 남겨 점점 줄여가며 다시 묻는다.
    실측상 3단어까지 줄이면 대체로 잡힌다.
    """
    direct = _clean(suggestions(phrase, source))
    if direct:
        return direct, phrase
    words = _tokens(phrase)
    # 2단어까지 줄이는 것은 원문이 짧을 때만 허용한다. 긴 문구를 2단어로
    # 자르면 맥락이 날아가 엉뚱한 주제가 붙는다. 실제로 "수수료 우대 받는
    # 연매출 기준 정리" 가 "수수료 우대" 로 잘려 "수수료 우대 증권사" 가
    # 나왔다. 소상공인 카드수수료 글에 증권사 이야기가 붙을 뻔했다.
    steps = (4, 3) if len(words) > 4 else (4, 3, 2)
    for n in steps:
        if len(words) <= n:
            continue
        seed = " ".join(words[:n])
        got = _clean(suggestions(seed, source))
        if got:
            return got, seed
    return [], phrase


def best_variant(base: str, is_covered=None, source: str = DEFAULT_SOURCE
                 ) -> tuple[str, int, list[str]]:
    """base 를 자동완성으로 넓혀 쓸 만한 롱테일 하나를 고른다.

    돌려주는 값은 (고른 문구, 제안 개수, 제안 전체).

    고르는 기준: 제안 중 base 보다 단어가 많은 첫 번째. 자동완성은 대체로
    검색량 순이라 앞쪽일수록 수요가 크고, base 보다 길면 그만큼 구체적이라
    경쟁이 얕다. 둘을 같이 만족하는 지점이 목록 앞쪽의 긴 문구다.

    쓸 만한 것이 없으면 base 를 그대로 돌려준다. 제안이 0개면 수요가 낮다는
    뜻이므로 호출한 쪽이 그 값을 보고 판단하면 된다.
    """
    sugg, _ = topic_suggestions(base, source)

    # base 뒤에 말이 붙은 것만 받는다. 앞이나 중간이 바뀌면 다른 주제다.
    #
    # 자동완성은 모든 사용자층의 검색어라 우리 독자와 무관한 쪽으로 잘 샌다.
    # 실제로 '근로시간 단축' 이 '육아기 근로시간 단축' 으로, '현금 결제 유도' 가
    # '현금 결제 유도 레전드' 로, 카드수수료 주제가 증권사 이야기로 붙었다.
    # 원래 키워드는 사람이 독자를 보고 고른 것이므로 그 맥락을 깨지 않는다.
    head = _norm_for_prefix(base)
    for cand in sugg:
        if not _norm_for_prefix(cand).startswith(head):
            continue
        if _words(cand) <= _words(base):
            continue  # 같거나 짧다 — 머리 키워드라 경쟁만 세다
        if is_covered and is_covered(cand):
            continue
        return cand, len(sugg), sugg
    return base, len(sugg), sugg
