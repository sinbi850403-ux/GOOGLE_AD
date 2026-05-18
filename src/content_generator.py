"""
Claude API 기반 애드센스 최적화 블로그 글 생성 모듈
- 애드센스 승인 기준: 오리지널 콘텐츠 1500자+, 명확한 구조, 광고 친화적 주제
- 생성 결과: HTML 형식 (Blogger 직접 업로드용)
"""

import os
import re
import anthropic
from dotenv import load_dotenv

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
BLOG_LANGUAGE = os.getenv("BLOG_LANGUAGE", "ko")  # ko: 한국어, en: 영어


# 애드센스 승인에 유리한 카테고리별 프롬프트 전략
ADSENSE_HIGH_CPC_CATEGORIES = {
    "재테크/금융": ["주식", "ETF", "적금", "대출", "보험", "코인", "부동산"],
    "건강/의료": ["다이어트", "영양제", "운동", "건강검진", "질병"],
    "IT/테크": ["AI", "스마트폰", "노트북", "앱", "소프트웨어"],
    "여행/라이프": ["여행지", "맛집", "호텔", "항공"],
    "교육/자기계발": ["자격증", "영어", "온라인강의", "책"],
}


def detect_category(keyword: str) -> str:
    """키워드로 카테고리 감지"""
    for category, kws in ADSENSE_HIGH_CPC_CATEGORIES.items():
        if any(k in keyword for k in kws):
            return category
    return "라이프스타일"


def build_system_prompt() -> str:
    return """당신은 구글 애드센스 승인 전문가이자 SEO 최적화 블로그 작가입니다.
다음 원칙을 반드시 준수하여 블로그 포스트를 작성하세요:

[애드센스 승인 핵심 원칙]
1. 완전한 오리지널 콘텐츠 - 복사/패러프레이징 금지
2. 최소 1500자 이상의 충실한 내용
3. 독자에게 실질적인 가치와 정보 제공
4. 광고 친화적 주제 (혐오, 도박, 성인 내용 절대 금지)
5. 자연스러운 키워드 배치 (키워드 스터핑 금지)

[HTML 구조 요구사항]
- H1: 제목 (1개, 메인 키워드 포함)
- H2: 주요 섹션 (4~6개)
- H3: 소섹션 (각 H2 아래 2~3개)
- 본문: <p> 태그 사용
- 리스트: <ul>/<ol> 적극 활용
- 이미지 alt 텍스트 포함한 <figure> 태그
- 강조: <strong> 태그

[SEO 요구사항]
- 제목에 메인 키워드 포함
- 첫 문단에 메인 키워드 자연스럽게 삽입
- 관련 키워드(LSI) 자연스럽게 분산 배치
- 메타 설명 (150자 이내) 별도 제공

출력 형식: JSON
{
  "title": "SEO 최적화된 제목",
  "meta_description": "검색 결과에 표시될 설명 (150자 이내)",
  "labels": ["태그1", "태그2", "태그3"],
  "html_content": "완전한 HTML 본문"
}"""


def build_user_prompt(keyword: str, category: str) -> str:
    lang_instruction = "반드시 한국어로 작성하세요." if BLOG_LANGUAGE == "ko" else "Write in English."
    return f"""키워드: "{keyword}"
카테고리: {category}
{lang_instruction}

위 키워드로 구글 애드센스 승인에 최적화된 블로그 포스트를 작성하세요.

요구사항:
- 제목: 클릭하고 싶게 만드는 SEO 제목 (숫자/연도 포함 권장)
- 본문: 최소 1500자, HTML 형식
- 구조: H1 > H2(5개 이상) > H3 > 본문 단락
- 실용적인 정보: 구체적인 수치, 예시, 팁 포함
- 마무리: 독자 행동 유도 (댓글 유도, 관련 주제 언급)
- labels: 관련 태그 5개 (Blogger 라벨용)

JSON 형식으로만 응답하세요."""


class ContentGenerator:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        self.model = "claude-sonnet-4-6"

    def generate(self, keyword: str) -> dict | None:
        """
        키워드로 블로그 포스트 생성
        반환: {"title": ..., "meta_description": ..., "labels": [...], "html_content": ...}
        """
        category = detect_category(keyword)
        print(f"  생성 중: '{keyword}' (카테고리: {category})")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=build_system_prompt(),
                messages=[
                    {"role": "user", "content": build_user_prompt(keyword, category)}
                ],
            )

            raw = response.content[0].text.strip()
            # JSON 블록 추출 (마크다운 코드블록 제거)
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            import json
            post = json.loads(raw)

            # 필수 필드 검증
            required = ["title", "meta_description", "labels", "html_content"]
            for field in required:
                if field not in post:
                    raise ValueError(f"응답에 '{field}' 필드 없음")

            # 콘텐츠 길이 검증 (1000자 이상)
            text_only = re.sub(r"<[^>]+>", "", post["html_content"])
            if len(text_only) < 1000:
                print(f"  경고: 콘텐츠가 너무 짧음 ({len(text_only)}자) - 재생성 시도")
                return self._regenerate_longer(keyword, category)

            print(f"  완료: '{post['title']}' ({len(text_only)}자)")
            return post

        except Exception as e:
            print(f"  [오류] 콘텐츠 생성 실패: {e}")
            return None

    def _regenerate_longer(self, keyword: str, category: str) -> dict | None:
        """콘텐츠가 짧을 때 더 길게 재생성"""
        try:
            extended_prompt = build_user_prompt(keyword, category) + "\n\n중요: 각 H2 섹션마다 최소 300자 이상 작성하세요."
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=build_system_prompt(),
                messages=[{"role": "user", "content": extended_prompt}],
            )
            raw = response.content[0].text.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            import json
            return json.loads(raw)
        except Exception as e:
            print(f"  [오류] 재생성 실패: {e}")
            return None

    def generate_batch(self, keywords: list[dict]) -> list[dict]:
        """여러 키워드 배치 생성"""
        results = []
        for kw_data in keywords:
            keyword = kw_data["keyword"]
            post = self.generate(keyword)
            if post:
                post["source_keyword"] = keyword
                post["trend_score"] = kw_data.get("score", 0)
                results.append(post)
        return results


if __name__ == "__main__":
    gen = ContentGenerator()
    result = gen.generate("ETF 투자 방법")
    if result:
        print(f"\n제목: {result['title']}")
        print(f"메타: {result['meta_description']}")
        print(f"태그: {result['labels']}")
        print(f"본문 길이: {len(result['html_content'])}자")
