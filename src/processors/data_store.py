"""
데이터 저장소 모듈 - 정제된 데이터의 저장 및 관리
"""
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

class DataStore:
    """
    정제된 데이터를 저장하고 관리하는 클래스
    """
    
    def __init__(self, base_dir: str = "data"):
        """
        데이터 저장소 초기화
        
        Args:
            base_dir: 데이터 저장 기본 디렉토리
        """
        self.base_dir = Path(base_dir)
        self.slack_data_dir = self.base_dir / "slack"
        self.notion_data_dir = self.base_dir / "notion"
        
        # 디렉토리 생성
        os.makedirs(self.slack_data_dir, exist_ok=True)
        os.makedirs(self.notion_data_dir, exist_ok=True)
    
    def save_processed_slack_data(self, channel: str, data: List[Dict[str, Any]]) -> str:
        """
        처리된 슬랙 데이터 저장
        
        Args:
            channel: 슬랙 채널 이름
            data: 처리된 데이터
            
        Returns:
            저장된 파일 경로
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"slack_{channel}_{timestamp}.json"
        file_path = self.slack_data_dir / filename
        
        # 메타데이터 추가
        metadata = {
            "source": "slack",
            "channel": channel,
            "created_at": datetime.now().isoformat(),
            "count": len(data)
        }
        
        content = {
            "metadata": metadata,
            "data": data
        }
        
        # 파일 저장
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        
        return str(file_path)
    
    def save_processed_notion_data(self, doc_id: str, data: Dict[str, Any]) -> str:
        """
        처리된 노션 데이터 저장
        
        Args:
            doc_id: 노션 문서 ID
            data: 처리된 데이터
            
        Returns:
            저장된 파일 경로
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"notion_{timestamp}.json"
        file_path = self.notion_data_dir / filename
        
        # 메타데이터 추가
        metadata = {
            "source": "notion",
            "doc_id": doc_id,
            "created_at": datetime.now().isoformat()
        }
        
        content = {
            "metadata": metadata,
            "data": data
        }
        
        # 파일 저장
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        
        return str(file_path)
    
    def get_slack_data(self, channel: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        저장된 슬랙 데이터 가져오기
        
        Args:
            channel: 특정 채널 필터링 (None이면 모든 채널)
            
        Returns:
            저장된 데이터 목록
        """
        all_data = []
        
        for file_path in self.slack_data_dir.glob("slack_*.json"):
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                
                # 채널 필터링
                if channel is None or content["metadata"]["channel"] == channel:
                    all_data.append(content)
        
        return all_data
    
    def get_notion_data(self) -> List[Dict[str, Any]]:
        """
        저장된 노션 데이터 가져오기
        
        Returns:
            저장된 데이터 목록
        """
        all_data = []
        
        for file_path in self.notion_data_dir.glob("notion_*.json"):
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                all_data.append(content)
        
        return all_data 