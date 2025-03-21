import os
import argparse
import json
from datetime import datetime
from dotenv import load_dotenv

# 커스텀 모듈 가져오기
from src.fetchers.slack_fetcher import SlackFetcher
from src.fetchers.notion_fetcher import NotionFetcher
from src.prompts.slack_faq_prompt import SlackFAQPrompt
from src.prompts.ut_debrief_prompt import UTDebriefPrompt
from src.utils.document_updater import DocumentUpdater

# 환경 변수 로드
load_dotenv(override=True)

def generate_slack_faq(channel_name: str, days: int, output_file: str = None, update_existing: bool = False) -> str:
    """
    슬랙 스레드에서 FAQ 생성
    
    Args:
        channel_name: 채널 이름
        days: 검색할 일자
        output_file: 결과를 저장할 파일명 (None이면 자동 생성)
        update_existing: 기존 문서 업데이트 여부
        
    Returns:
        생성된 마크다운 파일명
    """
    print(f"슬랙 FAQ 생성을 시작합니다 (채널: {channel_name}, 기간: {days}일)")
    
    # 슬랙 스레드 가져오기
    slack_fetcher = SlackFetcher()
    threads = slack_fetcher.fetch_recent_threads(channel_name, days)
    
    if not threads:
        print("처리할 스레드가 없습니다.")
        return None
    
    # FAQ 생성
    print("\nFAQ 생성 중...")
    faq_prompt = SlackFAQPrompt()
    faq_markdown = faq_prompt.generate_faq(threads)
    
    # 결과 저장
    if output_file is None:
        today = datetime.now().strftime("%Y%m%d")
        output_file = f"results/faq_{channel_name}_{today}.md"
    elif not output_file.startswith("results/"):
        output_file = f"results/{output_file}"
    
    # 기존 문서 업데이트 여부 확인
    if update_existing and os.path.exists(output_file):
        print(f"\n기존 문서 '{output_file}'를 업데이트합니다.")
        document_updater = DocumentUpdater()
        faq_markdown = document_updater.update_faq_document(output_file, faq_markdown)
        print(f"LLM이 문서를 지능적으로 병합했습니다.")
        
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(faq_markdown)
    
    print(f"\nFAQ가 '{output_file}' 파일에 {'업데이트' if update_existing and os.path.exists(output_file) else '저장'}되었습니다.")
    return output_file

def generate_ut_debrief(notion_doc_id: str, output_file: str = None, update_existing: bool = False) -> str:
    """
    노션 UT 녹취록에서 Debrief 생성
    
    Args:
        notion_doc_id: 노션 문서 ID
        output_file: 결과를 저장할 파일명 (None이면 자동 생성)
        update_existing: 기존 문서 업데이트 여부
        
    Returns:
        생성된 마크다운 파일명
    """
    print(f"UT Debrief 생성을 시작합니다 (문서 ID: {notion_doc_id})")
    
    # 노션 문서 가져오기
    notion_fetcher = NotionFetcher()
    transcript = notion_fetcher.get_ut_transcript(notion_doc_id)
    
    if not transcript:
        print("노션 문서를 가져오는 데 실패했습니다.")
        return None
    
    # Debrief 생성
    print("\nDebrief 생성 중...")
    debrief_prompt = UTDebriefPrompt()
    debrief_markdown = debrief_prompt.generate_debrief(transcript)
    
    # 결과 저장
    if output_file is None:
        today = datetime.now().strftime("%Y%m%d")
        output_file = f"results/ut_debrief_{today}.md"
    elif not output_file.startswith("results/"):
        output_file = f"results/{output_file}"
    
    # 기존 문서 업데이트 여부 확인
    if update_existing and os.path.exists(output_file):
        print(f"\n기존 문서 '{output_file}'를 업데이트합니다.")
        document_updater = DocumentUpdater()
        debrief_markdown = document_updater.update_ut_document(output_file, debrief_markdown)
        print(f"LLM이 문서를 지능적으로 병합했습니다.")
        
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(debrief_markdown)
    
    print(f"\nUT Debrief가 '{output_file}' 파일에 {'업데이트' if update_existing and os.path.exists(output_file) else '저장'}되었습니다.")
    return output_file

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Log2Doc - 슬랙 FAQ 및 UT Debrief 생성 도구")
    subparsers = parser.add_subparsers(dest="command", help="실행할 명령")
    
    # FAQ 명령 인자
    faq_parser = subparsers.add_parser("faq", help="슬랙 FAQ 생성")
    faq_parser.add_argument("--channel", "-c", required=True, help="슬랙 채널 이름 (# 제외)")
    faq_parser.add_argument("--days", "-d", type=int, default=7, help="검색할 기간(일) (기본값: 7)")
    faq_parser.add_argument("--output", "-o", help="결과 파일명 (기본값: faq_채널명_날짜.md)")
    faq_parser.add_argument("--update", "-u", action="store_true", help="기존 문서 업데이트 (LLM을 사용하여 내용 병합)")
    
    # UT Debrief 명령 인자
    ut_parser = subparsers.add_parser("ut", help="UT Debrief 생성")
    ut_parser.add_argument("--doc_id", "-i", required=True, help="노션 문서 ID 또는 URL")
    ut_parser.add_argument("--output", "-o", help="결과 파일명 (기본값: ut_debrief_날짜.md)")
    ut_parser.add_argument("--update", "-u", action="store_true", help="기존 문서 업데이트 (LLM을 사용하여 내용 병합)")
    
    args = parser.parse_args()
    
    if args.command == "faq":
        generate_slack_faq(args.channel, args.days, args.output, args.update)
    elif args.command == "ut":
        generate_ut_debrief(args.doc_id, args.output, args.update)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()