"""
Glossary Semantic Data Extractor

용어집 데이터를 추출하는 모듈입니다.
"""

import os
from typing import Dict, Any, List, Optional, Callable

from .. import SemanticExtractor
from ..core import LLMClient, PromptTemplateFactory

class GlossaryExtractor(SemanticExtractor):
    """용어집 데이터를 추출하는 클래스"""
    
    def __init__(self, config: Dict[str, Any] = None, llm_client: Optional[LLMClient] = None):
        """
        초기화
        
        Args:
            config: OpenAI API 키 등 설정 정보
            llm_client: LLM 클라이언트 (없으면 새로 생성)
        """
        api_key = config.get("openai_api_key") if config else os.environ.get("OPENAI_API_KEY")
        self.llm_client = llm_client or LLMClient(api_key=api_key)
        
        # 부모 클래스 초기화
        super().__init__(prompt_templates=None)
        
        # 프롬프트 템플릿 등록
        # 슬랙 용어집 템플릿
        slack_templates = PromptTemplateFactory.create_slack_templates(self.llm_client)
        self.register_prompt_template("glossary", slack_templates["glossary"])
        
        # 노션 용어집 템플릿
        notion_templates = PromptTemplateFactory.create_notion_templates(self.llm_client)
        if "glossary" in notion_templates:
            self.register_prompt_template("notion_glossary", notion_templates["glossary"])
    
    async def __aenter__(self):
        """비동기 컨텍스트 관리자 진입"""
        await self.llm_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 관리자 종료"""
        await self.llm_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def close(self):
        """리소스 정리"""
        await self.llm_client.close()
    
    async def extract(self, raw_data: Dict[str, Any],
                     progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict[str, Any]]:
        """
        데이터에서 용어집 항목 추출
        
        Args:
            raw_data: 처리할 데이터 (슬랙 메시지, 노션 문서 등)
            progress_callback: 진행 상황을 업데이트할 콜백 함수 (current, total)
            
        Returns:
            추출된 용어집 데이터 목록
        """
        semantic_data = []
        
        # 슬랙 메시지 처리
        if "messages" in raw_data:
            # 단일 스레드 데이터인 경우
            if isinstance(raw_data["messages"], list):
                if "glossary" in self.prompt_templates:
                    results = await self.prompt_templates["glossary"].process(raw_data)
                    semantic_data.extend(results)
            
            # 여러 스레드 목록인 경우
            elif isinstance(raw_data["messages"], dict):
                threads = list(raw_data["messages"].values())
                total = len(threads)
                
                for i, thread in enumerate(threads):
                    # 진행 상황 업데이트
                    if progress_callback:
                        progress_callback(i, total)
                    
                    if "glossary" in self.prompt_templates:
                        thread_data = {"messages": thread}
                        results = await self.prompt_templates["glossary"].process(thread_data)
                        semantic_data.extend(results)
        
        # 노션 데이터 처리
        elif "pages" in raw_data:
            pages = raw_data.get("pages", [])
            total = len(pages)
            
            for i, page in enumerate(pages):
                # 진행 상황 업데이트
                if progress_callback:
                    progress_callback(i, total)
                
                if "notion_glossary" in self.prompt_templates:
                    sections = page.get("sections", [])
                    document = {
                        "id": page.get("id", ""),
                        "title": page.get("title", "")
                    }
                    
                    for section in sections:
                        section_data = {
                            "section": section,
                            "document": document
                        }
                        
                        results = await self.prompt_templates["notion_glossary"].process(section_data)
                        semantic_data.extend(results)
        
        # 최종 진행 상황 업데이트
        if progress_callback:
            progress_callback(1, 1)
            
        return semantic_data 