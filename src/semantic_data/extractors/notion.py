"""
Notion Semantic Data Extractor

노션 문서에서 의미 있는 정보를 추출하는 모듈입니다.
"""

import os
from typing import Dict, Any, List
from openai import AsyncOpenAI
import httpx
import json

from .. import SemanticExtractor, SemanticType

class NotionExtractor(SemanticExtractor):
    """노션 데이터에서 시맨틱 정보를 추출하는 클래스"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        초기화
        
        Args:
            config: OpenAI API 키 등 설정 정보
        """
        api_key = config.get("openai_api_key") if config else os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다.")
        self.client = AsyncOpenAI(api_key=api_key)
        self._session = None
    
    async def __aenter__(self):
        """비동기 컨텍스트 관리자 진입"""
        self._session = httpx.AsyncClient()
        self.client = AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            http_client=self._session
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 관리자 종료"""
        if self._session:
            await self._session.aclose()
    
    async def close(self):
        """리소스 정리"""
        if self._session:
            await self._session.aclose()
            self._session = None
    
    async def extract(self, raw_data: List[Dict[str, Any]], progress_callback=None) -> List[Dict[str, Any]]:
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
                # 인사이트 추출
                insights = await self._extract_insights_from_section(section, document)
                semantic_data.extend(insights)
                
                # 작업 지침 추출
                instructions = await self._extract_instructions_from_section(section, document)
                semantic_data.extend(instructions)
                
                # 참조 정보 추출
                references = await self._extract_references_from_section(section, document)
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
    
    async def _extract_insights_from_section(self, section: Dict[str, Any], document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        섹션에서 인사이트 추출
        
        Args:
            section: 문서 섹션 데이터
            document: 원본 문서 데이터
            
        Returns:
            추출된 인사이트 목록
        """
        prompt = f"""
        다음 노션 문서 섹션에서 유의미한 인사이트를 추출해주세요:
        
        제목: {section['title']}
        내용:
        {' '.join(section['content'])}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "insights": [
                {{
                    "type": "insight", // "insight" 또는 "feedback" 중 하나
                    "content": "인사이트 내용",
                    "keywords": ["키워드1", "키워드2", ...]
                }},
                // 더 많은 인사이트...
            ]
        }}
        ```
        
        인사이트가 없다면 빈 배열을 반환하세요. JSON 형식만 응답해주세요.
        """
        
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        try:
            result = response.choices[0].message.content
            parsed_result = json.loads(result)
            
            insights = []
            for insight_data in parsed_result.get("insights", []):
                insight_type = insight_data.get("type", "").lower()
                
                if insight_type == "insight":
                    semantic_type = SemanticType.INSIGHT
                elif insight_type == "feedback":
                    semantic_type = SemanticType.FEEDBACK
                else:
                    # 기본값은 인사이트로 설정
                    semantic_type = SemanticType.INSIGHT
                
                insight = {
                    "type": semantic_type,
                    "content": insight_data.get("content", ""),
                    "keywords": insight_data.get("keywords", []),
                    "source": {
                        "type": "notion_document",
                        "document_id": document.get("id", ""),
                        "document_title": document.get("title", ""),
                        "section_title": section.get("title", "")
                    }
                }
                
                insights.append(insight)
            
            return insights
        except (json.JSONDecodeError, KeyError) as e:
            print(f"JSON 파싱 오류: {e}")
            return []
    
    async def _extract_instructions_from_section(self, section: Dict[str, Any], document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        섹션에서 작업 지침 추출
        
        Args:
            section: 문서 섹션 데이터
            document: 원본 문서 데이터
            
        Returns:
            추출된 작업 지침 목록
        """
        # 제목이 작업 지침과 관련된 내용인지 확인
        title_lower = section["title"].lower()
        if not any(keyword in title_lower for keyword in ["how to", "guide", "tutorial", "instruction", "방법", "가이드", "튜토리얼", "지침"]):
            return []
        
        prompt = f"""
        다음 노션 문서 섹션에서 작업 지침이나 가이드를 추출해주세요:
        
        제목: {section['title']}
        내용:
        {' '.join(section['content'])}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "instructions": [
                {{
                    "title": "지침 제목",
                    "steps": ["1단계", "2단계", "3단계"],
                    "keywords": ["키워드1", "키워드2", ...]
                }},
                // 더 많은 지침...
            ]
        }}
        ```
        
        작업 지침이 없다면 빈 배열을 반환하세요. JSON 형식만 응답해주세요.
        """
        
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        try:
            result = response.choices[0].message.content
            parsed_result = json.loads(result)
            
            instructions_list = []
            for instruction_data in parsed_result.get("instructions", []):
                instruction = {
                    "type": SemanticType.INSTRUCTION,
                    "title": instruction_data.get("title", ""),
                    "steps": instruction_data.get("steps", []),
                    "keywords": instruction_data.get("keywords", []),
                    "source": {
                        "type": "notion_document",
                        "document_id": document.get("id", ""),
                        "document_title": document.get("title", ""),
                        "section_title": section.get("title", "")
                    }
                }
                
                instructions_list.append(instruction)
            
            return instructions_list
        except (json.JSONDecodeError, KeyError) as e:
            print(f"JSON 파싱 오류: {e}")
            return []
    
    async def _extract_references_from_section(self, section: Dict[str, Any], document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        섹션에서 참조 정보 추출
        
        Args:
            section: 문서 섹션 데이터
            document: 원본 문서 데이터
            
        Returns:
            추출된 참조 정보 목록
        """
        # 내용을 문자열로 결합
        content_text = ' '.join(section["content"])
        
        # URL, 책, 논문 등 참조 정보가 있는지 확인
        has_url = "http://" in content_text or "https://" in content_text
        has_reference_keywords = any(keyword in content_text.lower() for keyword in 
                                     ["참조", "참고", "reference", "refer to", "link", "url", "source", "citation"])
        
        if not (has_url or has_reference_keywords):
            return []
        
        prompt = f"""
        다음 노션 문서 섹션에서 참조 정보(URL, 책, 논문 등)를 추출해주세요:
        
        제목: {section['title']}
        내용:
        {content_text}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "references": [
                {{
                    "reference_type": "url/book/paper/etc",
                    "title": "참조 제목",
                    "url": "URL (있는 경우)",
                    "description": "참조 설명",
                    "keywords": ["키워드1", "키워드2", ...]
                }},
                // 더 많은 참조...
            ]
        }}
        ```
        
        참조 정보가 없다면 빈 배열을 반환하세요. JSON 형식만 응답해주세요.
        """
        
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        try:
            result = response.choices[0].message.content
            parsed_result = json.loads(result)
            
            references_list = []
            for reference_data in parsed_result.get("references", []):
                reference = {
                    "type": SemanticType.REFERENCE,
                    "reference_type": reference_data.get("reference_type", ""),
                    "title": reference_data.get("title", ""),
                    "url": reference_data.get("url", ""),
                    "description": reference_data.get("description", ""),
                    "keywords": reference_data.get("keywords", []),
                    "source": {
                        "type": "notion_document",
                        "document_id": document.get("id", ""),
                        "document_title": document.get("title", ""),
                        "section_title": section.get("title", "")
                    }
                }
                
                references_list.append(reference)
            
            return references_list
        except (json.JSONDecodeError, KeyError) as e:
            print(f"JSON 파싱 오류: {e}")
            return [] 