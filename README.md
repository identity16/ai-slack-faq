# Log2Doc

로그나 대화 기록을 기반으로 유용한 문서를 자동 생성하는 도구입니다.

## 기능

### 1. 슬랙 FAQ 생성기
- 특정 슬랙 채널의 스레드를 분석하여 FAQ 문서 자동 생성
- 최근 N일 동안의 대화에서 질문-답변 구조 추출
- 유의미한 Q&A 쌍을 카테고리별로 정리하여 마크다운 문서 생성
- LLM 기반 문서 업데이트 및 병합 지원

### 2. UT Debrief 생성기
- 노션에 저장된 사용자 테스트(UT) 녹취록을 분석
- 주요 논의 주제, 인사이트, 액션 아이템 추출
- 회의 요약, 역할 분담, 후속 조치가 포함된 마크다운 문서 생성
- LLM 기반 문서 업데이트 및 병합 지원

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
- `--update`, `-u`: LLM 기반 문서 업데이트 모드 활성화 (기존 내용과 새 내용 지능적 병합)

### UT Debrief 생성

```bash
python main.py ut --doc_id 노션문서ID --output 결과파일.md
```

옵션:
- `--doc_id`, `-i`: 노션 문서 ID 또는 URL
- `--output`, `-o`: 결과 파일명 (기본값: ut_debrief_날짜.md)
- `--update`, `-u`: LLM 기반 문서 업데이트 모드 활성화 (기존 내용과 새 내용 지능적 병합)

### 문서 업데이트 시나리오

기존 문서를 업데이트하려면 `--update` 또는 `-u` 옵션을 사용합니다:

```bash
# 기존 FAQ 문서 업데이트
python main.py faq --channel 일반 --days 7 --output faq_일반_20240315.md --update

# 기존 UT Debrief 문서 업데이트
python main.py ut --doc_id notion문서ID --output ut_debrief_20240315.md --update
```

LLM 기반 업데이트 시 수행되는 작업:
- GPT-4o 모델을 사용하여 두 문서를 지능적으로 병합
- 문서 구조와 포맷에 구애받지 않고 내용 기반으로 최적의 병합 제안
- 새로운 정보 추가와 중복 내용 통합 자동 처리
- 최종 병합 문서에 최신 업데이트 날짜 자동 삽입

## 참고 사항

- 처리 시간은 메시지 수와 복잡도에 따라 달라질 수 있습니다.
- OpenAI API 사용량에 따른 비용이 발생할 수 있습니다.
- 슬랙 봇은 초대된 채널의 메시지만 접근할 수 있습니다.
- 노션 통합은 공유된 페이지/데이터베이스만 접근할 수 있습니다.

## 아키텍처 구조

이 프로젝트는 다음과 같은 3계층 아키텍처로 구성되어 있습니다:

### 1. Repository 계층
- 외부 데이터 소스에서 원본 데이터를 가져오는 역할
- `src/repositories/` 디렉토리에 위치
- 주요 클래스:
  - `SlackRepository`: 슬랙 API를 통해 채널 및 스레드 데이터 가져오기
  - `NotionRepository`: 노션 API를 통해 UT 녹취록 데이터 가져오기

### 2. Processor 계층
- 원본 데이터를 정제, 분류, 저장하는 역할
- `src/processors/` 디렉토리에 위치
- 주요 클래스:
  - `SlackProcessor`: 슬랙 스레드 데이터 정제 및 분류
  - `NotionProcessor`: 노션 녹취록 데이터 정제 및 분석
  - `DataStore`: 정제된 데이터 저장 및 관리

### 3. Document 계층
- 정제된 데이터를 기반으로 문서를 생성하고 관리하는 역할
- `src/documents/` 디렉토리에 위치
- 주요 클래스:
  - `SlackFAQGenerator`: 슬랙 데이터로 FAQ 문서 생성
  - `UTDebriefGenerator`: 노션 데이터로 Debrief 문서 생성
  - `DocumentManager`: 문서 업데이트, 병합 등 관리

이 구조를 통해 데이터 소스, 데이터 처리, 문서 생성의 관심사를 명확하게 분리하여 코드의 가독성과 유지보수성을 높였습니다.

## GUI 앱 사용 방법

웹 인터페이스를 통해 문서 생성 및 관리가 가능합니다:

```bash
# GUI 앱 실행
streamlit run app.py
```

GUI 앱 기능:
- 문서 목록 조회 및 관리 (보기, 다운로드, 삭제)
- 슬랙 FAQ 생성 (채널, 기간 지정)
- UT Debrief 생성 (노션 문서 지정)
- 리소스 파일 업로드 및 관리 (PDF, DOCX, XLSX, CSV 등)

![GUI 앱 화면](https://example.com/gui_screenshot.png)