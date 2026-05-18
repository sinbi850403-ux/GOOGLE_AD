# AdBot - 구글 애드센스 자동 블로그 봇

Google Trends + 네이버 DataLab으로 트렌드를 수집하고, Claude AI로 고품질 원본 글을 생성해서 Blogger에 자동 업로드하는 봇입니다.

GitHub Actions로 **매일 자동 실행** (무료)

---

## 시스템 구조

```
트렌드 수집 → AI 글 생성 → Blogger 업로드
(Google Trends    (Claude API)    (Blogger API v3)
 + 네이버 DataLab)
```

---

## 빠른 시작

### 1. API 키 준비

| 필요한 것 | 발급 위치 |
|---|---|
| Claude API Key | [console.anthropic.com](https://console.anthropic.com/) |
| Google OAuth2 credentials.json | Google Cloud Console → API 사용 설정 → Blogger API v3 |
| Blogger Blog ID | 블로그 대시보드 URL 또는 설정 |
| 네이버 DataLab (선택) | [developers.naver.com](https://developers.naver.com/) |

### 2. Google Cloud Console 설정

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 (또는 기존 프로젝트 선택)
3. **API 및 서비스 → 라이브러리** → `Blogger API v3` 활성화
4. **API 및 서비스 → 사용자 인증 정보** → `OAuth 2.0 클라이언트 ID` 생성
   - 애플리케이션 유형: **데스크톱 앱**
5. `credentials.json` 다운로드 → `config/credentials.json` 에 저장

### 3. 로컬 설치 및 최초 인증

```bash
# 패키지 설치
pip install -r requirements.txt

# .env 설정
cp .env.example .env
# .env 파일 열어서 CLAUDE_API_KEY, BLOGGER_BLOG_ID 입력

# 최초 1회: OAuth 브라우저 인증 (token.json 자동 생성)
cd src
python blogger_uploader.py
```

### 4. 실행

```bash
cd src

# 기본 실행 (트렌드 자동 수집 → 3개 글 즉시 발행)
python main.py

# 초안 저장 (발행 안 함, 검토 후 발행)
python main.py --draft

# 글 수 지정
python main.py --count 5

# 특정 키워드로 생성
python main.py --keyword "ETF 투자 방법 2026"

# 스케줄러 데몬 (매일 09:00, 15:00 자동 실행)
python main.py --daemon

# 통계 보기
python main.py --stats
```

---

## GitHub Actions 자동화 설정

로컬 PC가 꺼져 있어도 자동 실행됩니다.

### Secrets 등록 (Settings → Secrets and variables → Actions)

| Secret 이름 | 값 |
|---|---|
| `CLAUDE_API_KEY` | Claude API 키 |
| `BLOGGER_BLOG_ID` | 블로그 ID |
| `BLOGGER_TOKEN_JSON` | `config/token.json` 파일 전체 내용 |
| `BLOGGER_CREDENTIALS_JSON` | `config/credentials.json` 파일 전체 내용 |
| `NAVER_CLIENT_ID` | 네이버 클라이언트 ID (선택) |
| `NAVER_CLIENT_SECRET` | 네이버 클라이언트 시크릿 (선택) |

> `token.json` 내용 복사: `cat config/token.json` 또는 메모장으로 열기

자동 실행 일정: **매일 오전 9시 + 오후 3시 (KST)**

수동 실행: Actions 탭 → `AdBot - Daily Auto Post` → `Run workflow`

---

## 애드센스 승인 전략

| 단계 | 목표 | 설정 |
|---|---|---|
| 승인 전 (1~4주) | 양질의 글 30개+ 축적 | `POSTS_PER_DAY=2`, `PUBLISH_AS_DRAFT=false` |
| 신청 시점 | 15개+ 발행 완료 | 글 길이 1500자+, 구조 명확 |
| 승인 후 | 수익 극대화 | `POSTS_PER_DAY=5`, 고CPC 키워드 집중 |

### 애드센스 승인 체크리스트
- [ ] Blogger 블로그 커스텀 도메인 연결 (선택사항이지만 권장)
- [ ] 개인정보처리방침 페이지 추가
- [ ] 소개(About) 페이지 추가
- [ ] 메뉴/네비게이션 구성
- [ ] 15개 이상 오리지널 글 발행
- [ ] 각 글 1500자 이상

---

## 파일 구조

```
GOOGLE_AD/
├── src/
│   ├── main.py              # 메인 오케스트레이터
│   ├── trend_collector.py   # 트렌드 키워드 수집
│   ├── content_generator.py # Claude AI 글 생성
│   └── blogger_uploader.py  # Blogger API 업로드
├── config/                  # 인증 파일 (gitignore)
│   ├── credentials.json     # Google OAuth2 (직접 저장)
│   └── token.json           # 자동 생성됨
├── logs/                    # 업로드 로그 (자동 생성)
├── .github/workflows/
│   └── adbot.yml            # GitHub Actions
├── .env.example             # 환경변수 템플릿
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 주의사항

- `config/token.json`, `config/credentials.json`, `.env` 는 **절대 GitHub에 올리지 마세요**
- 애드센스 정책 위반 콘텐츠(도박, 성인, 혐오) 생성 안 됨
- 구글 Blogger API 일일 할당량: 10,000 요청/일 (충분)
- Claude API 비용: 글 1개 약 $0.01~0.03 (월 300개 = 약 $3~9)
