import streamlit as st
import asyncio
import json
import os
import time
from typing import Callable, Coroutine

# 각 모듈 임포트
from src.raw_data import SlackCollector, NotionCollector
from src.semantic_data import (
    SemanticType,
    SlackExtractor, NotionExtractor
)
from src.document import DocumentType, MarkdownGenerator

# 페이지 설정
st.set_page_config(page_title="Log2Doc Playground", layout="wide")

# 세션 상태 초기화
if "raw_data" not in st.session_state:
    st.session_state.raw_data = None
if "semantic_data" not in st.session_state:
    st.session_state.semantic_data = None
if "generated_document" not in st.session_state:
    st.session_state.generated_document = None

# 비동기 함수를 동기적으로 실행하는 헬퍼 함수
def run_async(coro_func: Callable[..., Coroutine], *args, **kwargs):
    """
    비동기 함수를 동기적으로 실행하는 헬퍼 함수
    
    Args:
        coro_func: 코루틴 함수 (async def로 정의된 함수)
        *args: 코루틴 함수에 전달할 위치 인자
        **kwargs: 코루틴 함수에 전달할 키워드 인자
        
    Returns:
        코루틴 함수의 실행 결과
    """
    async def wrapper():
        return await coro_func(*args, **kwargs)
    return asyncio.run(wrapper())

# 헤더
st.title("Log2Doc Playground")
st.markdown("각 데이터 처리 단계를 독립적으로 시뮬레이션할 수 있는 Playground입니다.")

# 탭 생성
tab1, tab2, tab3 = st.tabs(["1. Raw Data Collection", "2. Semantic Data Extraction", "3. Document Generation"])

# 탭 1: Raw Data Collection
with tab1:
    st.header("원본 데이터 수집")
    
    col1, col2 = st.columns(2)
    
    with col1:
        collector_type = st.selectbox(
            "데이터 수집기 선택",
            ["Slack", "Notion"]
        )
        
        if collector_type == "Slack":
            st.subheader("Slack 설정")
            slack_token = st.text_input("Slack Token", value=os.getenv("SLACK_TOKEN", ""), type="password")
            channel_id = st.text_input("Channel ID", value=os.getenv("SLACK_CHANNEL_ID", ""))
            days = st.number_input("검색 기간 (일)", min_value=1, max_value=30, value=3)
            
            if st.button("Slack 데이터 수집"):
                with st.spinner("Slack에서 데이터를 수집하는 중..."):
                    # config 딕셔너리를 사용하여 SlackCollector 초기화
                    collector = SlackCollector(config={"slack_token": slack_token})
                    
                    try:
                        # SlackCollector.collect를 호출하여 데이터 수집
                        st.session_state.raw_data = run_async(collector.collect, channel_id, days)
                        st.success(f"Slack 데이터 수집 완료!")
                    except Exception as e:
                        st.error(f"데이터 수집 오류: {str(e)}")
                
        elif collector_type == "Notion":
            st.subheader("Notion 설정")
            notion_token = st.text_input("Notion Token", value=os.getenv("NOTION_TOKEN", ""), type="password")
            database_id = st.text_input("Database ID", value=os.getenv("NOTION_DATABASE_ID", ""))
            
            if st.button("Notion 데이터 수집"):
                with st.spinner("Notion에서 데이터를 수집하는 중..."):
                    collector = NotionCollector(config={"notion_token": notion_token})
                    try:
                        # NotionCollector.collect를 호출하여 데이터 수집
                        st.session_state.raw_data = run_async(collector.collect, database_id)
                        st.success(f"Notion 데이터 수집 완료!")
                    except Exception as e:
                        st.error(f"데이터 수집 오류: {str(e)}")
    
    with col2:
        st.subheader("수집된 원본 데이터")
        if st.session_state.raw_data:
            # 데이터 미리보기
            if isinstance(st.session_state.raw_data, list):
                # JSON 배열인 경우 더 보기 좋게 표시
                preview_data = json.dumps(st.session_state.raw_data[:20], indent=2, ensure_ascii=False)
                if len(st.session_state.raw_data) > 20:
                    preview_data += f"\n\n... 외 {len(st.session_state.raw_data) - 20}개 항목"
            else:
                # 다른 형태의 데이터인 경우
                preview_data = json.dumps(st.session_state.raw_data, indent=2, ensure_ascii=False)
                if len(preview_data) > 10000:
                    preview_data = preview_data[:10000] + "..."
            
            st.text_area("원본 데이터 미리보기", value=preview_data, height=400, disabled=True)
            
            # 파일로 저장 옵션
            if st.button("원본 데이터 JSON으로 저장"):
                try:
                    os.makedirs("data/raw", exist_ok=True)
                    filename = f"data/raw/{collector_type.lower()}_data_{int(time.time())}.json"
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(st.session_state.raw_data, f, indent=2, ensure_ascii=False)
                    st.success(f"원본 데이터를 {filename}에 저장했습니다!")
                except Exception as e:
                    st.error(f"파일 저장 오류: {str(e)}")
        else:
            st.info("원본 데이터를 수집하려면 왼쪽에서 데이터 소스를 설정하고 수집 버튼을 클릭하세요.")
        
        # 파일에서 로드 옵션
        st.subheader("파일에서 원본 데이터 로드")
        uploaded_file = st.file_uploader("JSON 파일 업로드", type=["json"], key="raw_data_upload")
        if uploaded_file is not None:
            try:
                st.session_state.raw_data = json.load(uploaded_file)
                st.success("파일에서 원본 데이터를 로드했습니다!")
            except Exception as e:
                st.error(f"파일 로드 오류: {str(e)}")

# 탭 2: Semantic Data Extraction
with tab2:
    st.header("시맨틱 데이터 추출")
    
    col1, col2 = st.columns(2)
    
    with col1:
        extractor_type = st.selectbox(
            "데이터 추출기 선택",
            ["Slack", "Notion"]
        )
        
        # 원본 데이터 소스
        data_source = st.radio(
            "데이터 소스",
            ["이전 단계에서 수집한 데이터", "직접 입력"]
        )
        
        raw_data_input = None
        
        if data_source == "이전 단계에서 수집한 데이터":
            if st.session_state.raw_data:
                st.success("이전 단계에서 수집한 데이터를 사용합니다.")
                raw_data_input = st.session_state.raw_data
            else:
                st.warning("이전 단계에서 수집한 데이터가 없습니다. 먼저 '원본 데이터 수집' 탭에서 데이터를 수집하세요.")
        else:
            raw_data_json = st.text_area("원본 데이터 (JSON)", height=300)
            if raw_data_json:
                try:
                    raw_data_input = json.loads(raw_data_json)
                except Exception as e:
                    st.error(f"JSON 파싱 오류: {str(e)}")
        
        if raw_data_input and st.button("시맨틱 데이터 추출"):
            with st.spinner("시맨틱 데이터를 추출하는 중..."):
                try:
                    if extractor_type == "Slack":
                        extractor = SlackExtractor()
                    else:
                        extractor = NotionExtractor()
                    
                    # extract 메서드 호출 수정
                    st.session_state.semantic_data = run_async(extractor.extract, raw_data_input)
                    st.success(f"{len(st.session_state.semantic_data)}개의 시맨틱 데이터 항목을 추출했습니다!")
                except Exception as e:
                    st.error(f"데이터 추출 오류: {str(e)}")
    
    with col2:
        st.subheader("추출된 시맨틱 데이터")
        if st.session_state.semantic_data:
            # 데이터 필터링 옵션
            semantic_types = ["모두 표시"]
            semantic_types.extend([t for t in dir(SemanticType) if not t.startswith("__")])
            selected_type = st.selectbox("시맨틱 데이터 유형 필터링", semantic_types)
            
            filtered_data = st.session_state.semantic_data
            if selected_type != "모두 표시":
                type_value = getattr(SemanticType, selected_type)
                filtered_data = [item for item in st.session_state.semantic_data 
                                if item.get("type") == type_value]
            
            # 데이터 표시
            st.text(f"총 {len(filtered_data)}개 항목")
            st.json(json.dumps(filtered_data, indent=2, ensure_ascii=False))
            
            # 파일로 저장 옵션
            if st.button("시맨틱 데이터 JSON으로 저장"):
                try:
                    os.makedirs("data/semantic", exist_ok=True)
                    filename = f"data/semantic/{extractor_type.lower()}_semantic_{int(time.time())}.json"
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(st.session_state.semantic_data, f, indent=2, ensure_ascii=False)
                    st.success(f"시맨틱 데이터를 {filename}에 저장했습니다!")
                except Exception as e:
                    st.error(f"파일 저장 오류: {str(e)}")
        else:
            st.info("시맨틱 데이터를 추출하려면 왼쪽에서 설정을 완료하고 추출 버튼을 클릭하세요.")
        
        # 파일에서 로드 옵션
        st.subheader("파일에서 시맨틱 데이터 로드")
        uploaded_file = st.file_uploader("시맨틱 데이터 JSON 파일 업로드", type=["json"], key="semantic_data_upload")
        if uploaded_file is not None:
            try:
                st.session_state.semantic_data = json.load(uploaded_file)
                st.success("파일에서 시맨틱 데이터를 로드했습니다!")
            except Exception as e:
                st.error(f"파일 로드 오류: {str(e)}")

# 탭 3: Document Generation
with tab3:
    st.header("문서 생성")
    
    col1, col2 = st.columns(2)
    
    with col1:
        doc_type = st.selectbox(
            "문서 유형",
            [getattr(DocumentType, t) for t in dir(DocumentType) if not t.startswith("__") and t.isupper()]
        )
        
        # 시맨틱 데이터 소스
        data_source = st.radio(
            "데이터 소스",
            ["이전 단계에서 추출한 데이터", "직접 입력"],
            key="doc_data_source"
        )
        
        semantic_data_input = None
        
        if data_source == "이전 단계에서 추출한 데이터":
            if st.session_state.semantic_data:
                st.success("이전 단계에서 추출한 데이터를 사용합니다.")
                semantic_data_input = st.session_state.semantic_data
            else:
                st.warning("이전 단계에서 추출한 데이터가 없습니다. 먼저 '시맨틱 데이터 추출' 탭에서 데이터를 추출하세요.")
        else:
            semantic_data_json = st.text_area("시맨틱 데이터 (JSON)", height=300)
            if semantic_data_json:
                try:
                    semantic_data_input = json.loads(semantic_data_json)
                except Exception as e:
                    st.error(f"JSON 파싱 오류: {str(e)}")
        
        output_path = st.text_input("저장 경로 (옵션)", value="results/")
        
        if semantic_data_input and st.button("문서 생성"):
            with st.spinner("문서를 생성하는 중..."):
                try:
                    generator = MarkdownGenerator()
                    
                    # generate 메서드 호출 수정
                    document_content = run_async(generator.generate, semantic_data_input, doc_type)
                    st.session_state.generated_document = document_content
                    
                    # 문서 저장 (옵션)
                    if output_path:
                        os.makedirs(output_path, exist_ok=True)
                        filename = f"{output_path}/{doc_type}_{int(time.time())}.md"
                        run_async(generator.save, document_content, filename)
                        st.success(f"문서를 {filename}에 저장했습니다!")
                    
                    st.success("문서 생성이 완료되었습니다!")
                except Exception as e:
                    st.error(f"문서 생성 오류: {str(e)}")
    
    with col2:
        st.subheader("생성된 문서")
        if st.session_state.generated_document:
            st.markdown(st.session_state.generated_document)
            
            # 다운로드 버튼
            st.download_button(
                label="Markdown 다운로드",
                data=st.session_state.generated_document,
                file_name=f"document.md",
                mime="text/plain"
            )
        else:
            st.info("문서를 생성하려면 왼쪽에서 설정을 완료하고 생성 버튼을 클릭하세요.")

# 푸터
st.markdown("---")
st.markdown("Log2Doc Playground © 2024") 