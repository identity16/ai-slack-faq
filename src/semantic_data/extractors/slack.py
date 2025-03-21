"""
Slack Semantic Data Extractor

슬랙 대화 데이터에서 의미 있는 정보를 추출하는 모듈입니다.
"""

import os
from typing import Dict, Any, List
from openai import AsyncOpenAI
import httpx
import json

from .. import SemanticExtractor, SemanticType

class SlackExtractor(SemanticExtractor):
    """슬랙 데이터에서 시맨틱 정보를 추출하는 클래스"""
    
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
        슬랙 스레드에서 시맨틱 데이터 추출
        
        Args:
            raw_data: 슬랙 스레드 데이터 리스트
            progress_callback: 진행 상황을 업데이트할 콜백 함수 (current, total)
            
        Returns:
            추출된 시맨틱 데이터 목록
        """
        semantic_data = []
        total = len(raw_data)
        
        for i, thread in enumerate(raw_data):
            # 진행 상황 업데이트
            if progress_callback:
                progress_callback(i, total)
                
            # Q&A 추출
            if "question" in thread and "answer" in thread:
                qa_data = await self._extract_qa(thread)
                if qa_data:
                    semantic_data.append(qa_data)
            
            # 인사이트 추출
            insights = await self._extract_insights(thread)
            semantic_data.extend(insights)
        
        # 최종 진행 상황 업데이트
        if progress_callback:
            progress_callback(total, total)
            
        return semantic_data
    
    async def _extract_qa(self, thread_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Q&A 형식의 시맨틱 데이터 추출
        
        Args:
            thread_data: 스레드 데이터
            
        Returns:
            Q&A 시맨틱 데이터
        """
        # GPT를 사용하여 질문과 답변의 품질 검증 및 정제
        prompt = f"""
        다음 슬랙 스레드의 질문과 답변을 분석하여 유의미한 Q&A로 정제해주세요:
        
        질문: {thread_data['question']}
        답변: {thread_data['answer']}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "is_valuable": true/false,  // 문서화할 가치가 있는지 여부
            "question": "정제된 질문",
            "answer": "정제된 답변",
            "keywords": ["키워드1", "키워드2", ...]  // 관련 키워드
        }}
        ```
        
        JSON 형식만 응답해주세요. 다른 텍스트는 포함하지 마세요.
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
            
            if not parsed_result.get("is_valuable", False):
                return None
                
            return {
                "type": SemanticType.QA,
                "question": parsed_result["question"],
                "answer": parsed_result["answer"],
                "keywords": parsed_result["keywords"],
                "source": {
                    "type": "slack_thread",
                    "channel": thread_data["channel"],
                    "timestamp": thread_data["timestamp"],
                    "questioner": thread_data["questioner"],
                    "answerer": thread_data["answerer"]
                }
            }
        except (json.JSONDecodeError, KeyError) as e:
            print(f"JSON 파싱 오류: {e}")
            return None
    
    async def _extract_insights(self, thread_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        스레드에서 인사이트 추출
        
        Args:
            thread_data: 스레드 데이터
            
        Returns:
            추출된 인사이트 목록
        """
        prompt = f"""
        다음 슬랙 스레드에서 유의미한 인사이트를 추출해주세요:
        
        내용:
        {thread_data.get('question', '')}
        {thread_data.get('answer', '')}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "insights": [
                {{
                    "type": "insight", // "insight", "feedback", "reference" 중 하나
                    "content": "인사이트 내용",
                    "keywords": ["키워드1", "키워드2", ...],
                    "reference_type": "링크" // type이 "reference"인 경우에만 필요
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
                elif insight_type == "reference":
                    semantic_type = SemanticType.REFERENCE
                else:
                    # 기본값은 인사이트로 설정
                    semantic_type = SemanticType.INSIGHT
                
                insight = {
                    "type": semantic_type,
                    "content": insight_data.get("content", ""),
                    "keywords": insight_data.get("keywords", []),
                    "source": {
                        "type": "slack_thread",
                        "channel": thread_data.get("channel", ""),
                        "timestamp": thread_data.get("timestamp", "")
                    }
                }
                
                # 참조 타입인 경우 reference_type 추가
                if semantic_type == SemanticType.REFERENCE and "reference_type" in insight_data:
                    insight["reference_type"] = insight_data["reference_type"]
                
                insights.append(insight)
            
            return insights
        except (json.JSONDecodeError, KeyError) as e:
            print(f"JSON 파싱 오류: {e}")
            return [] 