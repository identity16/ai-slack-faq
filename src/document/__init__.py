"""
Document Generation Module

시맨틱 데이터를 기반으로 문서를 생성하는 모듈입니다.
"""

from typing import Dict, Any, List
from abc import ABC, abstractmethod

class DocumentType:
    """문서 유형"""
    FAQ = "faq"                      # 자주 묻는 질문
    GUIDE = "guide"                  # 사용자 가이드
    RELEASE_NOTE = "release_note"    # 릴리스 노트
    GLOSSARY = "glossary"           # 용어집

class DocumentGenerator(ABC):
    """문서 생성기 인터페이스"""
    
    @abstractmethod
    async def generate(self, semantic_data: List[Dict[str, Any]], doc_type: str) -> str:
        """
        시맨틱 데이터를 기반으로 문서 생성
        
        Args:
            semantic_data: 시맨틱 데이터 목록
            doc_type: 문서 유형
            
        Returns:
            생성된 문서 내용
        """
        pass
    
    @abstractmethod
    async def save(self, content: str, output_path: str) -> None:
        """
        생성된 문서 저장
        
        Args:
            content: 문서 내용
            output_path: 저장 경로
        """
        pass

from .generators.markdown import MarkdownGenerator

__all__ = [
    'DocumentType',
    'DocumentGenerator',
    'MarkdownGenerator'
] 