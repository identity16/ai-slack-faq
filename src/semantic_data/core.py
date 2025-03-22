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


class SlackGlossaryPromptTemplate(SemanticPromptTemplate):
    """슬랙 용어집 데이터 추출 프롬프트 템플릿"""
    
    def __init__(self, llm_client: LLMClient):
        """
        초기화
        
        Args:
            llm_client: LLM 클라이언트
        """
        self.llm_client = llm_client
    
    async def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        슬랙 스레드에서 용어 정의 데이터 처리
        
        Args:
            data: 스레드 데이터
            
        Returns:
            추출된 용어집 데이터 목록
        """
        # 스레드 내 모든 메시지의 텍스트 추출
        messages = data.get("messages", [])
        thread_content = "\n".join([msg.get("text", "") for msg in messages])
        
        prompt = f"""
        다음 슬랙 스레드에서 도메인 용어와 그 정의를 추출해주세요:
        
        내용:
        {thread_content}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "glossary_items": [
                {{
                    "term": "용어",
                    "definition": "용어에 대한 정의",
                    "confidence": "high/medium/low",  // 정의에 대한 확신도
                    "needs_review": true/false,       // 전문가 검토 필요 여부
                    "keywords": ["키워드1", "키워드2", ...]
                }},
                // 더 많은 용어...
            ]
        }}
        ```
        
        용어 정의에 대한 가이드라인:
        1. 'term'은 도메인 전문 용어, 약어, 중요 개념 등을 포함합니다.
        2. 'definition'은 명확하고 간결하게 용어를 설명합니다.
        3. 'confidence'는 정의의 확신도를 나타냅니다:
           - high: 명확히 정의된 경우
           - medium: 맥락에서 유추 가능한 경우
           - low: 불확실하거나 추정한 경우
        4. 'needs_review'는 전문가 검토가 필요한지 여부입니다:
           - true: 정의가 불확실하거나 추가 검증이 필요한 경우
           - false: 정의가 신뢰할 수 있는 경우
        
        용어를 찾을 수 없으면 빈 배열을 반환하세요. JSON 형식만 응답해주세요.
        """
        
        result = await self.llm_client.generate(prompt)
        
        glossary_items = []
        for item in result.get("glossary_items", []):
            glossary_item = {
                "type": SemanticType.GLOSSARY,
                "term": item.get("term", ""),
                "definition": item.get("definition", ""),
                "confidence": item.get("confidence", "low"),
                "needs_review": item.get("needs_review", True),
                "keywords": item.get("keywords", []),
                "source": {
                    "type": "slack_thread",
                    "channel": data.get("channel", ""),
                    "thread_ts": data.get("thread_ts", ""),
                    "message_count": len(messages)
                }
            }
            
            glossary_items.append(glossary_item)
        
        return glossary_items


class NotionGlossaryPromptTemplate(SemanticPromptTemplate):
    """노션 용어집 데이터 추출 프롬프트 템플릿"""
    
    def __init__(self, llm_client: LLMClient):
        """
        초기화
        
        Args:
            llm_client: LLM 클라이언트
        """
        self.llm_client = llm_client
    
    async def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        노션 섹션에서 용어 정의 데이터 처리
        
        Args:
            data: 섹션과 문서 데이터를 포함한 딕셔너리
                - section: 섹션 데이터
                - document: 원본 문서 데이터
            
        Returns:
            추출된 용어집 데이터 목록
        """
        section = data.get("section", {})
        document = data.get("document", {})
        
        section_title = section.get('title', '')
        section_content = ' '.join(section.get('content', []))
        
        # 용어집과 관련된 섹션인지 사전 확인 (최적화를 위함)
        glossary_keywords = ["용어", "glossary", "terminology", "definition", "dictionary", "약어", "abbreviation", "term"]
        is_likely_glossary = False
        
        # 제목에 용어집 관련 키워드가 있는지 확인
        if any(keyword in section_title.lower() for keyword in glossary_keywords):
            is_likely_glossary = True
        # 아니면 내용에 "용어:" 또는 "정의:" 와 같은 패턴이 있는지 확인
        elif any(f"{keyword}:" in section_content.lower() for keyword in glossary_keywords):
            is_likely_glossary = True
        
        # 용어집 관련 섹션이 아니면 빈 결과 반환 (최적화)
        if not is_likely_glossary and len(section_content) < 500:  # 짧은 섹션만 스킵
            return []
        
        prompt = f"""
        다음 노션 문서 섹션에서 도메인 용어와 그 정의를 추출해주세요:
        
        제목: {section_title}
        내용:
        {section_content}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "glossary_items": [
                {{
                    "term": "용어",
                    "definition": "용어에 대한 정의",
                    "confidence": "high/medium/low",  // 정의에 대한 확신도
                    "needs_review": true/false,       // 전문가 검토 필요 여부
                    "keywords": ["키워드1", "키워드2", ...]
                }},
                // 더 많은 용어...
            ]
        }}
        ```
        
        용어 정의에 대한 가이드라인:
        1. 'term'은 도메인 전문 용어, 약어, 중요 개념 등을 포함합니다.
        2. 'definition'은 명확하고 간결하게 용어를 설명합니다.
        3. 'confidence'는 정의의 확신도를 나타냅니다:
           - high: 문서에 명확히 정의된 경우
           - medium: 맥락에서 유추 가능한 경우
           - low: 불확실하거나 추정한 경우
        4. 'needs_review'는 전문가 검토가 필요한지 여부입니다:
           - true: 정의가 불확실하거나 추가 검증이 필요한 경우
           - false: 정의가 신뢰할 수 있는 경우
        
        용어를 찾을 수 없으면 빈 배열을 반환하세요. JSON 형식만 응답해주세요.
        """
        
        result = await self.llm_client.generate(prompt)
        
        glossary_items = []
        for item in result.get("glossary_items", []):
            confidence = item.get("confidence", "low")
            needs_review = item.get("needs_review", True)
            
            # 낮은 확신도 항목은 항상 검토 필요로 설정
            if confidence == "low":
                needs_review = True
            
            glossary_item = {
                "type": SemanticType.GLOSSARY,
                "term": item.get("term", ""),
                "definition": item.get("definition", ""),
                "confidence": confidence,
                "needs_review": needs_review,
                "keywords": item.get("keywords", []),
                "source": {
                    "type": "notion_document",
                    "document_id": document.get("id", ""),
                    "document_title": document.get("title", ""),
                    "section_title": section_title
                }
            }
            
            glossary_items.append(glossary_item)
        
        return glossary_items


class GlossaryEnhancementPromptTemplate(SemanticPromptTemplate):
    """용어 정의 개선 프롬프트 템플릿"""
    
    def __init__(self, llm_client: LLMClient):
        """
        초기화
        
        Args:
            llm_client: LLM 클라이언트
        """
        self.llm_client = llm_client
    
    async def process(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        낮은 확신도의 용어 정의를 개선
        
        Args:
            data: 용어 데이터 리스트를 포함한 딕셔너리
                - items: 확신도가 낮은 용어 항목 리스트
                - context: 용어가 사용된 문맥 정보
            
        Returns:
            개선된 용어집 데이터 목록
        """
        items = data.get("items", [])
        context = data.get("context", "")
        
        if not items:
            return []
        
        # 용어 목록 구성
        terms_list = "\n".join([f"- {item['term']}: {item['definition']} (확신도: {item['confidence']})" 
                               for item in items])
        
        prompt = f"""
        다음은 도메인 용어집에서 확신도가 낮거나 추가 검토가 필요한 용어들입니다:
        
        {terms_list}
        
        이 용어들이 사용된 문맥:
        {context}
        
        각 용어에 대해 다음을 수행해주세요:
        1. 용어의 정의를 개선하거나 명확히 합니다.
        2. 문맥에서 추론할 수 있는 정보를 활용합니다.
        3. 확신도를 재평가합니다.
        4. 여전히 불확실한 경우 대안적 정의를 제시합니다.
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "enhanced_items": [
                {{
                    "term": "원래 용어",
                    "definition": "개선된 정의",
                    "confidence": "medium/low",  // 재평가된 확신도
                    "needs_review": true/false,  // 여전히 전문가 검토가 필요한지 여부
                    "alternative_definitions": ["대안 정의 1", "대안 정의 2"],  // 가능한 다른 정의
                    "keywords": ["키워드1", "키워드2", ...],
                    "domain_hint": "추정되는 도메인 영역" // 용어가 속할 것으로 추정되는 도메인
                }},
                // 더 많은 용어...
            ]
        }}
        ```
        
        JSON 형식만 응답해주세요.
        """
        
        result = await self.llm_client.generate(prompt)
        
        enhanced_items = []
        for item in result.get("enhanced_items", []):
            original_item = next((i for i in items if i["term"] == item["term"]), {})
            
            enhanced_item = {
                "type": SemanticType.GLOSSARY,
                "term": item.get("term", ""),
                "definition": item.get("definition", ""),
                "confidence": item.get("confidence", "low"),
                "needs_review": item.get("needs_review", True),
                "alternative_definitions": item.get("alternative_definitions", []),
                "keywords": item.get("keywords", original_item.get("keywords", [])),
                "domain_hint": item.get("domain_hint", ""),
                "source": original_item.get("source", {})
            }
            
            enhanced_items.append(enhanced_item)
        
        return enhanced_items


# 프롬프트 템플릿을 위한 유틸리티 함수
async def enhance_low_confidence_terms(llm_client: LLMClient, glossary_items: List[Dict[str, Any]], 
                                      context: str = "") -> List[Dict[str, Any]]:
    """
    확신도가 낮은 용어를 개선
    
    Args:
        llm_client: LLM 클라이언트
        glossary_items: 확신도가 낮거나 검토가 필요한 용어 목록
        context: 용어가 사용된 문맥 정보
        
    Returns:
        개선된 용어 목록
    """
    # 확신도가 낮거나 검토가 필요한 항목 필터링
    low_confidence_items = [item for item in glossary_items 
                           if item.get("confidence") == "low" or item.get("needs_review", False)]
    
    if not low_confidence_items:
        return glossary_items
    
    enhancer = GlossaryEnhancementPromptTemplate(llm_client)
    
    # 강화 처리 수행
    enhanced_items = await enhancer.process({
        "items": low_confidence_items,
        "context": context
    })
    
    # 결과 목록 구성
    result_items = []
    
    # 확신도가 높은 항목은 그대로 유지
    high_confidence_items = [item for item in glossary_items 
                            if item.get("confidence") != "low" and not item.get("needs_review", False)]
    result_items.extend(high_confidence_items)
    
    # 개선된 항목과 원본 항목의 ID로 매핑하여 병합
    for item in enhanced_items:
        original_item = next((i for i in low_confidence_items if i["term"] == item["term"]), None)
        if original_item:
            # 확신도가 여전히 낮으면 대안 정의 추가
            if item.get("confidence") == "low":
                # 원본 항목과 개선된 항목 합치기
                merged_item = {**original_item, **item}
                result_items.append(merged_item)
            else:
                # 확신도가 높아졌으면 개선된 항목 사용
                result_items.append(item)
        else:
            # 새로 발견된 용어라면 추가
            result_items.append(item)
    
    return result_items


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
            "insights": SlackInsightsPromptTemplate(llm_client),
            "glossary": SlackGlossaryPromptTemplate(llm_client)
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
            "references": NotionReferencesPromptTemplate(llm_client),
            "glossary": NotionGlossaryPromptTemplate(llm_client)
        } 