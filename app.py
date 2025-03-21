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

async def generate_glossary() -> None:
    """용어집 생성 페이지"""
    print("[DEBUG] generate_glossary 함수 시작")
    st.header("용어집 생성")
    
    with st.form("glossary_form"):
        # 데이터 소스 선택
        data_source = st.radio(
            "데이터 소스 선택",
            ["예제 데이터", "슬랙", "노션"],
            help="용어집을 생성할 데이터 소스를 선택하세요"
        )
        
        # 데이터 소스별 추가 입력 필드
        if data_source == "슬랙":
            channel = st.text_input(
                "채널 이름",
                help="용어를 수집할 슬랙 채널 이름을 입력하세요 (예: general)"
            )
            days = st.number_input(
                "검색 기간 (일)",
                min_value=1,
                max_value=30,
                value=7,
                help="최근 몇 일 동안의 대화를 검색할지 선택하세요"
            )
        elif data_source == "노션":
            doc_id = st.text_input(
                "노션 문서 ID 또는 URL",
                help="용어를 수집할 노션 문서의 ID나 URL을 입력하세요"
            )
        
        output_format = st.selectbox(
            "출력 형식",
            ["markdown", "html"],
            help="생성된 용어집의 출력 형식을 선택하세요"
        )
        
        submitted = st.form_submit_button("용어집 생성")
        print(f"[DEBUG] 폼 제출 상태: {submitted}")
        
    if submitted:
        try:
            print(f"[DEBUG] 용어집 생성 시작 - 데이터 소스: {data_source}")
            
            # 입력값 검증
            if data_source == "슬랙" and not channel:
                st.warning("슬랙 채널 이름을 입력해주세요.")
                return
            if data_source == "노션" and not doc_id:
                st.warning("노션 문서 ID를 입력해주세요.")
                return
            
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
                status_text.info("용어집 생성을 준비하는 중...")
                collector_status.info("🔄 데이터 수집 준비 중...")
                extractor_status.info("⏳ 시맨틱 데이터 추출 대기 중...")
                db_status.info("⏳ 데이터베이스 저장 대기 중...")
                doc_status.info("⏳ 문서 생성 대기 중...")
                progress_bar.progress(5)
                
                # 데이터 수집 및 추출
                semantic_data = []
                
                if data_source == "예제 데이터":
                    # 예제 데이터 생성
                    collector_status.info("🔄 예제 용어집 데이터 생성 중...")
                    print("[DEBUG] 예제 용어집 데이터 생성 시작")
                    
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
                    
                    print("[DEBUG] 예제 용어집 데이터 생성 완료")
                    collector_status.success("✅ 예제 용어집 데이터 생성 완료")
                    extractor_status.success("✅ 시맨틱 데이터 추출 완료")
                    progress_bar.progress(30)
                    
                elif data_source == "슬랙":
                    # 슬랙 데이터 수집
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
                        extracted_data = await extractor.extract(threads, progress_updater.update)
                        semantic_count = len(extracted_data) if extracted_data else 0
                        print(f"[DEBUG] 시맨틱 데이터 추출 완료 - 결과 개수: {semantic_count}")
                    
                    # 추출 완료 표시
                    extract_text.empty()
                    extractor_status.success(f"✅ 총 {semantic_count}개의 시맨틱 데이터 추출 완료")
                    progress_bar.progress(60)
                    
                    # 용어 참조 데이터만 필터링
                    semantic_data = [d for d in extracted_data if d["type"] == SemanticType.REFERENCE]
                    reference_count = len(semantic_data)
                    print(f"[DEBUG] 참조 데이터 필터링 완료 - 용어 개수: {reference_count}")
                    
                    if not semantic_data:
                        extract_text.warning("⚠️ 용어 데이터가 없습니다. 다른 채널을 시도해보세요.")
                    
                elif data_source == "노션":
                    # 노션 데이터 수집
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
                        extracted_data = await extractor.extract(raw_data, progress_updater.update)
                        semantic_count = len(extracted_data) if extracted_data else 0
                        print(f"[DEBUG] 시맨틱 데이터 추출 완료 - 결과 개수: {semantic_count}")
                    
                    # 추출 완료 표시
                    extract_text.empty()
                    extractor_status.success(f"✅ 총 {semantic_count}개의 시맨틱 데이터 추출 완료")
                    progress_bar.progress(60)
                    
                    # 용어 참조 데이터만 필터링
                    semantic_data = [d for d in extracted_data if d["type"] == SemanticType.REFERENCE]
                    reference_count = len(semantic_data)
                    print(f"[DEBUG] 참조 데이터 필터링 완료 - 용어 개수: {reference_count}")
                    
                    if not semantic_data:
                        extract_text.warning("⚠️ 용어 데이터가 없습니다. 다른 문서를 시도해보세요.")
                
                # 시맨틱 데이터가 비어있는지 확인
                if not semantic_data:
                    if data_source != "예제 데이터":
                        status_text.warning("용어 데이터를 찾을 수 없습니다.")
                        st.warning("용어 데이터를 찾을 수 없습니다. 다른 소스를 시도하거나 예제 데이터를 사용해보세요.")
                        return
                
                # 시맨틱 데이터 저장
                status_text.info("데이터베이스에 저장하는 중...")
                db_status.info("🔄 시맨틱 데이터 저장 중...")
                print("[DEBUG] 데이터베이스 저장 시작")
                store = SQLiteStore()
                await store.store(semantic_data)
                print("[DEBUG] 데이터베이스 저장 완료")
                db_status.success("✅ 데이터베이스 저장 완료")
                progress_bar.progress(70)
                
                # 문서 생성
                status_text.info("용어집 문서를 생성하는 중...")
                doc_status.info("🔄 문서 생성기 초기화 및 용어집 생성 중...")
                print("[DEBUG] 문서 생성기 초기화")
                generator = MarkdownGenerator() if output_format == "markdown" else HTMLGenerator()
                print("[DEBUG] 문서 생성 시작")
                content = await generator.generate(
                    semantic_data,
                    DocumentType.GLOSSARY
                )
                print("[DEBUG] 문서 생성 완료")
                doc_status.success("✅ 용어집 문서 생성 완료")
                progress_bar.progress(90)
                
                # 결과 저장
                status_text.info("결과를 저장하고 표시하는 중...")
                print("[DEBUG] 결과 저장 시작")
                today = datetime.now().strftime("%Y%m%d")
                source_name = "example"
                if data_source == "슬랙":
                    source_name = channel
                elif data_source == "노션":
                    source_name = "notion"
                
                extension = ".md" if output_format == "markdown" else ".html"
                output_file = f"glossary_{source_name}_{today}{extension}"
                output_path = RESULTS_DIR / output_file
                
                await generator.save(content, str(output_path))
                print("[DEBUG] 결과 저장 완료")
                
                st.success(f"용어집이 '{output_file}' 파일에 저장되었습니다.")
                
                # 생성된 문서 표시
                st.subheader("생성된 문서:")
                if output_format == "markdown":
                    st.markdown(content)
                else:
                    st.components.v1.html(content, height=600)
                
                # 최종 완료 표시
                progress_bar.progress(100)
                status_text.success("✅ 용어집 생성이 완료되었습니다!")
                
        except Exception as e:
            print(f"[ERROR] generate_glossary 오류 발생: {str(e)}")
            import traceback
            print(traceback.format_exc())
            st.error(f"오류가 발생했습니다: {str(e)}")
    else:
        print("[DEBUG] 폼이 제출되지 않음")
    
    print("[DEBUG] generate_glossary 함수 종료")

def sync_generate_slack_faq() -> None:
    """generate_slack_faq의 동기 래퍼"""
    try:
        asyncio.run(generate_slack_faq())
    except Exception as e:
        st.error(f"오류가 발생했습니다: {str(e)}")

def sync_generate_notion_guide() -> None:
    """generate_notion_guide의 동기 래퍼"""
    try:
        asyncio.run(generate_notion_guide())
    except Exception as e:
        st.error(f"오류가 발생했습니다: {str(e)}")

def sync_generate_glossary() -> None:
    """generate_glossary의 동기 래퍼"""
    try:
        asyncio.run(generate_glossary())
    except Exception as e:
        st.error(f"오류가 발생했습니다: {str(e)}")

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
        ["문서 목록", "슬랙 FAQ 생성", "노션 가이드 생성", "용어집 생성"]
    )
    
    if menu == "문서 목록":
        list_documents()
    elif menu == "슬랙 FAQ 생성":
        sync_generate_slack_faq()
    elif menu == "노션 가이드 생성":
        sync_generate_notion_guide()
    elif menu == "용어집 생성":
        sync_generate_glossary()

if __name__ == "__main__":
    main() 