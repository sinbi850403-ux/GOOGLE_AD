"""
급상승 검색어 → 실제로 쓸 만한 주제 선별

트렌드를 그대로 쓰면 안 된다. 한국 실시간 검색어는 대부분 인물·사건·언론사다
(실측: '이희진', '매일경제', '땅집고'). 여기에 AI 로 글을 자동 생성해 올리면

  - 실존 인물에 대한 확인되지 않은 서술이 나갈 수 있다
  - 애드센스는 사건·사고, 인물 콘텐츠에 제약이 있다
  - 무엇보다 구글이 말하는 스팸 블로그의 전형이 된다

애드센스는 계정 단위라 이 블로그가 걸리면 같은 계정의 다른 사이트까지
위험해진다. 그래서 검색량은 트렌드에서 가져오되, 주제는 '이슈에 붙은 실용
안내'로만 좁힌다.

  쓴다:   "○○ 예매 방법", "○○ 신청 자격", "○○ 환불 규정"
  안 쓴다: "○○씨 논란 정리", "○○ 사건 전말"

판정은 모델에 맡긴다. 사람 이름 패턴으로 거르는 방식은 '땅집고'(부동산 매체)나
'죠스'(영화) 같은 걸 구분하지 못한다.
"""

import os
import json
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
MODEL = "claude-haiku-4-5"

PROMPT = """급상승 검색어 목록이다. 이 중 **실용 안내 글**을 쓸 수 있는 것만 골라라.

{items}

[고르는 기준]
- 독자가 "어떻게 하는지" 알고 싶어할 만한 것만 고른다.
  예: 예매·신청·환불·가입·조회·계산·자격·일정 확인 방법
- 다음은 반드시 제외한다.
  · 특정 인물에 대한 것 (연예인, 정치인, 사건 당사자)
  · 사건·사고·논란·재판·부고
  · 언론사·기업 이름 자체 (그 회사 소식을 다루는 것)
  · 스포츠 경기 결과, 주가 등락 같은 지나가는 속보
- 애매하면 제외한다. 하나도 없으면 빈 배열을 반환한다.

[주제 만드는 법]
검색어 그대로가 아니라, 사람이 실제로 검색할 실용 질문 형태로 다듬어라.
  "미스터트롯" → "미스터트롯 투표 문자 보내는 방법"
  "청년내일저축" → "청년내일저축계좌 신청 자격과 기간"

JSON 배열만 출력하라. 설명 금지. 최대 {count}개.
[{{"keyword": "실용 주제", "why": "왜 실용 안내가 되는지 한 줄"}}]"""


def select_practical_topics(trends: list[dict], count: int = 3) -> list[dict]:
    """트렌드 목록에서 실용 안내로 쓸 만한 주제만 골라 돌려준다.

    고를 게 없으면 빈 목록. 호출 측은 기존 카테고리 풀로 넘어가면 된다 —
    억지로 쓰느니 평소 주제를 쓰는 편이 낫다.
    """
    if not trends or not CLAUDE_API_KEY:
        return []

    lines = []
    for t in trends:
        ctx = " / ".join(t.get("context", [])[:2])
        traffic = t.get("traffic", "")
        lines.append(f"- {t['keyword']} ({traffic}) {ctx}".rstrip())

    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": PROMPT.format(items="\n".join(lines), count=count),
            }],
        )
        raw = resp.content[0].text
        m = re.search(r"\[[\s\S]*\]", raw)
        if not m:
            print("  [트렌드 선별] 응답 형식 불일치 — 트렌드 사용 안 함")
            return []

        picked = json.loads(m.group(0))
    except Exception as e:
        print(f"  [트렌드 선별] 실패: {e} — 트렌드 사용 안 함")
        return []

    out = []
    for p in picked[:count]:
        kw = (p.get("keyword") or "").strip()
        if not kw:
            continue
        print(f"  [트렌드 채택] {kw}  ← {p.get('why', '')}")
        out.append({
            "keyword": kw,
            "score": 100 - len(out),
            "sources": ["trend"],
            # 트렌드 주제는 기존 자영업 카테고리 어디에도 안 맞는다.
            # detect_category 가 알아서 분류하도록 비워 둔다.
            "category": "",
        })

    if not out:
        print("  [트렌드 선별] 쓸 만한 주제 없음 — 평소 주제로 진행")
    return out
