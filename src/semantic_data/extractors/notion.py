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
        total_sections = sum(len(doc.get("sections", [])) for doc in raw_data)
        processed_sections = 0
        
        for doc_idx, document in enumerate(raw_data):
            # 섹션별 처리
            sections = document.get("sections", [])
            
            for section_idx, section in enumerate(sections):
                # 진행 상황 업데이트
                if progress_callback:
                    processed_sections += 1
                    progress_callback(processed_sections, total_sections)
                
                # 인사이트 추출
                insights = await self._extract_insights(section)
                semantic_data.extend(insights)
                
                # 작업 지침 추출
                instructions = await self._extract_instructions(section)
                semantic_data.extend(instructions)
                
                # 참조 정보 추출
                references = await self._extract_references(section)
                semantic_data.extend(references)
        
        # 최종 진행 상황 업데이트
        if progress_callback:
            progress_callback(total_sections, total_sections)
            
        return semantic_data
    
    async def _extract_insights(self, section: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        섹션에서 인사이트 추출
        
        Args:
            section: 문서 섹션 데이터
            
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
                        "type": "notion_section",
                        "title": section["title"]
                    }
                }
                
                insights.append(insight)
            
            return insights
        except (json.JSONDecodeError, KeyError) as e:
            print(f"JSON 파싱 오류: {e}")
            return []
    
    async def _extract_instructions(self, section: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        섹션에서 작업 지침 추출
        
        Args:
            section: 문서 섹션 데이터
            
        Returns:
            추출된 작업 지침 목록
        """
        prompt = f"""
        다음 노션 문서 섹션에서 작업 지침이나 가이드라인을 추출해주세요:
        
        제목: {section['title']}
        내용:
        {' '.join(section['content'])}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "instructions": [
                {{
                    "content": "지침 내용",
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
            
            instructions = []
            for instruction_data in parsed_result.get("instructions", []):
                instruction = {
                    "type": SemanticType.INSTRUCTION,
                    "content": instruction_data.get("content", ""),
                    "keywords": instruction_data.get("keywords", []),
                    "source": {
                        "type": "notion_section",
                        "title": section["title"]
                    }
                }
                
                instructions.append(instruction)
            
            return instructions
        except (json.JSONDecodeError, KeyError) as e:
            print(f"JSON 파싱 오류: {e}")
            return []
    
    async def _extract_references(self, section: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        섹션에서 참조 정보 추출
        
        Args:
            section: 문서 섹션 데이터
            
        Returns:
            추출된 참조 정보 목록
        """
        prompt = f"""
        다음 노션 문서 섹션에서 참조할만한 정보(링크, 문서, 도구 등)를 추출해주세요:
        
        제목: {section['title']}
        내용:
        {' '.join(section['content'])}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "references": [
                {{
                    "content": "참조 내용",
                    "reference_type": "링크", // 참조 유형(링크, 문서, 도구 등)
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
            
            references = []
            for reference_data in parsed_result.get("references", []):
                reference = {
                    "type": SemanticType.REFERENCE,
                    "content": reference_data.get("content", ""),
                    "reference_type": reference_data.get("reference_type", ""),
                    "keywords": reference_data.get("keywords", []),
                    "source": {
                        "type": "notion_section",
                        "title": section["title"]
                    }
                }
                
                references.append(reference)
            
            return references
        except (json.JSONDecodeError, KeyError) as e:
            print(f"JSON 파싱 오류: {e}")
            return [] 