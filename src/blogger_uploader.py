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
TOKEN_PATH = Path("config/token.json")
CREDENTIALS_PATH = Path("config/credentials.json")
LOG_PATH = Path("logs/upload_log.json")
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

    def upload_post(
        self,
        title: str,
        html_content: str,
        labels: list[str] = None,
        draft: bool = False,
    ) -> dict | None:
        """
        Blogger에 포스트 업로드
        draft=True: 초안 저장 (검토 후 발행)
        draft=False: 즉시 발행
        """
        if not BLOG_ID:
            raise ValueError("BLOGGER_BLOG_ID 환경변수가 설정되지 않았습니다.")

        body = {
            "title": title,
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
                return self.upload_post(title, html_content, labels, draft)
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
            with open(LOG_PATH) as f:
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
        with open(LOG_PATH) as f:
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
