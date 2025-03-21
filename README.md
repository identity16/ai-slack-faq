# Log2Doc

로그나 대화 기록을 기반으로 유용한 문서를 자동 생성하는 도구입니다.

## 기능

### 1. 슬랙 FAQ 생성기
- 특정 슬랙 채널의 스레드를 분석하여 FAQ 문서 자동 생성
- 최근 N일 동안의 대화에서 질문-답변 구조 추출
- 유의미한 Q&A 쌍을 카테고리별로 정리하여 마크다운 문서 생성

### 2. UT Debrief 생성기
- 노션에 저장된 사용자 테스트(UT) 녹취록을 분석
- 주요 논의 주제, 인사이트, 액션 아이템 추출
- 회의 요약, 역할 분담, 후속 조치가 포함된 마크다운 문서 생성

## 설치 방법

1. 저장소 클론:
```bash
git clone https://github.com/yourusername/log2doc.git
cd log2doc
```

2. 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

3. 환경 변수 설정:
- `.env.example` 파일을 `.env`로 복사하고 다음 값을 설정:
  - `SLACK_BOT_TOKEN`: 슬랙 봇 토큰
  - `OPENAI_API_KEY`: OpenAI API 키
  - `NOTION_API_KEY`: 노션 통합 API 키 (UT Debrief 기능 사용 시 필요)

## 슬랙 봇 설정

1. [Slack API 웹사이트](https://api.slack.com/apps)에서 새 앱 생성
2. 다음 Bot Token Scopes 추가:
   - channels:history
   - channels:read
   - groups:history
   - groups:read
3. 워크스페이스에 앱 설치 후 Bot Token 복사
4. 분석할 채널에 봇 초대하기

## 노션 API 설정

1. [Notion API 페이지](https://www.notion.so/my-integrations)에서 통합 생성
2. 통합 이름과 관련 워크스페이스 설정
3. 생성된 Secret을 `.env` 파일에 추가
4. 분석할 노션 페이지/데이터베이스에 통합 추가 (페이지/데이터베이스 우측 상단의 공유 메뉴)

## 사용 방법

### 슬랙 FAQ 생성

```bash
python main.py faq --channel 채널명 --days 7 --output 결과파일.md
```

옵션:
- `--channel`, `-c`: 슬랙 채널 이름 (# 기호 제외)
- `--days`, `-d`: 검색할 기간(일) (기본값: 7)
- `--output`, `-o`: 결과 파일명 (기본값: faq_채널명_날짜.md)

### UT Debrief 생성

```bash
python main.py ut --doc_id 노션문서ID --output 결과파일.md
```

옵션:
- `--doc_id`, `-i`: 노션 문서 ID 또는 URL
- `--output`, `-o`: 결과 파일명 (기본값: ut_debrief_날짜.md)

## 참고 사항

- 처리 시간은 메시지 수와 복잡도에 따라 달라질 수 있습니다.
- OpenAI API 사용량에 따른 비용이 발생할 수 있습니다.
- 슬랙 봇은 초대된 채널의 메시지만 접근할 수 있습니다.
- 노션 통합은 공유된 페이지/데이터베이스만 접근할 수 있습니다.