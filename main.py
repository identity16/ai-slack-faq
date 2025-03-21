"""
Log2Doc CLI Application

대화형 데이터 자동 문서화 시스템의 CLI 인터페이스입니다.
"""

import os
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from src.raw_data import SlackCollector, NotionCollector
from src.semantic_data import SlackExtractor, NotionExtractor, SQLiteStore
from src.document import DocumentType, MarkdownGenerator, HTMLGenerator

# 환경 변수 로드
load_dotenv(override=True)

# 디렉토리 설정
RESULTS_DIR = Path("results")
RESOURCES_DIR = Path("resources")
DATA_DIR = Path("data")

# 디렉토리 생성
for directory in [RESULTS_DIR, RESOURCES_DIR, DATA_DIR]:
    directory.mkdir(exist_ok=True)

async def generate_slack_faq(
    channel_name: str,
    days: int,
    output_file: Optional[str] = None,
    output_format: str = "markdown"
) -> str:
    """
    슬랙 스레드에서 FAQ 생성

    Args:
        channel_name: 채널 이름
        days: 검색할 일자
        output_file: 결과를 저장할 파일명 (None이면 자동 생성)
        output_format: 출력 형식 ("markdown" 또는 "html")

    Returns:
        생성된 문서 파일명
    """
    print(f"슬랙 FAQ 생성을 시작합니다 (채널: {channel_name}, 기간: {days}일)")

    try:
        # 1. Raw Data 수집
        print("\n슬랙 데이터를 수집하는 중...")
        collector = SlackCollector()
        print("[DEBUG] SlackCollector 인스턴스 생성 완료")
        
        try:
            print("[DEBUG] collector.collect 함수 호출 시작")
            raw_data = await collector.collect(channel_name, days)
            print(f"[DEBUG] collector.collect 함수 호출 완료, 데이터 개수: {len(raw_data) if raw_data else 0}")
        except Exception as e:
            print(f"[ERROR] 데이터 수집 중 예외 발생: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None

        if not raw_data:
            print("처리할 데이터가 없습니다.")
            return None

        # 2. Semantic Data 추출
        print("\n시맨틱 데이터를 추출하는 중...")
        extractor = SlackExtractor()
        print("[DEBUG] SlackExtractor 인스턴스 생성 완료")
        
        try:
            print("[DEBUG] extractor.extract 함수 호출 시작")
            semantic_data = await extractor.extract(raw_data)
            print(f"[DEBUG] extractor.extract 함수 호출 완료, 시맨틱 데이터 개수: {len(semantic_data) if semantic_data else 0}")
        except Exception as e:
            print(f"[ERROR] 시맨틱 데이터 추출 중 예외 발생: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None

        # 시맨틱 데이터 저장
        store = SQLiteStore()
        print("[DEBUG] SQLiteStore 인스턴스 생성 완료")
        
        try:
            print("[DEBUG] store.store 함수 호출 시작")
            await store.store(semantic_data)
            print("[DEBUG] store.store 함수 호출 완료")
        except Exception as e:
            print(f"[ERROR] 시맨틱 데이터 저장 중 예외 발생: {str(e)}")
            import traceback
            print(traceback.format_exc())
            # 저장 실패해도 계속 진행

        # 3. Document 생성
        print("\nFAQ 문서를 생성하는 중...")
        generator = MarkdownGenerator() if output_format == "markdown" else HTMLGenerator()
        print(f"[DEBUG] DocumentGenerator 인스턴스 생성 완료: {type(generator).__name__}")
        
        try:
            print("[DEBUG] generator.generate 함수 호출 시작")
            content = await generator.generate(semantic_data, DocumentType.FAQ)
            print("[DEBUG] generator.generate 함수 호출 완료")
        except Exception as e:
            print(f"[ERROR] 문서 생성 중 예외 발생: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None

        # 결과 저장
        if output_file is None:
            today = datetime.now().strftime("%Y%m%d")
            extension = ".md" if output_format == "markdown" else ".html"
            output_file = f"faq_{channel_name}_{today}{extension}"

        output_path = RESULTS_DIR / output_file
        
        try:
            print(f"[DEBUG] generator.save 함수 호출 시작: {output_path}")
            await generator.save(content, str(output_path))
            print("[DEBUG] generator.save 함수 호출 완료")
        except Exception as e:
            print(f"[ERROR] 문서 저장 중 예외 발생: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None

        print(f"\nFAQ가 '{output_file}' 파일에 저장되었습니다.")
        return output_file

    except Exception as e:
        print(f"\n오류가 발생했습니다: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

async def generate_notion_guide(
    doc_id: str,
    output_file: Optional[str] = None,
    output_format: str = "markdown"
) -> str:
    """
    노션 문서에서 가이드 생성

    Args:
        doc_id: 노션 문서 ID 또는 URL
        output_file: 결과를 저장할 파일명 (None이면 자동 생성)
        output_format: 출력 형식 ("markdown" 또는 "html")

    Returns:
        생성된 문서 파일명
    """
    print(f"노션 가이드 생성을 시작합니다 (문서 ID: {doc_id})")

    try:
        # 1. Raw Data 수집
        print("\n노션 데이터를 수집하는 중...")
        collector = NotionCollector()
        raw_data = await collector.collect(doc_id)

        if not raw_data:
            print("처리할 데이터가 없습니다.")
            return None

        # 2. Semantic Data 추출
        print("\n시맨틱 데이터를 추출하는 중...")
        extractor = NotionExtractor()
        semantic_data = await extractor.extract(raw_data)

        # 시맨틱 데이터 저장
        store = SQLiteStore()
        await store.store(semantic_data)

        # 3. Document 생성
        print("\n가이드 문서를 생성하는 중...")
        generator = MarkdownGenerator() if output_format == "markdown" else HTMLGenerator()
        content = await generator.generate(semantic_data, DocumentType.GUIDE)

        # 결과 저장
        if output_file is None:
            today = datetime.now().strftime("%Y%m%d")
            extension = ".md" if output_format == "markdown" else ".html"
            output_file = f"guide_{today}{extension}"

        output_path = RESULTS_DIR / output_file
        await generator.save(content, str(output_path))

        print(f"\n가이드가 '{output_file}' 파일에 저장되었습니다.")
        return output_file

    except Exception as e:
        print(f"\n오류가 발생했습니다: {str(e)}")
        return None

async def generate_glossary(
    source: str = "example",
    channel: Optional[str] = None,
    days: int = 7,
    doc_id: Optional[str] = None,
    output_file: Optional[str] = None,
    output_format: str = "markdown"
) -> str:
    """
    용어집 생성

    Args:
        source: 데이터 소스 ("example", "slack", "notion" 중 하나)
        channel: 슬랙 채널 이름 (source가 "slack"인 경우 필요)
        days: 슬랙 검색 기간 (source가 "slack"인 경우 사용)
        doc_id: 노션 문서 ID (source가 "notion"인 경우 필요)
        output_file: 결과를 저장할 파일명 (None이면 자동 생성)
        output_format: 출력 형식 ("markdown" 또는 "html")

    Returns:
        생성된 문서 파일명
    """
    print(f"용어집 생성을 시작합니다 (소스: {source})")

    try:
        semantic_data = []
        
        if source == "example":
            # 예제 데이터 생성
            print("\n예제 용어집 데이터를 생성하는 중...")
            semantic_data = [
                {
                    "type": "reference",
                    "content": "AI",
                    "description": "인공지능(Artificial Intelligence)은 인간의 학습, 추론, 인식, 판단 등 지적 능력을 컴퓨터로 구현하는 기술입니다.",
                    "keywords": ["인공지능", "머신러닝", "딥러닝"],
                    "source": {
                        "type": "manual",
                        "author": "system",
                        "timestamp": datetime.now().isoformat()
                    }
                },
                {
                    "type": "reference",
                    "content": "API",
                    "description": "응용 프로그램 인터페이스(Application Programming Interface)는 소프트웨어 구성 요소가 서로 통신하기 위해 따라야 하는 규칙과 사양의 집합입니다.",
                    "keywords": ["인터페이스", "통신", "개발"],
                    "source": {
                        "type": "manual",
                        "author": "system",
                        "timestamp": datetime.now().isoformat()
                    }
                },
                {
                    "type": "reference",
                    "content": "CLI",
                    "description": "명령 줄 인터페이스(Command Line Interface)는 사용자가 텍스트 명령을 통해 컴퓨터와 상호 작용하는 방식입니다.",
                    "keywords": ["명령어", "터미널", "콘솔"],
                    "source": {
                        "type": "manual",
                        "author": "system",
                        "timestamp": datetime.now().isoformat()
                    }
                },
                {
                    "type": "reference",
                    "content": "FAQ",
                    "description": "자주 묻는 질문(Frequently Asked Questions)은 특정 주제에 대해 반복적으로 묻는 질문과 그에 대한 답변을 모아놓은 문서입니다.",
                    "keywords": ["질문", "답변", "가이드"],
                    "source": {
                        "type": "manual",
                        "author": "system",
                        "timestamp": datetime.now().isoformat()
                    }
                },
                {
                    "type": "reference",
                    "content": "JSON",
                    "description": "JavaScript Object Notation은 데이터를 저장하거나 전송할 때 사용하는 경량의 데이터 교환 형식입니다.",
                    "keywords": ["데이터 형식", "직렬화", "파싱"],
                    "source": {
                        "type": "manual",
                        "author": "system",
                        "timestamp": datetime.now().isoformat()
                    }
                },
                {
                    "type": "reference",
                    "content": "마크다운",
                    "description": "텍스트 기반의 마크업 언어로, 쉽게 쓰고 읽을 수 있으며 HTML로 변환이 가능합니다.",
                    "keywords": ["문서", "서식", "텍스트"],
                    "source": {
                        "type": "manual",
                        "author": "system",
                        "timestamp": datetime.now().isoformat()
                    }
                },
                {
                    "type": "reference",
                    "content": "시맨틱 데이터",
                    "description": "의미론적 데이터로, 데이터 간의 관계와 의미를 포함하는 구조화된 데이터입니다.",
                    "keywords": ["의미론", "데이터", "구조화"],
                    "source": {
                        "type": "manual",
                        "author": "system",
                        "timestamp": datetime.now().isoformat()
                    }
                }
            ]
            
        elif source == "slack":
            # 슬랙에서 데이터 수집
            if not channel:
                raise ValueError("슬랙 채널 이름이 필요합니다.")
                
            print(f"\n슬랙 채널 '{channel}'에서 데이터 수집 중...")
            collector = SlackCollector()
            threads = await collector.collect(channel, days)
            
            if not threads:
                print("처리할 스레드가 없습니다.")
                return None
                
            print(f"총 {len(threads)}개의 스레드를 수집했습니다.")
            
            # 시맨틱 데이터 추출
            print("\n시맨틱 데이터 추출 중...")
            async with SlackExtractor() as extractor:
                extracted_data = await extractor.extract(threads)
                
            # 용어 참조 데이터만 필터링
            semantic_data = [d for d in extracted_data if d["type"] == SemanticType.REFERENCE]
            print(f"총 {len(semantic_data)}개의 용어 데이터를 추출했습니다.")
            
            if not semantic_data:
                print("용어 데이터가 없습니다. 다른 채널을 시도해보세요.")
                return None
                
        elif source == "notion":
            # 노션에서 데이터 수집
            if not doc_id:
                raise ValueError("노션 문서 ID가 필요합니다.")
                
            print(f"\n노션 문서 '{doc_id}'에서 데이터 수집 중...")
            collector = NotionCollector()
            raw_data = await collector.collect(doc_id)
            
            if not raw_data:
                print("처리할 데이터가 없습니다.")
                return None
                
            # 섹션 개수 계산
            total_sections = sum(len(doc.get("sections", [])) for doc in raw_data)
            print(f"총 {len(raw_data)}개 문서, {total_sections}개 섹션을 수집했습니다.")
            
            # 시맨틱 데이터 추출
            print("\n시맨틱 데이터 추출 중...")
            async with NotionExtractor() as extractor:
                extracted_data = await extractor.extract(raw_data)
                
            # 용어 참조 데이터만 필터링
            semantic_data = [d for d in extracted_data if d["type"] == SemanticType.REFERENCE]
            print(f"총 {len(semantic_data)}개의 용어 데이터를 추출했습니다.")
            
            if not semantic_data:
                print("용어 데이터가 없습니다. 다른 문서를 시도해보세요.")
                return None
        else:
            raise ValueError(f"지원하지 않는 데이터 소스입니다: {source}")
            
        if not semantic_data:
            print("처리할 데이터가 없습니다.")
            return None

        # 시맨틱 데이터 저장
        store = SQLiteStore()
        await store.store(semantic_data)

        # 3. Document 생성
        print("\n용어집 문서를 생성하는 중...")
        generator = MarkdownGenerator() if output_format == "markdown" else HTMLGenerator()
        content = await generator.generate(semantic_data, DocumentType.GLOSSARY)

        # 결과 저장
        if output_file is None:
            today = datetime.now().strftime("%Y%m%d")
            source_name = "example"
            if source == "slack":
                source_name = channel
            elif source == "notion":
                source_name = "notion"
                
            extension = ".md" if output_format == "markdown" else ".html"
            output_file = f"glossary_{source_name}_{today}{extension}"

        output_path = RESULTS_DIR / output_file
        await generator.save(content, str(output_path))

        print(f"\n용어집이 '{output_file}' 파일에 저장되었습니다.")
        return output_file

    except Exception as e:
        print(f"\n오류가 발생했습니다: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

async def main() -> None:
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Log2Doc - 대화형 데이터 자동 문서화 시스템")
    subparsers = parser.add_subparsers(dest="command", help="실행할 명령")

    # FAQ 명령 인자
    faq_parser = subparsers.add_parser("faq", help="슬랙 FAQ 생성")
    faq_parser.add_argument("--channel", "-c", required=True, help="슬랙 채널 이름 (# 제외)")
    faq_parser.add_argument("--days", "-d", type=int, default=7, help="검색할 기간(일) (기본값: 7)")
    faq_parser.add_argument("--output", "-o", help="결과 파일명 (기본값: faq_채널명_날짜.md)")
    faq_parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "html"],
        default="markdown",
        help="출력 형식 (기본값: markdown)"
    )

    # 가이드 명령 인자
    guide_parser = subparsers.add_parser("guide", help="노션 가이드 생성")
    guide_parser.add_argument("--doc_id", "-i", required=True, help="노션 문서 ID 또는 URL")
    guide_parser.add_argument("--output", "-o", help="결과 파일명 (기본값: guide_날짜.md)")
    guide_parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "html"],
        default="markdown",
        help="출력 형식 (기본값: markdown)"
    )
    
    # 용어집 명령 인자
    glossary_parser = subparsers.add_parser("glossary", help="용어집 생성")
    glossary_parser.add_argument(
        "--source",
        "-s",
        choices=["example", "slack", "notion"],
        default="example",
        help="데이터 소스 (기본값: example)"
    )
    glossary_parser.add_argument("--channel", "-c", help="슬랙 채널 이름 (소스가 slack인 경우)")
    glossary_parser.add_argument("--days", "-d", type=int, default=7, help="슬랙 검색 기간(일) (기본값: 7)")
    glossary_parser.add_argument("--doc_id", "-i", help="노션 문서 ID 또는 URL (소스가 notion인 경우)")
    glossary_parser.add_argument("--output", "-o", help="결과 파일명 (기본값: glossary_소스명_날짜.md)")
    glossary_parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "html"],
        default="markdown",
        help="출력 형식 (기본값: markdown)"
    )

    args = parser.parse_args()

    if args.command == "faq":
        await generate_slack_faq(args.channel, args.days, args.output, args.format)
    elif args.command == "guide":
        await generate_notion_guide(args.doc_id, args.output, args.format)
    elif args.command == "glossary":
        # 소스별 인자 검증
        if args.source == "slack" and not args.channel:
            print("오류: 슬랙 소스를 사용할 때는 --channel 인자가 필요합니다.")
            return
        if args.source == "notion" and not args.doc_id:
            print("오류: 노션 소스를 사용할 때는 --doc_id 인자가 필요합니다.")
            return
            
        await generate_glossary(
            args.source, 
            args.channel, 
            args.days, 
            args.doc_id, 
            args.output, 
            args.format
        )
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())