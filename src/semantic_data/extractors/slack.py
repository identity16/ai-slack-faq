"""
Slack Semantic Data Extractor

슬랙 대화 데이터에서 의미 있는 정보를 추출하는 모듈입니다.
"""

import os
from typing import Dict, Any, List, Optional, Callable

from .. import SemanticExtractor
from ..core import LLMClient, PromptTemplateFactory

class SlackExtractor(SemanticExtractor):
    """슬랙 데이터에서 시맨틱 정보를 추출하는 클래스"""
    
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
        templates = PromptTemplateFactory.create_slack_templates(self.llm_client)
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
        슬랙 스레드에서 시맨틱 데이터 추출
        
        Args:
            raw_data: 슬랙 스레드 데이터 리스트
            progress_callback: 진행 상황을 업데이트할 콜백 함수 (current, total)
            
        Returns:
            추출된 시맨틱 데이터 목록
        """
        semantic_data = []
        total = len(raw_data)
        
        for i, thread in enumerate(raw_data):
            # 진행 상황 업데이트
            if progress_callback:
                progress_callback(i, total)
                
            # 스레드에 메시지가 있는지 확인
            if "messages" in thread and len(thread["messages"]) >= 2:
                # QnA 프롬프트 템플릿 처리
                if "qna" in self.prompt_templates:
                    qa_results = await self.prompt_templates["qna"].process(thread)
                    semantic_data.extend(qa_results)
                
                # 인사이트 프롬프트 템플릿 처리
                if "insights" in self.prompt_templates:
                    insights_results = await self.prompt_templates["insights"].process(thread)
                    semantic_data.extend(insights_results)
                
                # 용어집 프롬프트 템플릿 처리
                if "glossary" in self.prompt_templates:
                    glossary_results = await self.prompt_templates["glossary"].process(thread)
                    semantic_data.extend(glossary_results)
        
        # 최종 진행 상황 업데이트
        if progress_callback:
            progress_callback(total, total)
            
        return semantic_data 