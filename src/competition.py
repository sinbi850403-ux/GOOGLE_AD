"""키워드 경쟁 강도 측정 (구글 블로그용).

왜 필요한가:
지금까지는 트렌드 급상승어나 고정 풀에서 순서대로 골랐다. 그러면 검색량이
얼마인지, 이미 쓴 사람이 몇인지 모르는 채로 쓴다. 이길 수 없는 자리에
쓰면 같은 노력으로 아무도 안 온다.

이 블로그는 구글 검색이 대상이다:
공급(경쟁)은 구글에서 재야 맞다. Custom Search API 가 설정돼 있으면 구글
결과 수를 쓰고, 없으면 네이버 블로그 문서수로 대신한다. 후자는 한국어
주제의 포화도를 보는 대용치일 뿐 구글 경쟁을 그대로 반영하지 않는다.

무엇을 재는가:
두 가지를 같이 본다. 하나만 보면 틀린다.

  공급 — 블로그 문서수(검색 API 의 total). 그 키워드로 이미 쓰인 글 수.
  수요 — 상대 검색량(데이터랩). 사람들이 실제로 찾는 정도.

문서수만 보면 "아무도 안 찾는데 경쟁도 없는" 키워드를 고르게 된다. 문서수가
310개여도 검색량이 0이면 써봐야 아무도 안 온다. 수요를 공급으로 나눈 값이
높은 쪽, 즉 찾는 사람은 있는데 쓴 사람은 적은 자리를 고른다.

두 API 모두 같은 openapi 자격증명(NAVER_CLIENT_ID/SECRET)을 쓴다.

HTML 을 긁지 않는 이유:
네이버 블로그 검색 화면에서 총 문서수 표기가 사라졌고, 결과 제목은 난독화된
클래스명 안에 들어 있어 마크업이 바뀌면 조용히 깨진다. 공식 API 는 total 을
그대로 주고 스펙이 안정적이다.

키가 없으면:
측정을 건너뛰고 기존 순환 방식대로 고른다. 경쟁 측정은 어디까지나 보조이며
이것 때문에 발행이 멈춰서는 안 된다.
"""

import datetime
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

# 2026-07-31 부로 개발자센터에서 검색·데이터랩 API 신규 발급이 중단됐다.
# 기존 키는 2027-06-30 까지만 동작하고, 신규 발급은 NAVER API Hub 에서만 된다.
# 도메인과 인증 헤더가 다르므로 양쪽을 다 지원한다. HUB 를 먼저 본다.
HUB_SEARCH_URL = "https://naverapihub.apigw.ntruss.com/search/v1/blog"
HUB_TREND_URL = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
API_URL = "https://openapi.naver.com/v1/search/blog.json"
DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"
CSE_URL = "https://www.googleapis.com/customsearch/v1"
TIMEOUT_SEC = 6

# 데이터랩은 한 번에 최대 5개 그룹까지 받는다.
DATALAB_MAX_GROUPS = 5

# 같은 키워드를 하루에 두 번 물어볼 일이 없도록 프로세스 안에서만 기억한다.
# 하루 호출이 10회 미만이라 영속 캐시까지는 필요 없다(API 한도는 일 25,000회).
_memo: dict[str, int | None] = {}

_WARNED_NO_KEY = False


def hub_credentials() -> tuple[str, str] | None:
    """NAVER API Hub(네이버 클라우드) 키. 신규 발급은 이쪽뿐이다."""
    kid = os.environ.get("NCP_API_KEY_ID", "").strip()
    key = os.environ.get("NCP_API_KEY", "").strip()
    return (kid, key) if kid and key else None


def legacy_credentials() -> tuple[str, str] | None:
    """개발자센터 키. 2027-06-30 이후로는 동작하지 않는다."""
    cid = os.environ.get("NAVER_CLIENT_ID", "").strip()
    secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    return (cid, secret) if cid and secret else None


def credentials() -> tuple[str, str] | None:
    """쓸 수 있는 키가 있는지. HUB 를 먼저 본다."""
    return hub_credentials() or legacy_credentials()


def _endpoint(kind: str) -> tuple[str, dict] | None:
    """(주소, 인증 헤더). kind 는 'search' 또는 'trend'."""
    hub = hub_credentials()
    if hub:
        kid, key = hub
        url = HUB_SEARCH_URL if kind == "search" else HUB_TREND_URL
        return url, {"X-NCP-APIGW-API-KEY-ID": kid, "X-NCP-APIGW-API-KEY": key}
    legacy = legacy_credentials()
    if legacy:
        cid, secret = legacy
        url = API_URL if kind == "search" else DATALAB_URL
        return url, {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}
    return None


def _http_error_detail(e) -> str:
    """네이버가 본문에 실어 보내는 원인 코드를 꺼낸다.

    상태 코드만으로는 키가 틀린 건지, 앱에 그 API 가 추가돼 있지 않은 건지
    구분할 수 없다. 네이버는 errorCode/errorMessage 를 본문에 준다.
    """
    try:
        body = e.read().decode("utf-8", "replace")[:300]
    except Exception:
        return ""
    try:
        data = json.loads(body)
    except Exception:
        return f" {body}"

    # 개발자센터는 {errorCode, errorMessage}, HUB 는 {error:{errorCode, message, details}}
    inner = data.get("error") if isinstance(data.get("error"), dict) else data
    code = inner.get("errorCode") or ""
    msg = inner.get("errorMessage") or inner.get("message") or ""
    details = inner.get("details") or ""
    out = f" [{code}] {msg}".rstrip()
    if details and details not in msg:
        out += f" — {details}"
    return out


def _call_api(query: str) -> int | None:
    """블로그 문서수를 돌려준다. 못 재면 None."""
    ep = _endpoint("search")
    if not ep:
        return None
    base, headers = ep

    req = urllib.request.Request(
        f"{base}?query={urllib.parse.quote(query)}&display=1", headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        total = data.get("total")
        return int(total) if isinstance(total, (int, float)) else None
    except urllib.error.HTTPError as e:
        # 401/403 은 키 문제, 429 는 한도. 어느 쪽이든 오늘은 측정을 포기한다.
        logger.warning(
            f"[경쟁] 검색 API 오류 {e.code}{_http_error_detail(e)} — '{query}' 측정 건너뜀"
        )
        return None
    except Exception as e:
        logger.warning(f"[경쟁] 측정 실패 ({type(e).__name__}) — '{query}' 건너뜀")
        return None


def _call_datalab(keywords: list[str]) -> dict[str, float] | None:
    """키워드별 상대 검색량. 못 재면 None.

    데이터랩은 절대 검색량을 주지 않고 요청 안에서 최댓값이 100이 되도록
    정규화한 비율을 준다. 그래서 후보들을 한 번에 넣어 서로 비교해야 의미가
    있다. 어차피 후보끼리만 비교하므로 절대값은 필요 없다.
    """
    ep = _endpoint("trend")
    if not ep or not keywords:
        return None
    base, headers = ep

    end = datetime.date.today()
    start = end - datetime.timedelta(days=30)
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "timeUnit": "week",
        "keywordGroups": [
            {"groupName": k, "keywords": [k]} for k in keywords[:DATALAB_MAX_GROUPS]
        ],
    }
    req = urllib.request.Request(
        base,
        data=json.dumps(body).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning(
            f"[수요] 데이터랩 오류 {e.code}{_http_error_detail(e)} — 검색량 측정 건너뜀"
        )
        return None
    except Exception as e:
        logger.warning(f"[수요] 데이터랩 실패 ({type(e).__name__}) — 검색량 측정 건너뜀")
        return None

    out = {}
    for group in data.get("results", []):
        points = [p.get("ratio", 0) for p in group.get("data", [])]
        # 주간 비율의 평균. 한 주만 튄 키워드보다 꾸준한 쪽을 높게 본다.
        out[group.get("title", "")] = (sum(points) / len(points)) if points else 0.0
    return out or None


def relative_demand(keywords: list[str], *, fetch=None) -> dict[str, float] | None:
    """후보들의 상대 검색량. 측정 불가면 None."""
    return (fetch or _call_datalab)(keywords)


def _google_credentials() -> tuple[str, str] | None:
    key = os.environ.get("GOOGLE_CSE_KEY", "").strip()
    cx = os.environ.get("GOOGLE_CSE_ID", "").strip()
    return (key, cx) if key and cx else None


def _call_google(query: str) -> int | None:
    """구글 검색 결과 수. 이 블로그가 실제로 경쟁하는 곳이다."""
    creds = _google_credentials()
    if not creds:
        return None
    key, cx = creds
    url = (
        f"{CSE_URL}?key={urllib.parse.quote(key)}&cx={urllib.parse.quote(cx)}"
        f"&q={urllib.parse.quote(query)}&num=1"
    )
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        total = data.get("searchInformation", {}).get("totalResults")
        return int(total) if total is not None else None
    except urllib.error.HTTPError as e:
        logger.warning(f"[경쟁] 구글 CSE 오류 {e.code}{_http_error_detail(e)} — '{query}' 건너뜀")
        return None
    except Exception as e:
        logger.warning(f"[경쟁] 구글 CSE 실패 ({type(e).__name__}) — '{query}' 건너뜀")
        return None


def _supply(query: str) -> int | None:
    """공급(경쟁) 측정. 구글이 되면 구글, 아니면 네이버 문서수로 대신한다."""
    if _google_credentials():
        return _call_google(query)
    return _call_api(query)


def document_count(query: str, *, fetch=None) -> int | None:
    """키워드의 블로그 문서수. 측정 불가면 None.

    fetch 를 넘기면 그것으로 대체한다(테스트용).
    """
    if query in _memo:
        return _memo[query]
    value = (fetch or _supply)(query)
    _memo[query] = value
    return value


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[가-힣A-Za-z0-9]+", text or "") if len(t) > 1}


def _matches(token: str, pool: set[str]) -> bool:
    """어미만 다른 같은 말을 같게 본다.

    "계산" 과 "계산하는", "입금" 과 "입금일" 이 다른 단어로 잡히면 같은 주제를
    새 주제로 착각한다. 한쪽이 다른 쪽으로 시작하면 같은 말로 취급한다.
    """
    if token in pool:
        return True
    return any(
        len(other) > 1 and (other.startswith(token) or token.startswith(other))
        for other in pool
    )


def already_covered(keyword: str, recent_titles: list[str]) -> bool:
    """최근 발행한 제목이 이 키워드를 사실상 다 담고 있으면 True.

    제목은 LLM 이 키워드를 부풀려 만들므로 키워드 단어가 제목에 거의 다
    들어 있으면 같은 주제로 본다.
    """
    kt = _tokens(keyword)
    if not kt:
        return False
    for title in recent_titles:
        tt = _tokens(title)
        hit = sum(1 for t in kt if _matches(t, tt))
        if hit / len(kt) >= 0.8:
            return True
    return False


def pick_best(candidates: list[str], recent_titles: list[str] | None = None,
              *, docs_fetch=None, demand_fetch=None
              ) -> tuple[str, list[tuple[str, int | None, float | None]]]:
    """후보 중 "찾는 사람은 있는데 쓴 사람은 적은" 키워드를 고른다.

    점수 = 상대 검색량 / 문서수. 높을수록 빈자리다.

    절대 기준값을 두지 않고 후보끼리만 비교한다. "문서수 몇 이하가 쉽다" 는
    기준은 분야마다 다르고 지금 근거가 없다. 상대 비교면 보정값이 필요 없고
    후보가 전부 나빠도 어쨌든 하나는 고르므로 발행이 멈추지 않는다.

    한쪽만 측정되면 그 한쪽으로 고른다. 둘 다 안 되면 순환 순서를 지킨다.
    경쟁 측정은 보조이며 이것 때문에 발행이 멈춰서는 안 된다.

    돌려주는 두 번째 값은 (키워드, 문서수, 검색량) 목록이다. 로그로 남겨 두면
    나중에 실제 수치를 보고 기준을 잡을 수 있다.
    """
    if not candidates:
        raise ValueError("후보가 비어 있습니다")

    recent = recent_titles or []
    fresh = [k for k in candidates if not already_covered(k, recent)]
    if not fresh:
        logger.info("[경쟁] 후보가 모두 최근 주제와 겹침 — 순환 순서대로 진행")
        fresh = candidates

    global _WARNED_NO_KEY
    if not credentials() and not _google_credentials():
        if not _WARNED_NO_KEY:
            logger.info(
                "[경쟁] 네이버 API 키가 없어 경쟁 측정을 건너뜁니다. "
                "NCP_API_KEY_ID/NCP_API_KEY 를 설정하세요 "
                "(개발자센터 신규 발급은 2026-07-31 종료, NAVER API Hub 로 이관)"
            )
            _WARNED_NO_KEY = True
        return fresh[0], []

    docs = {k: document_count(k, fetch=docs_fetch) for k in fresh}
    demand = relative_demand(fresh, fetch=demand_fetch) or {}
    measured = [(k, docs.get(k), demand.get(k)) for k in fresh]

    def score(k):
        d, q = docs.get(k), demand.get(k)
        if d is not None and q is not None:
            # 문서가 0건이어도 나눌 수 있게 바닥을 1로 둔다.
            return q / max(d, 1)
        return None

    scored = [(k, score(k)) for k in fresh]
    usable = [(k, v) for k, v in scored if v is not None]
    if usable:
        best = max(usable, key=lambda x: (x[1], -fresh.index(x[0])))[0]
        return best, measured

    # 수요만 측정된 경우 — 많이 찾는 쪽
    only_demand = [(k, demand[k]) for k in fresh if k in demand]
    if only_demand:
        logger.warning("[경쟁] 문서수를 못 재 검색량만으로 고릅니다")
        return max(only_demand, key=lambda x: (x[1], -fresh.index(x[0])))[0], measured

    # 공급만 측정된 경우 — 적게 쓰인 쪽
    only_docs = [(k, docs[k]) for k in fresh if docs.get(k) is not None]
    if only_docs:
        logger.warning("[경쟁] 검색량을 못 재 문서수만으로 고릅니다")
        return min(only_docs, key=lambda x: (x[1], fresh.index(x[0])))[0], measured

    logger.warning("[경쟁] 후보를 하나도 측정하지 못했습니다 — 순환 순서대로 진행")
    return fresh[0], measured
