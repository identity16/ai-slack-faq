"""
Semantic Data Extraction Module

원본 데이터에서 의미 있는 정보를 추출하고 구조화하는 모듈입니다.
"""

from typing import Dict, Any, List, Protocol, Callable, Optional, Union
from abc import ABC, abstractmethod

class SemanticType:
    """시맨틱 데이터 유형"""
    QnA = "qna"                    # 질문-답변
    INSIGHT = "insight"          # 인사이트
    FEEDBACK = "feedback"        # 피드백
    REFERENCE = "reference"      # 참조 정보
    INSTRUCTION = "instruction"  # 작업 지침
    GLOSSARY = "glossary"        # 용어집

class SemanticPromptTemplate(Protocol):
    """시맨틱 데이터 추출 프롬프트 템플릿 프로토콜"""
    
    async def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        데이터를 처리하여 시맨틱 데이터 추출
        
        Args:
            data: 처리할 원본 데이터
            
        Returns:
            추출된 시맨틱 데이터 목록
        """
        ...

class SemanticExtractor(ABC):
    """시맨틱 데이터 추출기 인터페이스"""
    
    def __init__(self, prompt_templates: Dict[str, SemanticPromptTemplate] = None):
        """
        초기화
        
        Args:
            prompt_templates: 시맨틱 타입별 프롬프트 템플릿
        """
        self.prompt_templates = prompt_templates or {}
    
    def register_prompt_template(self, semantic_type: str, template: SemanticPromptTemplate) -> None:
        """
        특정 시맨틱 타입에 대한 프롬프트 템플릿 등록
        
        Args:
            semantic_type: 시맨틱 데이터 유형
            template: 프롬프트 템플릿
        """
        self.prompt_templates[semantic_type] = template
    
    @abstractmethod
    async def extract(self, raw_data: Union[Dict[str, Any], List[Dict[str, Any]]], 
                     progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict[str, Any]]:
        """
        원본 데이터에서 시맨틱 데이터 추출
        
        Args:
            raw_data: 원본 데이터
            progress_callback: 진행 상황 콜백 함수
            
        Returns:
            추출된 시맨틱 데이터 목록
        """
        pass

class SemanticStore(ABC):
    """시맨틱 데이터 저장소 인터페이스"""
    
    @abstractmethod
    async def store(self, semantic_data: List[Dict[str, Any]]) -> None:
        """
        시맨틱 데이터 저장
        
        Args:
            semantic_data: 저장할 시맨틱 데이터 목록
        """
        pass
    
    @abstractmethod
    async def retrieve(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        시맨틱 데이터 검색
        
        Args:
            query: 검색 조건
            
        Returns:
            검색된 시맨틱 데이터 목록
        """
        pass

from .extractors.slack import SlackExtractor
from .extractors.notion import NotionExtractor
from .store.sqlite import SQLiteStore
from .core import (
    LLMClient, 
    PromptTemplateFactory, 
    GlossaryEnhancementPromptTemplate, 
    enhance_low_confidence_terms
)

__all__ = [
    'SemanticType',
    'SemanticPromptTemplate',
    'SemanticExtractor',
    'SemanticStore',
    'SlackExtractor',
    'NotionExtractor',
    'SQLiteStore',
    'LLMClient',
    'PromptTemplateFactory',
    'GlossaryEnhancementPromptTemplate',
    'enhance_low_confidence_terms'
] 