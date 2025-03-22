"""
Semantic Data Core Components

시맨틱 데이터 추출 및 처리를 위한 핵심 컴포넌트
"""

import os
import json
from typing import Dict, Any, List, Optional, Union, Type
from openai import AsyncOpenAI
import httpx

from . import SemanticType, SemanticPromptTemplate


class LLMClient:
    """LLM API 클라이언트"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        초기화
        
        Args:
            api_key: OpenAI API 키
            model: 사용할 모델 이름
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다.")
        self.model = model
        self.client = AsyncOpenAI(api_key=self.api_key)
        self._session = None
    
    async def __aenter__(self):
        """비동기 컨텍스트 관리자 진입"""
        self._session = httpx.AsyncClient()
        self.client = AsyncOpenAI(
            api_key=self.api_key,
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
    
    async def generate(self, prompt: str, temperature: float = 0.3, as_json: bool = True) -> Union[str, Dict[str, Any]]:
        """
        LLM을 사용하여 텍스트 생성
        
        Args:
            prompt: 프롬프트 텍스트
            temperature: 생성 온도 (낮을수록 결정적)
            as_json: JSON 응답 반환 여부
            
        Returns:
            생성된 텍스트 또는 파싱된 JSON
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            response_format={"type": "json_object"} if as_json else None
        )
        
        result = response.choices[0].message.content
        
        if as_json:
            try:
                return json.loads(result)
            except json.JSONDecodeError as e:
                print(f"JSON 파싱 오류: {e}")
                return {}
        return result


class SlackQnAPromptTemplate(SemanticPromptTemplate):
    """슬랙 QnA 데이터 추출 프롬프트 템플릿"""
    
    def __init__(self, llm_client: LLMClient):
        """
        초기화
        
        Args:
            llm_client: LLM 클라이언트
        """
        self.llm_client = llm_client
    
    async def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        슬랙 스레드에서 QA 데이터 처리
        
        Args:
            data: 스레드 데이터
            
        Returns:
            추출된 QA 데이터
        """
        # 메시지 목록에서 첫 번째 메시지와 두 번째 메시지 추출
        messages = data.get("messages", [])
        if len(messages) < 2:
            return []
        
        question_message = messages[0]
        answer_message = messages[1]
        
        prompt = f"""
        다음 슬랙 스레드의 질문과 답변을 분석하여 유의미한 Q&A로 정제해주세요:
        
        질문: {question_message.get('text', '')}
        답변: {answer_message.get('text', '')}
        
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
        
        result = await self.llm_client.generate(prompt)
        
        if not result.get("is_valuable", False):
            return []
            
        return [{
            "type": SemanticType.QnA,
            "question": result["question"],
            "answer": result["answer"],
            "keywords": result["keywords"],
            "source": {
                "type": "slack_thread",
                "channel": data.get("channel", ""),
                "thread_ts": data.get("thread_ts", ""),
                "questioner": question_message.get("username", "Unknown"),
                "answerer": answer_message.get("username", "Unknown")
            }
        }]


class SlackInsightsPromptTemplate(SemanticPromptTemplate):
    """슬랙 인사이트 데이터 추출 프롬프트 템플릿"""
    
    def __init__(self, llm_client: LLMClient):
        """
        초기화
        
        Args:
            llm_client: LLM 클라이언트
        """
        self.llm_client = llm_client
    
    async def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        슬랙 스레드에서 인사이트 데이터 처리
        
        Args:
            data: 스레드 데이터
            
        Returns:
            추출된 인사이트 데이터 목록
        """
        # 스레드 내 모든 메시지의 텍스트 추출
        messages = data.get("messages", [])
        thread_content = "\n".join([msg.get("text", "") for msg in messages])
        
        prompt = f"""
        다음 슬랙 스레드에서 유의미한 인사이트를 추출해주세요:
        
        내용:
        {thread_content}
        
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
        
        result = await self.llm_client.generate(prompt)
        
        insights = []
        for insight_data in result.get("insights", []):
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
                    "channel": data.get("channel", ""),
                    "thread_ts": data.get("thread_ts", "")
                }
            }
            
            # 참조 타입인 경우 reference_type 추가
            if semantic_type == SemanticType.REFERENCE and "reference_type" in insight_data:
                insight["reference_type"] = insight_data["reference_type"]
            
            insights.append(insight)
        
        return insights


class NotionInsightsPromptTemplate(SemanticPromptTemplate):
    """노션 인사이트 데이터 추출 프롬프트 템플릿"""
    
    def __init__(self, llm_client: LLMClient):
        """
        초기화
        
        Args:
            llm_client: LLM 클라이언트
        """
        self.llm_client = llm_client
    
    async def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        노션 섹션에서 인사이트 데이터 처리
        
        Args:
            data: 섹션과 문서 데이터를 포함한 딕셔너리
                - section: 섹션 데이터
                - document: 원본 문서 데이터
            
        Returns:
            추출된 인사이트 데이터 목록
        """
        section = data.get("section", {})
        document = data.get("document", {})
        
        prompt = f"""
        다음 노션 문서 섹션에서 유의미한 인사이트를 추출해주세요:
        
        제목: {section.get('title', '')}
        내용:
        {' '.join(section.get('content', []))}
        
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
        
        result = await self.llm_client.generate(prompt)
        
        insights = []
        for insight_data in result.get("insights", []):
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


class NotionInstructionsPromptTemplate(SemanticPromptTemplate):
    """노션 작업 지침 데이터 추출 프롬프트 템플릿"""
    
    def __init__(self, llm_client: LLMClient):
        """
        초기화
        
        Args:
            llm_client: LLM 클라이언트
        """
        self.llm_client = llm_client
    
    async def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        노션 섹션에서 작업 지침 데이터 처리
        
        Args:
            data: 섹션과 문서 데이터를 포함한 딕셔너리
                - section: 섹션 데이터
                - document: 원본 문서 데이터
            
        Returns:
            추출된 작업 지침 데이터 목록
        """
        section = data.get("section", {})
        document = data.get("document", {})
        
        prompt = f"""
        다음 노션 문서 섹션에서 작업 지침이나 단계별 안내를 추출해주세요:
        
        제목: {section.get('title', '')}
        내용:
        {' '.join(section.get('content', []))}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "instructions": [
                {{
                    "content": "작업 지침 내용",
                    "keywords": ["키워드1", "키워드2", ...]
                }},
                // 더 많은 지침...
            ]
        }}
        ```
        
        작업 지침이 없다면 빈 배열을 반환하세요. JSON 형식만 응답해주세요.
        """
        
        result = await self.llm_client.generate(prompt)
        
        instructions = []
        for instruction_data in result.get("instructions", []):
            instruction = {
                "type": SemanticType.INSTRUCTION,
                "content": instruction_data.get("content", ""),
                "keywords": instruction_data.get("keywords", []),
                "source": {
                    "type": "notion_document",
                    "document_id": document.get("id", ""),
                    "document_title": document.get("title", ""),
                    "section_title": section.get("title", "")
                }
            }
            
            instructions.append(instruction)
        
        return instructions


class NotionReferencesPromptTemplate(SemanticPromptTemplate):
    """노션 참조 정보 데이터 추출 프롬프트 템플릿"""
    
    def __init__(self, llm_client: LLMClient):
        """
        초기화
        
        Args:
            llm_client: LLM 클라이언트
        """
        self.llm_client = llm_client
    
    async def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        노션 섹션에서 참조 정보 데이터 처리
        
        Args:
            data: 섹션과 문서 데이터를 포함한 딕셔너리
                - section: 섹션 데이터
                - document: 원본 문서 데이터
            
        Returns:
            추출된 참조 정보 데이터 목록
        """
        section = data.get("section", {})
        document = data.get("document", {})
        
        prompt = f"""
        다음 노션 문서 섹션에서 링크, API 참조, 코드 스니펫 등 참조 정보를 추출해주세요:
        
        제목: {section.get('title', '')}
        내용:
        {' '.join(section.get('content', []))}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "references": [
                {{
                    "content": "참조 정보 내용",
                    "reference_type": "링크|API|코드|문서",  // 참조 유형
                    "keywords": ["키워드1", "키워드2", ...]
                }},
                // 더 많은 참조...
            ]
        }}
        ```
        
        참조 정보가 없다면 빈 배열을 반환하세요. JSON 형식만 응답해주세요.
        """
        
        result = await self.llm_client.generate(prompt)
        
        references = []
        for reference_data in result.get("references", []):
            reference = {
                "type": SemanticType.REFERENCE,
                "content": reference_data.get("content", ""),
                "reference_type": reference_data.get("reference_type", "링크"),
                "keywords": reference_data.get("keywords", []),
                "source": {
                    "type": "notion_document",
                    "document_id": document.get("id", ""),
                    "document_title": document.get("title", ""),
                    "section_title": section.get("title", "")
                }
            }
            
            references.append(reference)
        
        return references


# 프롬프트 템플릿 팩토리
class PromptTemplateFactory:
    """프롬프트 템플릿 팩토리"""
    
    @staticmethod
    def create_slack_templates(llm_client: LLMClient) -> Dict[str, SemanticPromptTemplate]:
        """
        슬랙 프롬프트 템플릿 생성
        
        Args:
            llm_client: LLM 클라이언트
            
        Returns:
            유형별 프롬프트 템플릿 딕셔너리
        """
        return {
            "qna": SlackQnAPromptTemplate(llm_client),
            "insights": SlackInsightsPromptTemplate(llm_client)
        }
    
    @staticmethod
    def create_notion_templates(llm_client: LLMClient) -> Dict[str, SemanticPromptTemplate]:
        """
        노션 프롬프트 템플릿 생성
        
        Args:
            llm_client: LLM 클라이언트
            
        Returns:
            유형별 프롬프트 템플릿 딕셔너리
        """
        return {
            "insights": NotionInsightsPromptTemplate(llm_client),
            "instructions": NotionInstructionsPromptTemplate(llm_client),
            "references": NotionReferencesPromptTemplate(llm_client)
        } 