import os
import streamlit as st
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
import shutil

# 3계층 아키텍처 구조의 모듈 가져오기
# 1. Repository 계층 - 원본 데이터 소스 접근
from src.repositories.slack_repository import SlackRepository
from src.repositories.notion_repository import NotionRepository

# 2. Processor 계층 - 데이터 정제/분류/적재
from src.processors.slack_processor import SlackProcessor
from src.processors.notion_processor import NotionProcessor
from src.processors.data_store import DataStore

# 3. Document 계층 - 문서 생성/관리
from src.documents.slack_faq_generator import SlackFAQGenerator
from src.documents.ut_debrief_generator import UTDebriefGenerator
from src.documents.document_manager import DocumentManager

# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv(override=True)

# 문서 저장 위치
RESULTS_DIR = Path("results")
RESOURCES_DIR = Path("resources")

# 리소스 디렉토리가 없으면 생성
if not RESOURCES_DIR.exists():
    RESOURCES_DIR.mkdir()

# 데이터 파일 표시 함수
def display_data_files(files, file_type):
    if not files:
        st.info(f"저장된 {file_type} 데이터 파일이 없습니다.")
        return
    
    # 파일 정보 생성
    files_data = []
    for file in files:
        modified_time = datetime.fromtimestamp(file.stat().st_mtime)
        size_kb = file.stat().st_size / 1024
        files_data.append({
            "파일명": file.name,
            "수정일": modified_time,
            "크기(KB)": f"{size_kb:.1f}",
            "경로": str(file)
        })
    
    # 테이블 표시
    df = pd.DataFrame(files_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 데이터 파일 선택 및 작업
    col1, col2 = st.columns(2)
    
    with col1:
        selected_file = st.selectbox("파일 선택", [f["파일명"] for f in files_data], key=f"{file_type}_select")
    
    with col2:
        action = st.selectbox("작업 선택", ["데이터 보기", "데이터 다운로드", "데이터 삭제"], key=f"{file_type}_action")
    
    if selected_file:
        file_path = next((Path(f["경로"]) for f in files_data if f["파일명"] == selected_file), None)
        
        if file_path and action == "데이터 보기":
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            try:
                # JSON 데이터 예쁘게 표시
                data = json.loads(content)
                st.json(data)
            except json.JSONDecodeError:
                # JSON이 아닌 경우 일반 텍스트로 표시
                st.text(content)
            
        elif file_path and action == "데이터 다운로드":
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            st.download_button(
                "데이터 다운로드",
                content,
                file_name=selected_file,
                mime="application/json"
            )
            
        elif file_path and action == "데이터 삭제":
            if st.button("삭제 확인", key=f"{file_type}_delete"):
                os.remove(file_path)
                st.success(f"{selected_file} 파일이 삭제되었습니다.")
                st.rerun()

# 문서 표시 함수
def display_documents(files, doc_type):
    if not files:
        st.info(f"저장된 {doc_type} 문서가 없습니다.")
        return
    
    # 파일 정보 생성
    files_data = []
    for file in files:
        modified_time = datetime.fromtimestamp(file.stat().st_mtime)
        size_kb = file.stat().st_size / 1024
        files_data.append({
            "파일명": file.name,
            "수정일": modified_time,
            "크기(KB)": f"{size_kb:.1f}",
            "경로": str(file)
        })
    
    # 테이블 표시
    df = pd.DataFrame(files_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 문서 선택 및 작업
    col1, col2 = st.columns(2)
    
    with col1:
        selected_file = st.selectbox("문서 선택", [f["파일명"] for f in files_data], key=f"{doc_type}_select")
    
    with col2:
        action = st.selectbox("작업 선택", ["문서 보기", "문서 다운로드", "문서 삭제"], key=f"{doc_type}_action")
    
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

# 문서 목록 함수
def list_documents():
    st.header("문서 목록")
    
    # 문서 탭 나누기
    doc_tabs = st.tabs(["FAQ 문서", "UT Debrief 문서", "기타 문서"])
    
    with doc_tabs[0]:
        st.subheader("FAQ 문서")
        faq_files = list(RESULTS_DIR.glob("faq_*.md"))
        display_documents(faq_files, "FAQ")
    
    with doc_tabs[1]:
        st.subheader("UT Debrief 문서")
        ut_files = list(RESULTS_DIR.glob("ut_*.md"))
        display_documents(ut_files, "UT")
    
    with doc_tabs[2]:
        st.subheader("기타 문서")
        other_files = [f for f in RESULTS_DIR.glob("*.md") 
                     if not (f.name.startswith("faq_") or f.name.startswith("ut_"))]
        display_documents(other_files, "기타")

# 슬랙 FAQ 생성 함수
def generate_slack_faq_gui():
    st.header("슬랙 FAQ 생성")
    
    # 입력 폼
    with st.form("slack_faq_form"):
        channel_name = st.text_input("슬랙 채널 이름 (# 제외)")
        days = st.number_input("검색할 기간(일)", min_value=1, max_value=30, value=7)
        
        output_options = ["자동 생성", "기존 파일 업데이트"]
        output_option = st.radio("출력 옵션", output_options)
        
        if output_option == "기존 파일 업데이트":
            existing_files = [f.name for f in RESULTS_DIR.glob("faq_*.md")]
            if existing_files:
                output_file = st.selectbox("업데이트할 파일 선택", existing_files)
            else:
                st.warning("업데이트할 기존 FAQ 파일이 없습니다.")
                output_file = None
                output_option = "자동 생성"
        else:
            output_file = None
        
        submitted = st.form_submit_button("FAQ 생성 시작")
    
    if submitted and channel_name:
        update_existing = (output_option == "기존 파일 업데이트")
        
        with st.spinner("슬랙 FAQ를 생성 중입니다..."):
            try:
                # 1. Repository 계층: 슬랙 스레드 가져오기
                st.info("슬랙 스레드를 가져오는 중...")
                slack_repository = SlackRepository()
                threads = slack_repository.fetch_recent_threads(channel_name, days)
                
                if not threads:
                    st.error("처리할 스레드가 없습니다.")
                    return
                
                # 2. Processor 계층: 스레드 처리 및 정제
                st.info("스레드 데이터 처리 중...")
                slack_processor = SlackProcessor()
                processed_threads = slack_processor._process_thread_data(threads)
                
                # 처리된 데이터 저장 (data/slack 디렉토리에)
                data_store = DataStore()
                data_store.save_processed_slack_data(channel_name, processed_threads)
                
                # 3. Document 계층: FAQ 문서 생성
                st.info("FAQ 생성 중...")
                faq_generator = SlackFAQGenerator()
                faq_markdown = faq_generator.generate_faq(processed_threads, channel_name)
                
                # 결과 저장
                final_output_file = output_file
                if final_output_file is None:
                    today = datetime.now().strftime("%Y%m%d")
                    final_output_file = f"faq_{channel_name}_{today}.md"
                
                output_path = RESULTS_DIR / final_output_file
                
                # 기존 문서 업데이트 여부 확인
                if update_existing and output_path.exists():
                    st.info(f"기존 문서를 업데이트합니다.")
                    document_manager = DocumentManager()
                    faq_markdown = document_manager.update_faq_document(str(output_path), faq_markdown)
                
                # 결과 저장
                faq_generator.save_faq_document(faq_markdown, channel_name, final_output_file)
                
                action_text = "업데이트" if update_existing and output_path.exists() else "저장"
                st.success(f"FAQ가 '{final_output_file}' 파일에 {action_text}되었습니다.")
                
                # 생성된 문서 표시
                st.subheader("생성된 문서:")
                st.markdown(faq_markdown)
                
            except Exception as e:
                st.error(f"FAQ 생성 중 오류가 발생했습니다: {str(e)}")
    
    elif submitted:
        st.warning("슬랙 채널 이름을 입력해주세요.")

# UT Debrief 생성 함수
def generate_ut_debrief_gui():
    st.header("UT Debrief 생성")
    
    # 입력 폼
    with st.form("ut_debrief_form"):
        notion_doc_id = st.text_input("노션 문서 ID 또는 URL")
        
        output_options = ["자동 생성", "기존 파일 업데이트"]
        output_option = st.radio("출력 옵션", output_options)
        
        if output_option == "기존 파일 업데이트":
            existing_files = [f.name for f in RESULTS_DIR.glob("ut_*.md")]
            if existing_files:
                output_file = st.selectbox("업데이트할 파일 선택", existing_files)
            else:
                st.warning("업데이트할 기존 UT Debrief 파일이 없습니다.")
                output_file = None
                output_option = "자동 생성"
        else:
            output_file = None
        
        submitted = st.form_submit_button("Debrief 생성 시작")
    
    if submitted and notion_doc_id:
        update_existing = (output_option == "기존 파일 업데이트")
        
        with st.spinner("UT Debrief를 생성 중입니다..."):
            try:
                # 1. Repository 계층: 노션 문서 가져오기
                st.info("노션 문서를 가져오는 중...")
                notion_repository = NotionRepository()
                transcript = notion_repository.get_ut_transcript(notion_doc_id)
                
                if not transcript:
                    st.error("노션 문서를 가져오는 데 실패했습니다.")
                    return
                
                # 2. Processor 계층: 녹취록 처리 및 정제
                st.info("녹취록 데이터 처리 중...")
                notion_processor = NotionProcessor()
                processed_data = notion_processor._process_transcript_data(transcript)
                
                # 처리된 데이터 저장 (data/notion 디렉토리에)
                data_store = DataStore()
                data_store.save_processed_notion_data(notion_doc_id, processed_data)
                
                # 3. Document 계층: Debrief 문서 생성
                st.info("Debrief 생성 중...")
                debrief_generator = UTDebriefGenerator()
                debrief_markdown = debrief_generator.generate_debrief(processed_data)
                
                # 결과 저장
                final_output_file = output_file
                if final_output_file is None:
                    today = datetime.now().strftime("%Y%m%d")
                    final_output_file = f"ut_debrief_{today}.md"
                
                output_path = RESULTS_DIR / final_output_file
                
                # 기존 문서 업데이트 여부 확인
                if update_existing and output_path.exists():
                    st.info(f"기존 문서를 업데이트합니다.")
                    document_manager = DocumentManager()
                    debrief_markdown = document_manager.update_ut_document(str(output_path), debrief_markdown)
                
                # 결과 저장
                debrief_generator.save_debrief_document(debrief_markdown, final_output_file)
                
                action_text = "업데이트" if update_existing and output_path.exists() else "저장"
                st.success(f"UT Debrief가 '{final_output_file}' 파일에 {action_text}되었습니다.")
                
                # 생성된 문서 표시
                st.subheader("생성된 문서:")
                st.markdown(debrief_markdown)
                
            except Exception as e:
                st.error(f"Debrief 생성 중 오류가 발생했습니다: {str(e)}")
    
    elif submitted:
        st.warning("노션 문서 ID를 입력해주세요.")

# 리소스 관리 함수
def manage_resources():
    st.header("리소스 관리")
    
    # 리소스 업로드 섹션
    st.subheader("리소스 업로드")
    
    with st.form("resource_upload_form"):
        uploaded_file = st.file_uploader("파일 선택", type=["pdf", "docx", "xlsx", "csv", "json", "txt", "md"])
        resource_category = st.selectbox(
            "카테고리", 
            ["문서", "데이터", "이미지", "기타"]
        )
        resource_description = st.text_area("설명")
        submit_button = st.form_submit_button("업로드")
    
    if submit_button and uploaded_file is not None:
        try:
            # 파일 정보 저장
            file_info = {
                "파일명": uploaded_file.name,
                "카테고리": resource_category,
                "설명": resource_description,
                "업로드일": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "크기": f"{uploaded_file.size / 1024:.1f} KB"
            }
            
            # 리소스 메타데이터 저장
            metadata_file = RESOURCES_DIR / "metadata.json"
            
            if metadata_file.exists():
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            else:
                metadata = {"resources": []}
            
            metadata["resources"].append(file_info)
            
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # 파일 저장
            file_path = RESOURCES_DIR / uploaded_file.name
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.success(f"리소스 '{uploaded_file.name}'가 업로드되었습니다.")
            
        except Exception as e:
            st.error(f"리소스 업로드 중 오류가 발생했습니다: {str(e)}")
    
    # 리소스 목록 표시
    st.subheader("리소스 목록")
    
    metadata_file = RESOURCES_DIR / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        if metadata["resources"]:
            df = pd.DataFrame(metadata["resources"])
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # 리소스 선택 및 작업
            col1, col2 = st.columns(2)
            
            with col1:
                if "resources" in metadata and metadata["resources"]:
                    selected_resource = st.selectbox(
                        "리소스 선택", 
                        [r["파일명"] for r in metadata["resources"]]
                    )
                else:
                    selected_resource = None
            
            with col2:
                if selected_resource:
                    action = st.selectbox(
                        "작업 선택", 
                        ["다운로드", "삭제"]
                    )
            
            if selected_resource:
                resource_path = RESOURCES_DIR / selected_resource
                
                if action == "다운로드":
                    if resource_path.exists():
                        with open(resource_path, "rb") as f:
                            content = f.read()
                        
                        st.download_button(
                            "리소스 다운로드",
                            content,
                            file_name=selected_resource,
                            mime="application/octet-stream"
                        )
                    else:
                        st.error(f"리소스 파일을 찾을 수 없습니다: {selected_resource}")
                
                elif action == "삭제":
                    if st.button("삭제 확인"):
                        try:
                            # 파일 삭제
                            if resource_path.exists():
                                os.remove(resource_path)
                            
                            # 메타데이터에서 제거
                            metadata["resources"] = [
                                r for r in metadata["resources"] 
                                if r["파일명"] != selected_resource
                            ]
                            
                            with open(metadata_file, "w", encoding="utf-8") as f:
                                json.dump(metadata, f, ensure_ascii=False, indent=2)
                            
                            st.success(f"리소스 '{selected_resource}'가 삭제되었습니다.")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"리소스 삭제 중 오류가 발생했습니다: {str(e)}")
        else:
            st.info("저장된 리소스가 없습니다.")
    else:
        st.info("저장된 리소스가 없습니다.")

# 앱 제목 설정
st.set_page_config(page_title="AI FAQ 문서 관리 시스템", layout="wide")
st.title("AI FAQ 문서 관리 시스템")

# 사이드바 메뉴
st.sidebar.title("메뉴")
main_menu = st.sidebar.radio(
    "카테고리 선택",
    ["데이터 관리", "문서 생성", "리소스 관리"]
)

# 데이터 관리 메뉴 표시
if main_menu == "데이터 관리":
    data_menu = st.sidebar.radio(
        "데이터 관리",
        ["Repository 데이터", "Processor 데이터", "Document 목록"]
    )
    
    if data_menu == "Repository 데이터":
        st.header("Repository 데이터")
        repo_tabs = st.tabs(["슬랙 데이터", "노션 데이터"])
        
        with repo_tabs[0]:
            st.subheader("슬랙 Repository 데이터")
            # Repository 데이터 디렉토리 탐색
            slack_data_path = Path("data/slack")
            if slack_data_path.exists():
                slack_files = list(slack_data_path.glob("*.json"))
                display_data_files(slack_files, "슬랙")
            else:
                st.info("슬랙 데이터가 아직 없습니다.")
        
        with repo_tabs[1]:
            st.subheader("노션 Repository 데이터")
            notion_data_path = Path("data/notion")
            if notion_data_path.exists():
                notion_files = list(notion_data_path.glob("*.json"))
                display_data_files(notion_files, "노션")
            else:
                st.info("노션 데이터가 아직 없습니다.")
    
    elif data_menu == "Processor 데이터":
        st.header("Processor 데이터")
        proc_tabs = st.tabs(["슬랙 처리 데이터", "노션 처리 데이터"])
        
        with proc_tabs[0]:
            st.subheader("슬랙 Processor 데이터")
            processed_slack_path = Path("data/processed/slack")
            if processed_slack_path.exists():
                processed_files = list(processed_slack_path.glob("*.json"))
                display_data_files(processed_files, "슬랙 처리")
            else:
                st.info("처리된 슬랙 데이터가 아직 없습니다.")
        
        with proc_tabs[1]:
            st.subheader("노션 Processor 데이터")
            processed_notion_path = Path("data/processed/notion")
            if processed_notion_path.exists():
                processed_files = list(processed_notion_path.glob("*.json"))
                display_data_files(processed_files, "노션 처리")
            else:
                st.info("처리된 노션 데이터가 아직 없습니다.")
    
    elif data_menu == "Document 목록":
        list_documents()

# 문서 생성 메뉴 표시
elif main_menu == "문서 생성":
    doc_menu = st.sidebar.radio(
        "문서 생성",
        ["슬랙 FAQ 생성", "UT Debrief 생성"]
    )
    
    if doc_menu == "슬랙 FAQ 생성":
        generate_slack_faq_gui()
    
    elif doc_menu == "UT Debrief 생성":
        generate_ut_debrief_gui()

# 리소스 관리 메뉴 표시
elif main_menu == "리소스 관리":
    manage_resources()

# 앱 실행 방법 안내
st.sidebar.markdown("---")
st.sidebar.subheader("앱 실행 방법")
st.sidebar.code("streamlit run app.py") 