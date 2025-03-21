"""
Raw Data Collection Module

외부 데이터 소스에서 원본 데이터를 수집하는 모듈입니다.
"""

from typing import Dict, Any
from abc import ABC, abstractmethod

class RawDataCollector(ABC):
    """Raw Data Collector 인터페이스"""
    
    @abstractmethod
    async def collect(self, *args, **kwargs) -> Dict[str, Any]:
        """데이터 수집 메서드"""
        pass

from .collectors.slack import SlackCollector
from .collectors.notion import NotionCollector

__all__ = ['RawDataCollector', 'SlackCollector', 'NotionCollector'] 