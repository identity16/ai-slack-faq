"""
Notion Raw Data Collector

노션 문서에서 데이터를 수집하는 모듈입니다.
"""

import os
import re
from typing import Dict, Any, List
from notion_client import Client
from datetime import datetime

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
                "blocks": self._process_blocks(blocks["results"]),
                "parent": {
                    "type": page.get("parent", {}).get("type", ""),
                    "id": page.get("parent", {}).get(page.get("parent", {}).get("type", ""), "")
                },
                "url": page.get("url", ""),
                "properties": page.get("properties", {}),
                "metadata": {
                    "collection_timestamp": datetime.now().isoformat()
                }
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
            처리된 블록 목록
        """
        processed_blocks = []
        
        for block in blocks:
            block_type = block["type"]
            block_id = block["id"]
            
            processed_block = {
                "id": block_id,
                "type": block_type,
                "created_time": block.get("created_time", ""),
                "last_edited_time": block.get("last_edited_time", "")
            }
            
            # 블록 타입별 컨텐츠 추출
            if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]:
                rich_text = block[block_type].get("rich_text", [])
                processed_block["text"] = "".join([rt["plain_text"] for rt in rich_text]) if rich_text else ""
                processed_block["annotations"] = [rt.get("annotations", {}) for rt in rich_text] if rich_text else []
            elif block_type == "image":
                processed_block["url"] = block["image"].get("file", {}).get("url", "") or block["image"].get("external", {}).get("url", "")
                caption = block["image"].get("caption", [])
                processed_block["caption"] = "".join([rt["plain_text"] for rt in caption]) if caption else ""
            elif block_type == "code":
                rich_text = block["code"].get("rich_text", [])
                processed_block["text"] = "".join([rt["plain_text"] for rt in rich_text]) if rich_text else ""
                processed_block["language"] = block["code"].get("language", "")
            elif block_type == "table":
                processed_block["table_width"] = block["table"].get("table_width", 0)
                processed_block["has_column_header"] = block["table"].get("has_column_header", False)
                processed_block["has_row_header"] = block["table"].get("has_row_header", False)
                
                # 테이블 행 가져오기 (별도 API 호출 필요)
                try:
                    table_rows = self.client.blocks.children.list(block_id)
                    processed_block["rows"] = self._process_table_rows(table_rows.get("results", []))
                except Exception as e:
                    print(f"테이블 행 가져오기 실패: {e}")
                    processed_block["rows"] = []
            
            # 하위 블록 처리 (재귀적으로 수행)
            if block.get("has_children", False) and block_type != "table":
                try:
                    children = self.client.blocks.children.list(block_id)
                    processed_block["children"] = self._process_blocks(children.get("results", []))
                except Exception as e:
                    print(f"하위 블록 가져오기 실패: {e}")
                    processed_block["children"] = []
            
            processed_blocks.append(processed_block)
            
        return processed_blocks
    
    def _process_table_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        테이블 행 데이터 처리
        
        Args:
            rows: 테이블 행 블록 목록
            
        Returns:
            처리된 테이블 행 목록
        """
        processed_rows = []
        
        for row in rows:
            if row["type"] != "table_row":
                continue
                
            cells = row["table_row"]["cells"]
            processed_cells = []
            
            for cell in cells:
                cell_text = "".join([rt["plain_text"] for rt in cell]) if cell else ""
                processed_cells.append(cell_text)
                
            processed_rows.append(processed_cells)
            
        return processed_rows 