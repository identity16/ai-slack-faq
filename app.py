"""
Log2Doc Web Application

대화형 데이터 자동 문서화 시스템의 웹 인터페이스입니다.
"""

import os
import streamlit as st
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
from typing import List, Dict, Any
import asyncio

from src.raw_data import SlackCollector, NotionCollector
from src.semantic_data import SemanticType, SlackExtractor, NotionExtractor, SQLiteStore
from src.document import DocumentType, MarkdownGenerator, HTMLGenerator

# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv(override=True)

# 디렉토리 설정
RESULTS_DIR = Path("results")
RESOURCES_DIR = Path("resources")
DATA_DIR = Path("data")

# 디렉토리 생성
for directory in [RESULTS_DIR, RESOURCES_DIR, DATA_DIR]:
    directory.mkdir(exist_ok=True)

def display_documents(files: List[Path], doc_type: str) -> None:
    """문서 목록 표시 및 관리"""
    if not files:
        st.info(f"저장된 {doc_type} 문서가 없습니다.")
        return
    
    # 파일 정보 생성
    files_data = [
        {
            "파일명": file.name,
            "수정일": datetime.fromtimestamp(file.stat().st_mtime),
            "크기(KB)": f"{file.stat().st_size / 1024:.1f}",
            "경로": str(file)
        }
        for file in files
    ]
    
    # 테이블 표시
    df = pd.DataFrame(files_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 문서 선택 및 작업
    col1, col2 = st.columns(2)
    
    with col1:
        selected_file = st.selectbox(
            "문서 선택",
            [f["파일명"] for f in files_data],
            key=f"{doc_type}_select"
        )
    
    with col2:
        action = st.selectbox(
            "작업 선택",
            ["문서 보기", "문서 다운로드", "문서 삭제"],
            key=f"{doc_type}_action"
        )
    
    if selected_file:
        file_path = RESULTS_DIR / selected_file
        
        if action == "문서 보기":
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            st.markdown(content)
            
        elif action == "문서 다운로드":
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            st.download_button(
                "문서 다운로드",
                content,
                file_name=selected_file,
                mime="text/markdown"
            )
            
        elif action == "문서 삭제":
            if st.button("삭제 확인", key=f"{doc_type}_delete"):
                os.remove(file_path)
                st.success(f"{selected_file} 문서가 삭제되었습니다.")
                st.rerun()

def list_documents() -> None:
    """문서 목록 페이지"""
    st.header("문서 목록")
    
    # 문서 탭 나누기
    doc_tabs = st.tabs(["FAQ", "가이드", "릴리스 노트", "용어집"])
    
    with doc_tabs[0]:
        st.subheader("FAQ 문서")
        faq_files = list(RESULTS_DIR.glob("faq_*.md"))
        display_documents(faq_files, "FAQ")
    
    with doc_tabs[1]:
        st.subheader("가이드 문서")
        guide_files = list(RESULTS_DIR.glob("guide_*.md"))
        display_documents(guide_files, "가이드")
    
    with doc_tabs[2]:
        st.subheader("릴리스 노트")
        release_files = list(RESULTS_DIR.glob("release_*.md"))
        display_documents(release_files, "릴리스")
    
    with doc_tabs[3]:
        st.subheader("용어집")
        glossary_files = list(RESULTS_DIR.glob("glossary_*.md"))
        display_documents(glossary_files, "용어집")

def save_and_display_result(document: Dict[str, Any]) -> None:
    """결과 저장 및 표시"""
    # 파일 저장
    today = datetime.now().strftime("%Y%m%d")
    output_file = f"faq_{document['channel']}_{today}.md"
    output_path = RESULTS_DIR / output_file
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(document["content"])
    
    st.success(f"FAQ가 '{output_file}' 파일에 저장되었습니다.")
    
    # 생성된 문서 표시
    st.subheader("생성된 문서:")
    if document["format"] == "markdown":
        st.markdown(document["content"])
    else:
        st.components.v1.html(document["content"], height=600)

async def generate_slack_faq() -> None:
    """슬랙 FAQ 생성 페이지"""
    print("[DEBUG] generate_slack_faq 함수 시작")
    st.header("슬랙 FAQ 생성")
    
    with st.form("slack_faq_form"):
        channel = st.text_input(
            "채널 이름",
            help="FAQ를 생성할 슬랙 채널 이름을 입력하세요 (예: general)"
        )
        days = st.number_input(
            "검색 기간 (일)",
            min_value=1,
            max_value=30,
            value=7,
            help="최근 몇 일 동안의 대화를 검색할지 선택하세요"
        )
        output_format = st.selectbox(
            "출력 형식",
            ["markdown", "html"],
            help="생성된 FAQ의 출력 형식을 선택하세요"
        )
        
        submitted = st.form_submit_button("FAQ 생성")
        print(f"[DEBUG] 폼 제출 상태: {submitted}")
        
    if submitted:
        try:
            print(f"[DEBUG] FAQ 생성 시작 - 채널: {channel}, 기간: {days}일")
            
            # 진행 상황 컨테이너 생성
            progress_container = st.container()
            with progress_container:
                # 전체 진행 상태 표시
                progress_bar = st.progress(0)
                status_text = st.empty()
                details_expander = st.expander("자세한 진행 상황")
                
                # 단계별 상태 표시용 컴포넌트
                with details_expander:
                    collector_status = st.empty()
                    extractor_status = st.empty()
                    db_status = st.empty()
                    doc_status = st.empty()
                
                # 초기 상태 설정
                status_text.info("FAQ 생성을 준비하는 중...")
                collector_status.info("🔄 채널 데이터 수집 준비 중...")
                extractor_status.info("⏳ 시맨틱 데이터 추출 대기 중...")
                db_status.info("⏳ 데이터베이스 저장 대기 중...")
                doc_status.info("⏳ 문서 생성 대기 중...")
                progress_bar.progress(5)
                
                # SlackCollector 인스턴스 생성
                status_text.info("슬랙 채널 데이터를 수집하는 중...")
                collector_status.info("🔄 SlackCollector 초기화 중...")
                print("[DEBUG] SlackCollector 인스턴스 생성 시작")
                collector = SlackCollector()
                print("[DEBUG] SlackCollector 인스턴스 생성 완료")
                collector_status.success("✅ SlackCollector 초기화 완료")
                progress_bar.progress(10)
                
                # Raw 데이터 수집
                collector_status.info(f"🔄 '{channel}' 채널에서 최근 {days}일 동안의 데이터 수집 중...")
                print(f"[DEBUG] collector.collect 호출 시작 - 채널: {channel}, 기간: {days}일")
                threads = await collector.collect(channel, days)
                thread_count = len(threads) if threads else 0
                print(f"[DEBUG] collector.collect 호출 완료 - 결과 개수: {thread_count}")
                
                if not threads:
                    status_text.error("처리할 데이터가 없습니다.")
                    collector_status.error("❌ 슬랙 채널에서 스레드를 찾을 수 없습니다.")
                    st.error("처리할 스레드가 없습니다. 채널 이름과 검색 기간을 확인해주세요.")
                    print("[DEBUG] 처리할 스레드가 없음")
                    return
                
                # 수집 완료 표시
                collector_status.success(f"✅ 총 {thread_count}개의 스레드 수집 완료")
                progress_bar.progress(30)
                
                # 의미 데이터 추출
                status_text.info("시맨틱 데이터를 추출하는 중...")
                extractor_status.info("🔄 SlackExtractor 초기화 중...")
                print("[DEBUG] SlackExtractor 생성 및 초기화 시작")
                
                # 추출 진행 상황 표시용 카운터
                extract_counter = {"current": 0, "total": thread_count}
                extract_progress = extractor_status.progress(0)
                extract_text = extractor_status.empty()
                extract_text.info(f"🔄 시맨틱 데이터 추출 중... (0/{thread_count})")
                
                class ProgressUpdater:
                    def update(self, current, total):
                        extract_counter["current"] = current
                        percentage = int(100 * current / total) if total > 0 else 0
                        extract_progress.progress(percentage / 100)
                        extract_text.info(f"🔄 시맨틱 데이터 추출 중... ({current}/{total})")
                        # 전체 진행 상황도 업데이트
                        overall_progress = 30 + (percentage * 0.3)  # 30%에서 60%까지 할당
                        progress_bar.progress(min(int(overall_progress), 60))
                
                progress_updater = ProgressUpdater()
                
                async with SlackExtractor() as extractor:
                    # 시맨틱 데이터 추출 시 진행 상황 업데이트 함수 전달
                    print("[DEBUG] 시맨틱 데이터 추출 시작")
                    semantic_data = await extractor.extract(threads, progress_updater.update)
                    semantic_count = len(semantic_data) if semantic_data else 0
                    print(f"[DEBUG] 시맨틱 데이터 추출 완료 - 결과 개수: {semantic_count}")
                
                # 추출 완료 표시
                extract_text.empty()
                extractor_status.success(f"✅ 총 {semantic_count}개의 시맨틱 데이터 추출 완료")
                progress_bar.progress(60)
                
                # 시맨틱 데이터 저장
                status_text.info("데이터베이스에 저장하는 중...")
                db_status.info("🔄 SQLiteStore 초기화 및 데이터 저장 중...")
                print("[DEBUG] SQLiteStore 인스턴스 생성")
                store = SQLiteStore()
                print("[DEBUG] 시맨틱 데이터 저장 시작")
                await store.store(semantic_data)
                print("[DEBUG] 시맨틱 데이터 저장 완료")
                db_status.success("✅ 데이터베이스 저장 완료")
                progress_bar.progress(70)
                
                # 문서 생성
                status_text.info("FAQ 문서를 생성하는 중...")
                doc_status.info("🔄 문서 생성기 초기화 및 FAQ 생성 중...")
                print("[DEBUG] 문서 생성기 초기화")
                generator = MarkdownGenerator()
                print("[DEBUG] 문서 생성 시작")
                content = await generator.generate(
                    semantic_data,
                    DocumentType.FAQ
                )
                print("[DEBUG] 문서 생성 완료")
                doc_status.success("✅ FAQ 문서 생성 완료")
                progress_bar.progress(90)
                
                # 결과를 문서 객체로 변환
                document = {
                    "content": content,
                    "format": output_format,
                    "channel": channel
                }
                
                # 결과 저장 및 표시
                status_text.info("결과를 저장하고 표시하는 중...")
                print("[DEBUG] 결과 저장 및 표시 시작")
                save_and_display_result(document)
                print("[DEBUG] 결과 저장 및 표시 완료")
                
                # 최종 완료 표시
                progress_bar.progress(100)
                status_text.success("✅ FAQ 생성이 완료되었습니다!")
                
        except Exception as e:
            print(f"[ERROR] generate_slack_faq 오류 발생: {str(e)}")
            import traceback
            print(traceback.format_exc())
            st.error(f"오류가 발생했습니다: {str(e)}")
    else:
        print("[DEBUG] 폼이 제출되지 않음")
    
    print("[DEBUG] generate_slack_faq 함수 종료")

async def generate_notion_guide() -> None:
    """노션 가이드 생성 페이지"""
    print("[DEBUG] generate_notion_guide 함수 시작")
    st.header("노션 가이드 생성")
    
    # 입력 폼
    with st.form("notion_guide_form"):
        doc_id = st.text_input("노션 문서 ID 또는 URL")
        output_format = st.radio("출력 형식", ["Markdown", "HTML"])
        submitted = st.form_submit_button("가이드 생성 시작")
        print(f"[DEBUG] 폼 제출 상태: {submitted}")
    
    if submitted and doc_id:
        try:
            print(f"[DEBUG] 가이드 생성 시작 - 문서 ID: {doc_id}")
            
            # 진행 상황 컨테이너 생성
            progress_container = st.container()
            with progress_container:
                # 전체 진행 상태 표시
                progress_bar = st.progress(0)
                status_text = st.empty()
                details_expander = st.expander("자세한 진행 상황")
                
                # 단계별 상태 표시용 컴포넌트
                with details_expander:
                    collector_status = st.empty()
                    extractor_status = st.empty()
                    db_status = st.empty()
                    doc_status = st.empty()
                
                # 초기 상태 설정
                status_text.info("가이드 생성을 준비하는 중...")
                collector_status.info("🔄 노션 데이터 수집 준비 중...")
                extractor_status.info("⏳ 시맨틱 데이터 추출 대기 중...")
                db_status.info("⏳ 데이터베이스 저장 대기 중...")
                doc_status.info("⏳ 문서 생성 대기 중...")
                progress_bar.progress(5)
                
                # 1. Raw Data 수집
                status_text.info("노션 데이터를 수집하는 중...")
                collector_status.info("🔄 NotionCollector 초기화 중...")
                print("[DEBUG] NotionCollector 인스턴스 생성 시작")
                collector = NotionCollector()
                print("[DEBUG] NotionCollector 인스턴스 생성 완료")
                collector_status.success("✅ NotionCollector 초기화 완료")
                progress_bar.progress(10)
                
                collector_status.info(f"🔄 노션 문서 '{doc_id}' 데이터 수집 중...")
                print(f"[DEBUG] collector.collect 호출 시작 - 문서 ID: {doc_id}")
                raw_data = await collector.collect(doc_id)
                doc_count = len(raw_data) if raw_data else 0
                print(f"[DEBUG] collector.collect 호출 완료 - 결과 개수: {doc_count}")
                
                if not raw_data:
                    status_text.error("처리할 데이터가 없습니다.")
                    collector_status.error("❌ 노션 문서에서 데이터를 찾을 수 없습니다.")
                    st.error("처리할 데이터가 없습니다. 문서 ID를 확인해주세요.")
                    print("[DEBUG] 처리할 데이터가 없음")
                    return
                
                # 수집 완료 표시
                # 섹션 개수 계산
                total_sections = sum(len(doc.get("sections", [])) for doc in raw_data)
                collector_status.success(f"✅ 총 {doc_count}개 문서, {total_sections}개 섹션 수집 완료")
                progress_bar.progress(30)
                
                # 2. Semantic Data 추출
                status_text.info("시맨틱 데이터를 추출하는 중...")
                extractor_status.info("🔄 NotionExtractor 초기화 중...")
                print("[DEBUG] NotionExtractor 생성 및 초기화 시작")
                
                # 추출 진행 상황 표시용 컴포넌트
                extract_progress = extractor_status.progress(0)
                extract_text = extractor_status.empty()
                extract_text.info(f"🔄 시맨틱 데이터 추출 중... (0/{total_sections})")
                
                class ProgressUpdater:
                    def update(self, current, total):
                        percentage = int(100 * current / total) if total > 0 else 0
                        extract_progress.progress(percentage / 100)
                        extract_text.info(f"🔄 시맨틱 데이터 추출 중... ({current}/{total})")
                        # 전체 진행 상황도 업데이트
                        overall_progress = 30 + (percentage * 0.3)  # 30%에서 60%까지 할당
                        progress_bar.progress(min(int(overall_progress), 60))
                
                progress_updater = ProgressUpdater()
                
                async with NotionExtractor() as extractor:
                    print("[DEBUG] 시맨틱 데이터 추출 시작")
                    semantic_data = await extractor.extract(raw_data, progress_updater.update)
                    semantic_count = len(semantic_data) if semantic_data else 0
                    print(f"[DEBUG] 시맨틱 데이터 추출 완료 - 결과 개수: {semantic_count}")
                
                # 추출 완료 표시
                extract_text.empty()
                extractor_status.success(f"✅ 총 {semantic_count}개의 시맨틱 데이터 추출 완료")
                progress_bar.progress(60)
                
                # 시맨틱 데이터 저장
                status_text.info("데이터베이스에 저장하는 중...")
                db_status.info("🔄 SQLiteStore 초기화 및 데이터 저장 중...")
                print("[DEBUG] SQLiteStore 인스턴스 생성")
                store = SQLiteStore()
                print("[DEBUG] 시맨틱 데이터 저장 시작")
                await store.store(semantic_data)
                print("[DEBUG] 시맨틱 데이터 저장 완료")
                db_status.success("✅ 데이터베이스 저장 완료")
                progress_bar.progress(70)
                
                # 3. Document 생성
                status_text.info("가이드 문서를 생성하는 중...")
                doc_status.info("🔄 문서 생성기 초기화 및 가이드 생성 중...")
                print("[DEBUG] 문서 생성기 초기화")
                generator = MarkdownGenerator() if output_format == "Markdown" else HTMLGenerator()
                print("[DEBUG] 문서 생성 시작")
                content = await generator.generate(semantic_data, DocumentType.GUIDE)
                print("[DEBUG] 문서 생성 완료")
                doc_status.success("✅ 가이드 문서 생성 완료")
                progress_bar.progress(90)
                
                # 결과 저장
                status_text.info("결과를 저장하고 표시하는 중...")
                print("[DEBUG] 결과 저장 시작")
                today = datetime.now().strftime("%Y%m%d")
                extension = ".md" if output_format == "Markdown" else ".html"
                output_file = f"guide_{today}{extension}"
                output_path = RESULTS_DIR / output_file
                
                await generator.save(content, str(output_path))
                print("[DEBUG] 결과 저장 완료")
                
                st.success(f"가이드가 '{output_file}' 파일에 저장되었습니다.")
                
                # 생성된 문서 표시
                st.subheader("생성된 문서:")
                if output_format == "Markdown":
                    st.markdown(content)
                else:
                    st.components.v1.html(content, height=600)
                
                # 최종 완료 표시
                progress_bar.progress(100)
                status_text.success("✅ 가이드 생성이 완료되었습니다!")
                
        except Exception as e:
            print(f"[ERROR] generate_notion_guide 오류 발생: {str(e)}")
            import traceback
            print(traceback.format_exc())
            st.error(f"오류가 발생했습니다: {str(e)}")
    elif submitted:
        st.warning("노션 문서 ID를 입력해주세요.")
        print("[DEBUG] 노션 문서 ID가 입력되지 않음")
    
    print("[DEBUG] generate_notion_guide 함수 종료")

def sync_generate_slack_faq() -> None:
    """슬랙 FAQ 생성 페이지 (동기 래퍼)"""
    print("[DEBUG] sync_generate_slack_faq 시작")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        print("[DEBUG] generate_slack_faq 비동기 함수 실행 시작")
        loop.run_until_complete(generate_slack_faq())
        print("[DEBUG] generate_slack_faq 비동기 함수 실행 완료")
    except Exception as e:
        print(f"[ERROR] sync_generate_slack_faq 예외 발생: {e}")
        import traceback
        print(traceback.format_exc())
        st.error(f"오류가 발생했습니다: {str(e)}")
    finally:
        print("[DEBUG] 이벤트 루프 종료")
        loop.close()
        print("[DEBUG] sync_generate_slack_faq 종료")

def sync_generate_notion_guide() -> None:
    """노션 가이드 생성 페이지 (동기 래퍼)"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(generate_notion_guide())
    finally:
        loop.close()

def main() -> None:
    """메인 애플리케이션"""
    st.set_page_config(
        page_title="Log2Doc - 대화형 데이터 자동 문서화 시스템",
        page_icon="📚",
        layout="wide"
    )
    
    st.title("Log2Doc - 대화형 데이터 자동 문서화 시스템")
    
    # 사이드바 메뉴
    menu = st.sidebar.selectbox(
        "메뉴 선택",
        ["문서 목록", "슬랙 FAQ 생성", "노션 가이드 생성"]
    )
    
    if menu == "문서 목록":
        list_documents()
    elif menu == "슬랙 FAQ 생성":
        sync_generate_slack_faq()
    elif menu == "노션 가이드 생성":
        sync_generate_notion_guide()

if __name__ == "__main__":
    main() 