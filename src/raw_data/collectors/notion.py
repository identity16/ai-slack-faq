"""
Notion Raw Data Collector

노션 문서에서 데이터를 수집하는 모듈입니다.
"""

import os
import re
from typing import Dict, Any, List
from notion_client import Client

class NotionCollector:
    """
    노션 API를 통해 문서 데이터를 수집하는 Collector 클래스
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        노션 API 클라이언트 초기화
        
        Args:
            config: 설정 정보 (옵션)
        """
        notion_token = config.get("notion_token") if config else os.environ.get("NOTION_API_KEY")
        if not notion_token:
            raise ValueError("Notion 토큰이 설정되지 않았습니다.")
        self.client = Client(auth=notion_token)
    
    def _extract_doc_id(self, url_or_id: str) -> str:
        """
        노션 URL에서 문서 ID 추출
        
        Args:
            url_or_id: 노션 문서 URL 또는 ID
            
        Returns:
            노션 문서 ID
        """
        if "notion.so" in url_or_id:
            # URL에서 ID 추출 (UUID 형식)
            match = re.search(r"([a-f0-9]{32})", url_or_id)
            if match:
                return match.group(1)
                
            # 또는 다른 형식의 ID 추출
            match = re.search(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", url_or_id)
            if match:
                return match.group(1)
                
        return url_or_id
    
    async def collect(self, doc_id: str) -> Dict[str, Any]:
        """
        노션 문서에서 데이터 수집
        
        Args:
            doc_id: 노션 문서 ID 또는 URL
            
        Returns:
            수집된 문서 데이터
        """
        doc_id = self._extract_doc_id(doc_id)
        
        try:
            # 문서 메타데이터 가져오기
            page = self.client.pages.retrieve(doc_id)
            
            # 문서 내용 가져오기
            blocks = self.client.blocks.children.list(doc_id)
            
            # 문서 데이터 구조화
            document = {
                "id": doc_id,
                "type": "notion_document",
                "title": self._get_page_title(page),
                "created_time": page["created_time"],
                "last_edited_time": page["last_edited_time"],
                "sections": self._process_blocks(blocks["results"]),
                "raw_content": blocks
            }
            
            return document
            
        except Exception as e:
            print(f"노션 문서 가져오기 실패: {e}")
            return {}
    
    def _get_page_title(self, page: Dict[str, Any]) -> str:
        """
        페이지 제목 추출
        
        Args:
            page: 페이지 메타데이터
            
        Returns:
            페이지 제목
        """
        if "properties" in page and "title" in page["properties"]:
            title_property = page["properties"]["title"]
            if "title" in title_property and len(title_property["title"]) > 0:
                return title_property["title"][0]["plain_text"]
        return "Untitled"
    
    def _process_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        블록 데이터 처리
        
        Args:
            blocks: 블록 목록
            
        Returns:
            처리된 섹션 목록
        """
        sections = []
        current_section = None
        
        for block in blocks:
            block_type = block["type"]
            
            if block_type == "heading_1" or block_type == "heading_2":
                if current_section:
                    sections.append(current_section)
                current_section = {
                    "title": block[block_type]["rich_text"][0]["plain_text"] if block[block_type]["rich_text"] else "",
                    "content": []
                }
            elif current_section is not None and block_type == "paragraph":
                text = "".join([rt["plain_text"] for rt in block["paragraph"]["rich_text"]])
                if text.strip():
                    current_section["content"].append(text)
        
        if current_section:
            sections.append(current_section)
            
        return sections 