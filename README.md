# Log2Doc: 대화형 데이터 자동 문서화 시스템

## 프로젝트 개요

Log2Doc은 LLM(Large Language Model)을 활용하여 Raw Data → Semantic Data → Document 흐름을 자동화하는 시스템입니다. 기업 내 분산된 대화형 데이터를 자동으로 수집하고 문서화하여 지식 접근성을 높이는 것이 주요 목표입니다.

## 시스템 아키텍처

시스템은 다음 3가지 핵심 모듈로 구성됩니다:

1. **Raw Data 수집 모듈** (`src/raw_data/`)
   - Slack, Notion 등의 소스에서 원본 데이터 수집
   - 로컬 저장소에 데이터 저장

2. **Semantic Data 추출 모듈** (`src/semantic_data/`)
   - 원본 데이터 정제 및 전처리
   - OpenAI GPT를 활용한 의미 단위 추출
   - Q&A, 인사이트, 피드백 등 구조화

3. **Document 생성 모듈** (`src/document/`)
   - 시맨틱 데이터 기반 문서 생성
   - FAQ, 가이드, 용어집 등 다양한 문서 템플릿 지원
   - HTML/Markdown 형식 출력

## 설치 및 실행

### 요구사항
- Python 3.8+
- pip
- 가상환경 (권장)

### 설치
```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 API 키 등을 설정
```

### 실행
```bash
# 개발 서버 실행
python app.py

# CLI로 문서 생성
python main.py faq --channel [채널명] --days [일자]
python main.py guide --doc_id [노션문서ID]

# 용어집 생성
python main.py glossary  # 예제 데이터로 용어집 생성
python main.py glossary --source slack --channel [채널명] --days [일자]  # 슬랙 데이터로 용어집 생성
python main.py glossary --source notion --doc_id [노션문서ID]  # 노션 데이터로 용어집 생성
python main.py glossary --format html  # HTML 형식으로 용어집 생성
```

## 프로젝트 구조
```
.
├── src/
│   ├── raw_data/        # Raw Data 수집 모듈
│   ├── semantic_data/   # Semantic Data 추출 모듈
│   └── document/        # Document 생성 모듈
├── data/               # 로컬 데이터 저장소
├── resources/         # 설정 파일 및 리소스
├── results/          # 생성된 문서 저장
├── tests/           # 테스트 코드
├── app.py          # 메인 애플리케이션
├── requirements.txt # 의존성 목록
└── .env           # 환경 변수
```

## 기술 스택

- **백엔드**: Python, Flask/FastAPI
- **데이터베이스**: SQLite
- **AI/ML**: OpenAI GPT API
- **문서 생성**: Markdown/HTML

## 개발 가이드라인

1. 코드 스타일은 PEP 8을 따릅니다.
2. 모든 새로운 기능은 테스트 코드를 포함해야 합니다.
3. 커밋 메시지는 명확하고 설명적이어야 합니다.

## 라이선스

MIT License