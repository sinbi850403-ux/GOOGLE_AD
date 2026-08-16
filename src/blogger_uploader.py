"""
Blogger API v3 자동 업로드 모듈
- OAuth2 인증 또는 서비스 계정 사용
- 초안 저장 / 즉시 발행 선택 가능
- 업로드 로그 저장
"""

import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

BLOG_ID = os.getenv("BLOGGER_BLOG_ID")
BASE_DIR = Path(__file__).parent.parent
TOKEN_PATH = BASE_DIR / "config/token.json"
CREDENTIALS_PATH = BASE_DIR / "config/credentials.json"
LOG_PATH = BASE_DIR / "logs/upload_log.json"
SCOPES = ["https://www.googleapis.com/auth/blogger"]


class BloggerUploader:
    def __init__(self):
        self.service = self._authenticate()

    def _authenticate(self):
        """OAuth2 인증 (토큰 캐시 사용)"""
        creds = None

        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not CREDENTIALS_PATH.exists():
                    raise FileNotFoundError(
                        f"credentials.json 파일이 없습니다: {CREDENTIALS_PATH}\n"
                        "Google Cloud Console에서 OAuth2 클라이언트 ID를 다운로드하세요."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_PATH), SCOPES
                )
                # GitHub Actions 환경에서는 로컬 서버 불가 → 환경변수 토큰 사용
                if os.getenv("GITHUB_ACTIONS"):
                    raise EnvironmentError(
                        "GitHub Actions에서는 사전 발급된 token.json이 필요합니다."
                    )
                creds = flow.run_local_server(port=0)

            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())

        return build("blogger", "v3", credentials=creds)

    # ──────────────────────────────────────────
    # 포스트 업로드
    # ──────────────────────────────────────────

    def _retitle(self, result: dict, title: str, slug: str) -> dict:
        """발행 직후 제목을 한글로 되돌린다. 주소가 따라 바뀌지 않는지 확인하고,
        바뀌었다면 이 방법이 통하지 않는 것이므로 로그로 알린다."""
        before = result.get("url", "")
        try:
            patched = (
                self.service.posts()
                .patch(blogId=BLOG_ID, postId=result["id"], body={"title": title})
                .execute()
            )
        except HttpError as e:
            print(f"  [제목 복원 실패] {e} — 영문 제목으로 남습니다. 수동 수정 필요")
            return result

        after = patched.get("url", before)
        if slug not in after:
            print(f"  [경고] 주소에 슬러그가 남지 않았습니다: {after}")
        elif after != before:
            print(f"  [경고] 제목 변경으로 주소가 바뀌었습니다: {before} → {after}")
        return patched

    def upload_post(
        self,
        title: str,
        html_content: str,
        labels: list[str] = None,
        draft: bool = False,
        slug: str = None,
    ) -> dict | None:
        """
        Blogger에 포스트 업로드
        draft=True: 초안 저장 (검토 후 발행)
        draft=False: 즉시 발행

        slug: URL 에 넣을 영문 주소. Blogger API 는 permalink 를 직접 지정하는
        기능이 없고, 발행 시점의 제목으로 주소를 만든 뒤 고정한다. 한글 제목은
        그 과정에서 통째로 버려져 /2026-vs-7.html 같은 주소가 나온다(실제로
        100편이 그렇게 발행돼 3개월간 클릭 0을 기록했다).
        그래서 영문 제목으로 먼저 발행해 주소를 잡고, 곧바로 제목만 한글로
        바꾼다. 주소는 발행 때 고정되므로 그대로 남는다.
        """
        if not BLOG_ID:
            raise ValueError("BLOGGER_BLOG_ID 환경변수가 설정되지 않았습니다.")

        # 초안은 아직 주소가 정해지지 않아 이 방법을 쓸 수 없다.
        use_slug = bool(slug) and not draft
        body = {
            "title": slug.replace("-", " ") if use_slug else title,
            "content": html_content,
            "labels": labels or [],
        }

        try:
            if draft:
                result = (
                    self.service.posts()
                    .insert(blogId=BLOG_ID, body=body, isDraft=True)
                    .execute()
                )
            else:
                result = (
                    self.service.posts()
                    .insert(blogId=BLOG_ID, body=body, isDraft=False)
                    .execute()
                )

            if use_slug:
                result = self._retitle(result, title, slug)

            post_url = result.get("url", "")
            post_id = result.get("id", "")
            status = "draft" if draft else "published"

            print(f"  업로드 완료 [{status}]: {title}")
            print(f"  URL: {post_url}")

            self._save_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "post_id": post_id,
                "title": title,
                "url": post_url,
                "status": status,
                "labels": labels or [],
            })

            return result

        except HttpError as e:
            print(f"  [업로드 오류] {e}")
            if e.resp.status == 429:
                print("  API 한도 초과 - 60초 대기 후 재시도")
                time.sleep(60)
                return self.upload_post(title, html_content, labels, draft, slug)
            return None

    def upload_batch(self, posts: list[dict], draft: bool = False, delay: int = 10) -> list[dict]:
        """
        여러 포스트 배치 업로드
        delay: 각 업로드 사이 대기 시간 (초) - API 한도 방지
        """
        results = []
        for i, post in enumerate(posts, 1):
            print(f"\n[{i}/{len(posts)}] 업로드 중...")
            result = self.upload_post(
                title=post["title"],
                html_content=post["html_content"],
                labels=post.get("labels", []),
                draft=draft,
                slug=post.get("slug"),
            )
            if result:
                results.append(result)

            if i < len(posts):
                time.sleep(delay)

        print(f"\n배치 업로드 완료: {len(results)}/{len(posts)} 성공")
        return results

    def get_blog_info(self) -> dict:
        """블로그 기본 정보 조회"""
        try:
            blog = self.service.blogs().get(blogId=BLOG_ID).execute()
            return {
                "name": blog.get("name"),
                "url": blog.get("url"),
                "posts": blog.get("posts", {}).get("totalItems", 0),
            }
        except HttpError as e:
            print(f"블로그 정보 조회 실패: {e}")
            return {}

    # ──────────────────────────────────────────
    # 로그 관리
    # ──────────────────────────────────────────

    def _save_log(self, entry: dict):
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        logs = []
        if LOG_PATH.exists():
            with open(LOG_PATH, encoding="utf-8") as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
        logs.append(entry)
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

    def get_upload_stats(self) -> dict:
        """업로드 통계 조회"""
        if not LOG_PATH.exists():
            return {"total": 0, "published": 0, "draft": 0}
        with open(LOG_PATH, encoding="utf-8") as f:
            logs = json.load(f)
        return {
            "total": len(logs),
            "published": sum(1 for l in logs if l["status"] == "published"),
            "draft": sum(1 for l in logs if l["status"] == "draft"),
            "last_upload": logs[-1]["timestamp"] if logs else None,
        }


if __name__ == "__main__":
    uploader = BloggerUploader()
    info = uploader.get_blog_info()
    print(f"블로그: {info}")
    stats = uploader.get_upload_stats()
    print(f"업로드 통계: {stats}")
