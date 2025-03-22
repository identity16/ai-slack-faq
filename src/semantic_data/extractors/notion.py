"""
Notion Semantic Data Extractor

노션 문서에서 의미 있는 정보를 추출하는 모듈입니다.
"""

import os
from typing import Dict, Any, List, Optional, Callable

from .. import SemanticExtractor
from ..core import LLMClient, PromptTemplateFactory

class NotionExtractor(SemanticExtractor):
    """노션 데이터에서 시맨틱 정보를 추출하는 클래스"""
    
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
        templates = PromptTemplateFactory.create_notion_templates(self.llm_client)
        for semantic_type, template in templates.items():
            self.register_prompt_template(semantic_type, template)
    
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
    
    async def extract(self, raw_data: List[Dict[str, Any]], 
                     progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict[str, Any]]:
        """
        노션 문서에서 시맨틱 데이터 추출
        
        Args:
            raw_data: 노션 문서 데이터 리스트
            progress_callback: 진행 상황을 업데이트할 콜백 함수 (current, total)
            
        Returns:
            추출된 시맨틱 데이터 목록
        """
        semantic_data = []
        total_docs = len(raw_data)
        
        for doc_idx, document in enumerate(raw_data):
            # 문서 내 모든 블록 계산
            blocks = document.get("blocks", [])
            
            if progress_callback:
                progress_callback(doc_idx, total_docs)
            
            # 문서의 모든 텍스트 블록 추출
            text_blocks = self._extract_text_blocks(blocks)
            
            # 텍스트 블록을 의미 있는 섹션으로 그룹화
            sections = self._group_blocks_into_sections(text_blocks)
            
            # 각 섹션에서 의미 정보 추출
            for section_idx, section in enumerate(sections):
                # 섹션 및 문서 데이터 준비
                context_data = {
                    "section": section,
                    "document": document
                }
                
                # 인사이트 추출
                if "insights" in self.prompt_templates:
                    insights = await self.prompt_templates["insights"].process(context_data)
                    semantic_data.extend(insights)
                
                # 작업 지침 추출
                if "instructions" in self.prompt_templates:
                    instructions = await self.prompt_templates["instructions"].process(context_data)
                    semantic_data.extend(instructions)
                
                # 참조 정보 추출
                if "references" in self.prompt_templates:
                    references = await self.prompt_templates["references"].process(context_data)
                    semantic_data.extend(references)
        
        # 최종 진행 상황 업데이트
        if progress_callback:
            progress_callback(total_docs, total_docs)
            
        return semantic_data
    
    def _extract_text_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        텍스트 컨텐츠가 있는 블록만 추출
        
        Args:
            blocks: 노션 블록 목록
            
        Returns:
            텍스트 블록 목록
        """
        text_blocks = []
        
        for block in blocks:
            # 텍스트 컨텐츠가 있는 블록 추출
            if "text" in block and block["text"]:
                text_blocks.append(block)
            
            # 하위 블록 재귀적 처리
            if "children" in block and block["children"]:
                child_text_blocks = self._extract_text_blocks(block["children"])
                text_blocks.extend(child_text_blocks)
        
        return text_blocks
    
    def _group_blocks_into_sections(self, text_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        텍스트 블록을 섹션으로 그룹화
        
        Args:
            text_blocks: 텍스트 블록 목록
            
        Returns:
            섹션 목록
        """
        sections = []
        current_section = None
        
        for block in text_blocks:
            block_type = block["type"]
            
            # 제목 블록으로 새 섹션 시작
            if block_type in ["heading_1", "heading_2", "heading_3"]:
                if current_section:
                    sections.append(current_section)
                
                current_section = {
                    "title": block["text"],
                    "content": [],
                    "blocks": [block]
                }
            elif current_section is not None:
                # 현재 섹션에 콘텐츠 추가
                current_section["content"].append(block["text"])
                current_section["blocks"].append(block)
            else:
                # 섹션이 없으면 기본 섹션 생성
                current_section = {
                    "title": "Untitled Section",
                    "content": [block["text"]],
                    "blocks": [block]
                }
        
        # 마지막 섹션 추가
        if current_section:
            sections.append(current_section)
        
        return sections 