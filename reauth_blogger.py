"""Blogger OAuth 토큰 재발급.

왜 필요한가:
2026-09-27 부터 발행이 실패했다. 원인은 invalid_grant — 리프레시 토큰이
폐기된 것이다. 9/19 에 발급해 9/27 에 깨졌으니 정확히 8일이다.

구글 OAuth 앱이 "테스트(Testing)" 상태면 리프레시 토큰을 7일 뒤 자동으로
폐기한다. 그래서 매주 같은 일이 반복된다.

먼저 할 일:
Google Cloud Console 에서 앱을 프로덕션으로 게시해야 이 반복이 끝난다.
게시하지 않고 이 스크립트만 돌리면 또 7일 뒤에 같은 자리로 돌아온다.
  https://console.cloud.google.com/auth/audience?project=adbot-497401

실행:
  python reauth_blogger.py
"""

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

BASE = Path(__file__).resolve().parent
CREDENTIALS = BASE / "config" / "credentials.json"
TOKEN = BASE / "config" / "token.json"
SCOPES = ["https://www.googleapis.com/auth/blogger"]

CONSOLE_URL = "https://console.cloud.google.com/auth/audience?project=adbot-497401"


def main() -> int:
    if not CREDENTIALS.exists():
        print(f"credentials.json 이 없습니다: {CREDENTIALS}")
        return 1

    print("=" * 62)
    print("먼저 확인하세요 — 앱이 '프로덕션'으로 게시돼 있어야 합니다.")
    print(f"  {CONSOLE_URL}")
    print("'테스트' 상태면 7일 뒤 토큰이 또 폐기되어 발행이 멈춥니다.")
    print("=" * 62)
    if input("게시 상태가 '프로덕션' 입니까? (y/N) ").strip().lower() != "y":
        print("먼저 게시하고 다시 실행하세요.")
        return 1

    # 기존 토큰은 새로 받기 전에 치운다. 남겨 두면 만료된 것을 다시 쓴다.
    if TOKEN.exists():
        backup = TOKEN.with_suffix(".json.bak")
        TOKEN.replace(backup)
        print(f"기존 토큰을 {backup.name} 으로 옮겼습니다.")

    print("\n브라우저가 열립니다. 블로그를 운영하는 구글 계정으로 로그인하세요.")
    print("'Google에서 확인하지 않은 앱' 경고가 나오면 [고급] > [이동] 을 누르세요.")
    print("본인 앱이라 정상입니다(심사를 받지 않은 상태일 뿐입니다).\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
    creds = flow.run_local_server(port=0)

    if not creds.refresh_token:
        print("\n리프레시 토큰이 발급되지 않았습니다.")
        print("이미 승인된 앱이면 구글이 새로 주지 않습니다. 아래에서 접근 권한을")
        print("삭제한 뒤 다시 실행하세요: https://myaccount.google.com/permissions")
        return 1

    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    print(f"\n토큰 저장 완료: {TOKEN}")

    # GitHub Actions 는 이 값을 시크릿에서 읽어 config/token.json 으로 되살린다.
    one_line = json.dumps(json.loads(creds.to_json()), ensure_ascii=False, separators=(",", ":"))
    out = BASE / "BLOGGER_TOKEN_JSON.txt"
    out.write_text(one_line, encoding="utf-8")
    print(f"""
다음: GitHub 시크릿 갱신
  1) {out} 의 내용을 전부 복사
  2) https://github.com/sinbi850403-ux/GOOGLE_AD/settings/secrets/actions
  3) BLOGGER_TOKEN_JSON 을 그 값으로 덮어쓰기
  4) 붙여넣은 뒤 이 파일은 삭제하세요 (리프레시 토큰이 들어 있습니다)
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
