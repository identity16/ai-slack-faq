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
                    "term_type": "service/development/design/marketing/etc",  // 서비스, 개발, 디자인, 마케팅, 기타 등등
                    "confidence": "high/medium/low",         // 정의에 대한 확신도
                    "needs_review": true/false,              // 전문가 검토 필요 여부
                    "keywords": ["키워드1", "키워드2", ...]
                }},
                // 더 많은 용어...
            ]
        }}
        ```
        
        용어 정의에 대한 가이드라인:
        1. 'term'은 도메인 전문 용어, 약어, 중요 개념 등을 포함합니다.
        2. 'definition'은 명확하고 간결하게 용어를 설명합니다.
        3. 'term_type'은 다음과 같이 구분합니다:
           - service: 서비스 용어
           - development: 개발 용어
           - design: 디자인 용어
           - marketing: 마케팅 용어
           - etc: 기타 용어
        4. 'confidence'는 정의의 확신도를 나타냅니다:
           - high: 명확히 정의된 경우
           - medium: 맥락에서 유추 가능한 경우
           - low: 불확실하거나 추정한 경우
        5. 'needs_review'는 전문가 검토가 필요한지 여부입니다:
           - true: 정의가 불확실하거나 추가 검증이 필요한 경우
           - false: 정의가 신뢰할 수 있는 경우
        
        서비스 용어에 중점을 두고 추출하되, 맥락상 중요한 개발, 디자인, 마케팅 용어도 포함해주세요.
        용어를 찾을 수 없으면 빈 배열을 반환하세요. JSON 형식만 응답해주세요.
        """
        
        result = await self.llm_client.generate(prompt)
        
        glossary_items = []
        for item in result.get("glossary_items", []):
            glossary_item = {
                "type": SemanticType.GLOSSARY,
                "term": item.get("term", ""),
                "definition": item.get("definition", ""),
                "term_type": item.get("term_type", "etc"),
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
        노션 페이지에서 용어 정의 데이터 처리
        
        Args:
            data: 페이지 데이터
            
        Returns:
            추출된 용어집 데이터 목록
        """
        # 페이지 내용 추출
        page_content = data.get("content", "")
        page_title = data.get("title", "")
        
        prompt = f"""
        다음 노션 페이지에서 도메인 용어와 그 정의를 추출해주세요:
        
        제목: {page_title}
        
        내용:
        {page_content}
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "glossary_items": [
                {{
                    "term": "용어",
                    "definition": "용어에 대한 정의",
                    "term_type": "service/development/design/marketing/etc",  // 서비스, 개발, 디자인, 마케팅, 기타 등등
                    "confidence": "high/medium/low",         // 정의에 대한 확신도
                    "needs_review": true/false,              // 전문가 검토 필요 여부
                    "keywords": ["키워드1", "키워드2", ...]
                }},
                // 더 많은 용어...
            ]
        }}
        ```
        
        용어 정의에 대한 가이드라인:
        1. 'term'은 도메인 전문 용어, 약어, 중요 개념 등을 포함합니다.
        2. 'definition'은 명확하고 간결하게 용어를 설명합니다.
        3. 'term_type'은 다음과 같이 구분합니다:
           - service: 서비스 용어
           - development: 개발 용어
           - design: 디자인 용어
           - marketing: 마케팅 용어
           - etc: 기타 용어
        4. 'confidence'는 정의의 확신도를 나타냅니다:
           - high: 명확히 정의된 경우
           - medium: 맥락에서 유추 가능한 경우
           - low: 불확실하거나 추정한 경우
        5. 'needs_review'는 전문가 검토가 필요한지 여부입니다:
           - true: 정의가 불확실하거나 추가 검증이 필요한 경우
           - false: 정의가 신뢰할 수 있는 경우
        
        서비스 용어에 중점을 두고 추출하되, 맥락상 중요한 개발, 디자인, 마케팅 용어도 포함해주세요.
        용어를 찾을 수 없으면 빈 배열을 반환하세요. JSON 형식만 응답해주세요.
        """
        
        result = await self.llm_client.generate(prompt)
        
        glossary_items = []
        for item in result.get("glossary_items", []):
            glossary_item = {
                "type": SemanticType.GLOSSARY,
                "term": item.get("term", ""),
                "definition": item.get("definition", ""),
                "term_type": item.get("term_type", "etc"),
                "confidence": item.get("confidence", "low"),
                "needs_review": item.get("needs_review", True),
                "keywords": item.get("keywords", []),
                "source": {
                    "type": "notion_page",
                    "page_id": data.get("page_id", ""),
                    "title": page_title
                }
            }
            
            glossary_items.append(glossary_item)
        
        return glossary_items


class GlossaryEnhancementPromptTemplate:
    """
    낮은 확신도의 용어 정의를 향상시키기 위한 프롬프트 템플릿
    """
    
    def __init__(self, llm_client: LLMClient) -> None:
        """
        초기화
        
        Args:
            llm_client: 언어 모델 클라이언트
        """
        self.llm_client = llm_client
    
    async def process(self, terms_data: List[Dict[str, Any]], context: str = "") -> List[Dict[str, Any]]:
        """
        낮은 확신도의 용어 정의를 향상시키는 처리
        
        Args:
            terms_data: 용어 데이터 목록
            context: 추가 컨텍스트 (선택 사항)
            
        Returns:
            향상된 용어집 항목 목록
        """
        # 입력 용어 목록 구성
        terms_items = []
        for item in terms_data:
            terms_items.append({
                "term": item.get("term", ""),
                "definition": item.get("definition", ""),
                "term_type": item.get("term_type", "etc"),
                "confidence": item.get("confidence", "low"),
                "needs_review": item.get("needs_review", True),
                "keywords": item.get("keywords", [])
            })
        
        terms_json = json.dumps(terms_items, ensure_ascii=False)
        
        prompt = f"""
        다음은 낮은 확신도로 정의된 용어 목록입니다. 이 용어들의 정의를 향상시켜주세요:
        
        용어 데이터:
        {terms_json}
        
        {f"추가 컨텍스트 정보:{os.linesep}{context}" if context else ""}
        
        각 용어에 대해 다음을 수행해주세요:
        1. 정의를 개선하고 보다 명확하게 작성해주세요
        2. 주어진 컨텍스트를 활용하여 용어를 상세히 설명해주세요
        3. 정의에 대한 확신도를 재평가해주세요 (high/medium/low)
        4. 필요하다면 대체 정의를 제공해주세요
        
        다음 JSON 형식으로 응답해주세요:
        ```json
        {{
            "glossary_items": [
                {{
                    "term": "용어",
                    "definition": "개선된 정의",
                    "term_type": "service/development/design/marketing/etc",
                    "confidence": "high/medium/low",         
                    "needs_review": true/false,              
                    "alternative_definitions": ["대체 정의1", "대체 정의2"],
                    "keywords": ["키워드1", "키워드2", ...],
                    "domain_hints": ["도메인/분야"]
                }},
                // 더 많은 용어...
            ]
        }}
        ```
        
        참고사항:
        - 정의가 여전히 불확실한 경우, 여러 대체 정의를 제공하고 confidence를 'low'로 유지하세요
        - 'term_type'은 용어가 서비스, 개발, 디자인, 마케팅, 기타 등등 구분합니다
        - 기술, 산업, 또는 특정 도메인 분야의 힌트를 'domain_hints'에 포함하세요
        
        용어 개선에 집중하고 JSON 형식만 응답해주세요.
        """
        
        result = await self.llm_client.generate(prompt)
        
        enhanced_items = []
        for item in result.get("glossary_items", []):
            enhanced_item = {
                "type": SemanticType.GLOSSARY,
                "term": item.get("term", ""),
                "definition": item.get("definition", ""),
                "term_type": item.get("term_type", "etc"),
                "confidence": item.get("confidence", "low"),
                "needs_review": item.get("needs_review", True),
                "alternative_definitions": item.get("alternative_definitions", []),
                "keywords": item.get("keywords", []),
                "domain_hints": item.get("domain_hints", [])
            }
            
            # 원본 용어의 소스 정보 보존
            for original_item in terms_data:
                if original_item.get("term") == enhanced_item["term"]:
                    if "source" in original_item:
                        enhanced_item["source"] = original_item["source"]
                    break
            
            enhanced_items.append(enhanced_item)
        
        return enhanced_items


# 프롬프트 템플릿을 위한 유틸리티 함수
async def enhance_low_confidence_terms(
    glossary_items: List[Dict[str, Any]],
    llm_client: LLMClient,
    context: str = "",
    confidence_threshold: str = "medium"
) -> List[Dict[str, Any]]:
    """
    낮은 확신도의 용어를 개선합니다.
    
    Args:
        glossary_items: 용어집 항목 목록
        llm_client: LLM 클라이언트
        context: 컨텍스트 정보 (선택 사항)
        confidence_threshold: 개선이 필요한 확신도 임계값 (이 값 이하의 확신도는 개선됨)
        
    Returns:
        개선된 용어집 항목 목록
    """
    # 낮은 확신도 항목 필터링
    low_confidence_items = [
        item for item in glossary_items 
        if item.get("confidence") in ["low", "medium"] and item.get("confidence") <= confidence_threshold
    ]
    
    # 높은 확신도 항목 보존
    high_confidence_items = [
        item for item in glossary_items
        if item.get("confidence") not in ["low", "medium"] or item.get("confidence") > confidence_threshold
    ]
    
    # 낮은 확신도 항목이 없으면 원본 반환
    if not low_confidence_items:
        return glossary_items
    
    # 낮은 확신도 항목 처리
    template = GlossaryEnhancementPromptTemplate(llm_client)
    enhanced_items = await template.process(low_confidence_items, context)
    
    # 결과 병합: 향상된 항목을 기존 항목과 병합
    result_items = high_confidence_items.copy()
    
    for enhanced_item in enhanced_items:
        # 동일한 용어의 기존 항목이 있는지 확인
        existing_index = next(
            (i for i, item in enumerate(result_items) 
             if item.get("term") == enhanced_item.get("term")),
            None
        )
        
        # 기존 항목이 있고, 향상된 항목의 확신도가 더 높으면 교체
        if existing_index is not None:
            existing_confidence = result_items[existing_index].get("confidence", "low")
            enhanced_confidence = enhanced_item.get("confidence", "low")
            
            confidence_levels = {"high": 3, "medium": 2, "low": 1}
            if confidence_levels.get(enhanced_confidence, 0) > confidence_levels.get(existing_confidence, 0):
                result_items[existing_index] = enhanced_item
        else:
            # 기존 항목이 없으면 추가
            result_items.append(enhanced_item)
    
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