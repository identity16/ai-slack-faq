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

    args = parser.parse_args()

    if args.command == "faq":
        await generate_slack_faq(args.channel, args.days, args.output, args.format)
    elif args.command == "guide":
        await generate_notion_guide(args.doc_id, args.output, args.format)
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())