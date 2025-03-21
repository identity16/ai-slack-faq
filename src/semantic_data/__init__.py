"""
Semantic Data Extraction Module

원본 데이터에서 의미 있는 정보를 추출하고 구조화하는 모듈입니다.
"""

from typing import Dict, Any, List
from abc import ABC, abstractmethod

class SemanticType:
    """시맨틱 데이터 유형"""
    QA = "qa"                    # 질문-답변
    INSIGHT = "insight"          # 인사이트
    FEEDBACK = "feedback"        # 피드백
    REFERENCE = "reference"      # 참조 정보
    INSTRUCTION = "instruction"  # 작업 지침

class SemanticExtractor(ABC):
    """시맨틱 데이터 추출기 인터페이스"""
    
    @abstractmethod
    async def extract(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        원본 데이터에서 시맨틱 데이터 추출
        
        Args:
            raw_data: 원본 데이터
            
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

__all__ = [
    'SemanticType',
    'SemanticExtractor',
    'SemanticStore',
    'SlackExtractor',
    'NotionExtractor',
    'SQLiteStore'
] 