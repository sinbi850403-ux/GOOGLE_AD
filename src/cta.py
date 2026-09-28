"""글 주제에 맞는 CTA 를 만든다.

왜 필요한가:
이 블로그 글에는 지금까지 CTA 가 전혀 없었다. 읽고 나면 그걸로 끝이라
트래픽이 생겨도 아무 데로도 이어지지 않았다.

"돈 되는 키워드" 의 마지막 조건은 읽고 나서 다음 행동을 하느냐다. 그러려면
글이 끝나는 지점에서 독자가 방금 읽은 그 일을 실제로 해볼 수 있어야 한다.
카드수수료 글을 읽었으면 내 수수료를 계산해 보는 것이 다음 행동이다.

무엇을 하는가:
키워드와 카테고리를 보고 맞는 계산기로 보낸다. 맞는 계산기가 없으면 앱으로
보낸다. 링크에 utm 을 붙여 어느 글에서 넘어왔는지 GA4 에서 구분할 수 있게 한다.
이걸 붙여야 "다음 행동" 이 측정 가능한 값이 된다.

링크는 하나만 둔다:
글 하나에 계산기 링크 하나. 여러 개를 흩뿌리면 어느 것도 눌리지 않는다.
"""

import re
import urllib.parse

SITE = "https://오늘장부.kr"

# 계산기별 이동 조건. 순서가 곧 우선순위다.
#   words    — 주제나 제목에 이 말이 있으면 해당 계산기
#   category — 위에서 못 정했을 때 쓰는 카테고리
_TOOLS = [
    {
        "slug": "card-fee-calculator",
        "label": "카드수수료 계산기",
        "line": "내 연매출이 우대수수료율 구간에 드는지, 더 내고 있다면 얼마를 돌려받을 수 있는지 계산해 볼 수 있습니다.",
        # "정산 주기" 처럼 카드에도 배달앱에도 걸리는 말은 넣지 않는다.
        # "배민 정산 주기" 가 카드 계산기로 새는 원인이었다.
        "words": ["카드수수료", "우대수수료", "가맹점", "단말기", "밴사", "간편결제",
                  "카드매출", "카드사 정산", "카드 정산", "체크카드", "결제 취소",
                  "매출전표", "선정산"],
        "category": "카드수수료",
    },
    {
        "slug": "delivery-fee-calculator",
        "label": "배달앱 수수료 계산기",
        "line": "중개수수료와 배달비, 결제수수료를 빼고 실제로 통장에 들어오는 금액을 계산해 볼 수 있습니다.",
        "words": ["배달앱", "배민", "쿠팡이츠", "요기요", "중개수수료", "실입금",
                  "배달비", "포장 주문", "배달 대행"],
        "category": "배달앱",
    },
    {
        "slug": "vat-simplified-calculator",
        "label": "간이과세자 부가세 계산기",
        "line": "업종별 부가가치율을 적용해 이번에 낼 부가세가 대략 얼마인지 계산해 볼 수 있습니다.",
        "words": ["간이과세", "부가세", "부가가치율", "매입세액", "일반과세",
                  "세금계산서", "면세사업자", "홈택스"],
        "category": "부가세",
    },
]

# 맞는 계산기가 없을 때. 계산기가 없는 분야(직원관리·사업자등록 등)가 여기로 온다.
_APP = {
    "slug": "",
    "label": "오늘장부",
    "line": "카드·현금·배달앱 매출을 한 화면에 기록하면 부가세 예상액까지 자동으로 계산됩니다. 무료입니다.",
}


def _norm(text: str) -> str:
    """띄어쓰기를 지워 '카드 수수료' 와 '카드수수료' 를 같게 본다."""
    return re.sub(r"\s+", "", text or "")


def choose_tool(topic: str, title: str = "", category: str = "") -> dict:
    """주제에 맞는 도구를 고른다. 없으면 앱."""
    haystack = _norm(f"{topic} {title}")

    # 첫 매칭이 아니라 가장 많이 걸린 쪽을 고른다. 한 단어가 우연히 겹쳐
    # 엉뚱한 계산기로 새는 것을 막는다. 동점이면 목록 순서를 따른다.
    hits = [
        (sum(1 for w in tool["words"] if _norm(w) in haystack), -i, tool)
        for i, tool in enumerate(_TOOLS)
    ]
    best = max(hits, key=lambda x: (x[0], x[1]))
    if best[0] > 0:
        return best[2]

    if category:
        for tool in _TOOLS:
            if tool["category"] == category:
                return tool
    return _APP


def _url(tool: dict, topic: str) -> str:
    """utm 을 붙인 링크. 어느 글에서 넘어왔는지 GA4 에서 구분하려는 것이다."""
    path = f"/tools/{tool['slug']}/" if tool["slug"] else "/"
    params = urllib.parse.urlencode(
        {
            "utm_source": "blogger",
            "utm_medium": "post",
            "utm_campaign": "cta",
            # 주제를 그대로 넣으면 한글이 길게 인코딩된다. 40자로 자른다.
            "utm_content": (topic or "")[:40],
        }
    )
    return f"{SITE}{path}?{params}"


def build(topic: str, title: str = "", category: str = "") -> tuple[str, str]:
    """(네이버용 텍스트, HTML) 두 벌을 돌려준다."""
    tool = choose_tool(topic, title, category)
    url = _url(tool, topic)

    if tool["slug"]:
        head = f"{tool['label']}로 직접 확인해 보세요"
    else:
        head = "매출 기록부터 시작해 보세요"

    text = f"\n\n{head}\n\n{tool['line']}\n\n{tool['label']}: {url}"
    html = (
        f"<p>{head}</p>"
        f"<p>{tool['line']}</p>"
        f'<p><a href="{url}">{tool["label"]} 바로가기</a></p>'
    )
    return text, html
