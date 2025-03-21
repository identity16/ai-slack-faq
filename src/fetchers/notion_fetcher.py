import os
from typing import Dict, Any, Optional
import requests
from datetime import datetime

class NotionFetcher:
    """노션 API를 통해 문서 데이터를 가져오는 클래스"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        NotionFetcher 초기화
        
        Args:
            api_key: 노션 통합 API 키 (없으면 환경 변수에서 가져옴)
        """
        self.api_key = api_key or os.getenv("NOTION_API_KEY")
        if not self.api_key:
            raise ValueError("NOTION_API_KEY not found in environment variables")
            
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
    
    def get_page_content(self, page_id: str) -> Dict[str, Any]:
        """
        노션 페이지 내용 가져오기
        
        Args:
            page_id: 노션 페이지 ID
            
        Returns:
            페이지 콘텐츠 데이터
        """
        page_id = self._clean_page_id(page_id)
        url = f"{self.base_url}/pages/{page_id}"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        return response.json()
    
    def get_block_children(self, block_id: str) -> Dict[str, Any]:
        """
        블록의 하위 블록 가져오기
        
        Args:
            block_id: 노션 블록 ID
            
        Returns:
            하위 블록 데이터
        """
        block_id = self._clean_page_id(block_id)
        url = f"{self.base_url}/blocks/{block_id}/children"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        return response.json()
    
    def get_database_item(self, database_id: str, item_id: str) -> Dict[str, Any]:
        """
        데이터베이스 항목 가져오기
        
        Args:
            database_id: 노션 데이터베이스 ID
            item_id: 항목 ID
            
        Returns:
            데이터베이스 항목 데이터
        """
        database_id = self._clean_page_id(database_id)
        item_id = self._clean_page_id(item_id)
        
        url = f"{self.base_url}/pages/{item_id}"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        return response.json()
    
    def query_database(self, database_id: str, filter_params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        데이터베이스 쿼리하기
        
        Args:
            database_id: 노션 데이터베이스 ID
            filter_params: 필터 파라미터
            
        Returns:
            쿼리 결과 데이터
        """
        database_id = self._clean_page_id(database_id)
        url = f"{self.base_url}/databases/{database_id}/query"
        
        payload = {}
        if filter_params:
            payload.update(filter_params)
        
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        
        return response.json()
    
    def _clean_page_id(self, page_id: str) -> str:
        """노션 페이지 ID 정리 (URL에서 ID 추출)"""
        if page_id.startswith("https://"):
            # URL에서 ID 추출
            if "notion.so/" in page_id:
                page_id = page_id.split("notion.so/")[1]
                
                # 워크스페이스 이름 제거
                if "-" in page_id:
                    page_id = page_id.split("-")[-1]
                
                # 마지막 32자리가 ID
                if len(page_id) > 32:
                    page_id = page_id[-32:]
        
        # 대시 제거
        page_id = page_id.replace("-", "")
        
        return page_id
    
    def _extract_plain_text(self, rich_text_list: list) -> str:
        """리치 텍스트 목록에서 일반 텍스트 추출"""
        if not rich_text_list:
            return ""
        
        return "".join([text.get("plain_text", "") for text in rich_text_list])
    
    def _process_blocks_to_text(self, blocks: list) -> str:
        """블록 목록에서 텍스트 추출 및 포맷팅"""
        text = ""
        
        for block in blocks:
            block_type = block.get("type")
            
            if block_type == "paragraph":
                paragraph_text = self._extract_plain_text(block.get("paragraph", {}).get("rich_text", []))
                if paragraph_text:
                    text += paragraph_text + "\n\n"
            
            elif block_type == "heading_1":
                heading_text = self._extract_plain_text(block.get("heading_1", {}).get("rich_text", []))
                if heading_text:
                    text += f"# {heading_text}\n\n"
            
            elif block_type == "heading_2":
                heading_text = self._extract_plain_text(block.get("heading_2", {}).get("rich_text", []))
                if heading_text:
                    text += f"## {heading_text}\n\n"
            
            elif block_type == "heading_3":
                heading_text = self._extract_plain_text(block.get("heading_3", {}).get("rich_text", []))
                if heading_text:
                    text += f"### {heading_text}\n\n"
            
            elif block_type == "bulleted_list_item":
                item_text = self._extract_plain_text(block.get("bulleted_list_item", {}).get("rich_text", []))
                if item_text:
                    text += f"- {item_text}\n"
            
            elif block_type == "numbered_list_item":
                item_text = self._extract_plain_text(block.get("numbered_list_item", {}).get("rich_text", []))
                if item_text:
                    text += f"1. {item_text}\n"
            
            elif block_type == "to_do":
                todo_text = self._extract_plain_text(block.get("to_do", {}).get("rich_text", []))
                checked = block.get("to_do", {}).get("checked", False)
                if todo_text:
                    marker = "x" if checked else " "
                    text += f"- [{marker}] {todo_text}\n"
            
            elif block_type == "quote":
                quote_text = self._extract_plain_text(block.get("quote", {}).get("rich_text", []))
                if quote_text:
                    text += f"> {quote_text}\n\n"
            
            elif block_type == "code":
                code_text = self._extract_plain_text(block.get("code", {}).get("rich_text", []))
                language = block.get("code", {}).get("language", "")
                if code_text:
                    text += f"```{language}\n{code_text}\n```\n\n"
            
            elif block_type == "divider":
                text += "---\n\n"
            
            # 하위 블록이 있는 경우 재귀적으로 처리
            if block.get("has_children", False):
                children_response = self.get_block_children(block.get("id"))
                children_blocks = children_response.get("results", [])
                children_text = self._process_blocks_to_text(children_blocks)
                text += children_text
        
        return text
    
    def get_ut_transcript(self, doc_id: str) -> str:
        """
        노션 문서에서 UT 회의 녹취록 텍스트 가져오기
        
        Args:
            doc_id: 노션 문서 ID
            
        Returns:
            UT 회의 녹취록 텍스트
        """
        try:
            # 페이지 내용 가져오기
            page_data = self.get_page_content(doc_id)
            
            # 페이지 제목 추출
            title = ""
            if page_data.get("properties"):
                for prop_name, prop_data in page_data.get("properties", {}).items():
                    if prop_data.get("type") == "title":
                        title = self._extract_plain_text(prop_data.get("title", []))
                        break
            
            # 페이지 블록 가져오기
            blocks_data = self.get_block_children(doc_id)
            blocks = blocks_data.get("results", [])
            
            # 텍스트 생성
            content = self._process_blocks_to_text(blocks)
            
            if title:
                return f"# {title}\n\n{content}"
            else:
                return content
                
        except Exception as e:
            print(f"노션 문서 가져오기 오류: {str(e)}")
            return ""