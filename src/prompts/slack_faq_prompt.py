import os
import json
import re
from typing import List, Dict, Tuple, Any, Optional
from openai import OpenAI
from tqdm import tqdm

class SlackFAQPrompt:
    """슬랙 스레드에서 FAQ를 생성하는 프롬프트 클래스"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        SlackFAQPrompt 초기화
        
        Args:
            api_key: OpenAI API 키 (없으면 환경 변수에서 가져옴)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
            
        # OpenAI 클라이언트 초기화
        self.client = OpenAI(api_key=self.api_key)

    def extract_raw_qa(self, threads: List[Tuple[str, str, str]]) -> List[Dict]:
        """
        스레드에서 초기 Q&A 쌍 추출
        
        Args:
            threads: [(질문, 답변, 출처 링크)] 형태의 리스트
            
        Returns:
            변환된 QA 항목 리스트
        """
        raw_qas = []
        
        for question, answer, thread_link in tqdm(threads, desc="Q&A 추출 중"):
            try:
                # 질문/답변 정제
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": """슬랙 대화에서 질문과 답변을 추출하는 AI입니다.
당신의 임무는:
1. 대화에 명확한 질문과 그에 대한 답변이 포함되어 있는지 확인
2. 기술적 정확성을 유지하면서 핵심 질문과 답변 추출
3. "question", "answer", "context" 필드가 있는 JSON 객체로 출력 포맷팅
4. 대화에 명확한 Q&A가 포함되어 있지 않으면 {"question": null, "answer": null, "context": null} 반환

출력 형식 예시:
{
    "question": "스테이징 환경에서 배포 오류를 어떻게 해결할 수 있나요?",
    "answer": "배포 오류는 환경 변수가 누락되어 발생했습니다. .env.staging 파일에 DATABASE_URL을 추가하면 해결됩니다.",
    "context": "배포, 환경 변수, 스테이징 환경"
}"""},
                        {"role": "user", "content": f"다음 슬랙 대화에서 핵심 질문과 답변을 추출해주세요:\n\n질문: {question}\n\n답변: {answer}"}
                    ],
                    temperature=0.3
                )
                
                result = response.choices[0].message.content
                
                try:
                    # 수정된 부분: JSON 문자열 추출을 위한 전처리
                    json_str = self._extract_json_string(result)
                    qa_item = json.loads(json_str)
                    
                    if qa_item and isinstance(qa_item, dict):
                        if qa_item.get("question") and qa_item.get("answer"):
                            qa_item["source_link"] = thread_link
                            raw_qas.append(qa_item)
                except json.JSONDecodeError:
                    print(f"Q&A 파싱 실패: {result[:100]}...")
                    continue
                    
            except Exception as e:
                print(f"Q&A 추출 중 오류 발생: {str(e)}")
                continue
        
        print(f"총 {len(raw_qas)}개의 Q&A 쌍을 추출했습니다.")
        return raw_qas
        
    def group_and_generalize(self, raw_qas: List[Dict]) -> Dict[str, Any]:
        """
        유사한 Q&A 쌍을 그룹화하고 일반화
        
        Args:
            raw_qas: 추출된 Q&A 항목 리스트
            
        Returns:
            그룹화된 FAQ 항목
        """
        if not raw_qas:
            return {"grouped_faqs": []}
            
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """Q&A 쌍을 분석하고 종합적인 FAQ 항목으로 일반화하는 AI입니다.

당신의 임무는:
1. 유사한 질문을 함께 그룹화
2. 특정 질문을 더 넓게 적용 가능한 질문으로 일반화
3. 추가 컨텍스트와 모범 사례로 답변 강화
4. 그룹화된 FAQ 항목의 JSON 배열로 출력 포맷팅
5. 반드시 유효한 JSON 형식으로 응답할 것

출력 형식 예시:
{
    "grouped_faqs": [
        {
            "category": "환경 설정",
            "items": [
                {
                    "general_question": "환경 변수 설정은 어떻게 관리해야 하나요?",
                    "specific_examples": ["스테이징 환경에서 DB_URL 설정", "프로덕션 환경의 API 키 관리"],
                    "comprehensive_answer": "환경 변수 관리 모범 사례:\\n1. 환경별 .env 파일 사용 (.env.staging, .env.production)\\n2. 민감한 정보는 암호화하여 저장\\n3. 환경 변수 템플릿 (.env.example) 제공\\n4. 주기적인 키 로테이션 실행",
                    "best_practices": ["환경 변수 암호화", "정기적인 키 갱신", "접근 권한 제한"],
                    "related_topics": ["보안", "설정 관리", "배포 프로세스"],
                    "source_links": ["https://slack.com/archives/C01234/p1234"]
                }
            ]
        }
    ]
}"""},
                    {"role": "user", "content": f"다음 Q&A 쌍을 분석하고 포괄적인 FAQ 항목으로 그룹화해주세요. 반드시 유효한 JSON 형식으로 응답해주세요:\n\n{json.dumps(raw_qas, indent=2, ensure_ascii=False)}"}
                ],
                temperature=0.3
            )
            
            grouped_result = response.choices[0].message.content
            
            try:
                # 수정된 부분: JSON 문자열 추출을 위한 전처리
                json_str = self._extract_json_string(grouped_result)
                print(f"그룹화 결과 JSON 추출: {json_str[:100]}...")
                
                result_data = json.loads(json_str)
                return result_data
            except json.JSONDecodeError as e:
                print(f"그룹화 결과를 JSON으로 파싱하는 데 실패했습니다: {str(e)}")
                print(f"원본 응답: {grouped_result[:200]}...")
                # 기본 그룹화 데이터 반환
                return self._create_default_grouping(raw_qas)
                
        except Exception as e:
            print(f"Q&A 그룹화 중 오류 발생: {str(e)}")
            return self._create_default_grouping(raw_qas)
    
    def _extract_json_string(self, text: str) -> str:
        """텍스트에서 JSON 문자열 추출"""
        # JSON 블록 추출 시도
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)
            
        # 중괄호 안의 내용 추출 시도
        braces_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if braces_match:
            return braces_match.group(1)
        
        # 추출 실패시 원본 반환
        return text
    
    def _create_default_grouping(self, raw_qas: List[Dict]) -> Dict[str, Any]:
        """기본 그룹화 생성 (파싱 실패 시 대체용)"""
        grouped_faqs = []
        
        # 모든 Q&A 항목을 "일반" 카테고리로 그룹화
        items = []
        for qa in raw_qas:
            item = {
                "general_question": qa.get("question", ""),
                "specific_examples": [],
                "comprehensive_answer": qa.get("answer", ""),
                "best_practices": [],
                "related_topics": qa.get("context", "").split(", ") if qa.get("context") else [],
                "source_links": [qa.get("source_link", "")]
            }
            items.append(item)
        
        if items:
            grouped_faqs.append({
                "category": "일반",
                "items": items
            })
        
        return {"grouped_faqs": grouped_faqs}
    
    def format_final_faq(self, grouped_data: Dict[str, Any]) -> List[Dict]:
        """
        그룹화된 FAQ 데이터를 최종 문서 형식으로 변환
        
        Args:
            grouped_data: 그룹화된 FAQ 데이터
            
        Returns:
            최종 FAQ 항목 리스트
        """
        if not grouped_data or not grouped_data.get("grouped_faqs"):
            return []
            
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """잘 포맷된 한국어 FAQ 문서를 작성하는 AI입니다.

당신의 임무는:
1. 그룹화된 FAQ 항목을 최종 문서 형식으로 변환
2. 문서를 명확하고 전문적으로 만듭니다:
   - 자연스럽고 전문적인 한국어 사용
   - 질문은 간결하지만 설명적이어야 함
   - 명확한 구조와 예제로 답변 포맷팅
   - 관련 컨텍스트와 모범 사례 포함
3. FAQ 항목의 JSON 배열로 출력 포맷팅
4. 반드시 유효한 JSON 형식으로 응답할 것

출력 형식 예시:
{
    "faqs": [
        {
            "category": "환경 설정",
            "question": "환경 변수 설정은 어떻게 관리해야 하나요?",
            "answer": "환경 변수 관리를 위한 모범 사례는 다음과 같습니다:\\n\\n1. 환경별 설정 파일 관리\\n   - .env.staging: 스테이징 환경 설정\\n   - .env.production: 프로덕션 환경 설정\\n\\n2. 보안 관리\\n   - 민감한 정보는 반드시 암호화\\n   - 정기적인 키 로테이션 실행\\n   - 접근 권한 제한 설정\\n\\n3. 문서화\\n   - .env.example 템플릿 제공\\n   - 필수 환경 변수 목록 관리",
            "source_links": ["https://slack.com/archives/C01234/p1234"]
        }
    ]
}"""},
                    {"role": "user", "content": f"다음 그룹화된 FAQ 항목을 최종 한국어 문서로 변환해주세요. 반드시 유효한 JSON 형식으로 응답해주세요:\n\n{json.dumps(grouped_data, indent=2, ensure_ascii=False)}"}
                ],
                temperature=0.3
            )
            
            final_result = response.choices[0].message.content
            
            try:
                # 수정된 부분: JSON 문자열 추출을 위한 전처리
                json_str = self._extract_json_string(final_result)
                
                result_json = json.loads(json_str)
                return result_json.get("faqs", [])
            except json.JSONDecodeError as e:
                print(f"최종 FAQ 결과를 JSON으로 파싱하는 데 실패했습니다: {str(e)}")
                print(f"원본 응답: {final_result[:200]}...")
                
                # 기본 FAQ 직접 생성
                return self._create_default_faqs(grouped_data)
                
        except Exception as e:
            print(f"최종 FAQ 포맷팅 중 오류 발생: {str(e)}")
            return self._create_default_faqs(grouped_data)
    
    def _create_default_faqs(self, grouped_data: Dict[str, Any]) -> List[Dict]:
        """기본 FAQ 생성 (파싱 실패 시 대체용)"""
        faqs = []
        
        for category_data in grouped_data.get("grouped_faqs", []):
            category = category_data.get("category", "일반")
            
            for item in category_data.get("items", []):
                question = item.get("general_question", "")
                answer = item.get("comprehensive_answer", "")
                source_links = item.get("source_links", [])
                
                if question and answer:
                    faqs.append({
                        "category": category,
                        "question": question,
                        "answer": answer,
                        "source_links": source_links
                    })
        
        return faqs
    
    def generate_faq(self, threads: List[Tuple[str, str, str]]) -> str:
        """
        스레드 목록에서 FAQ 마크다운 생성
        
        Args:
            threads: [(질문, 답변, 출처 링크)] 형태의 리스트
            
        Returns:
            FAQ 마크다운 텍스트
        """
        # 1단계: Q&A 쌍 추출
        raw_qas = self.extract_raw_qa(threads)
        
        # 2단계: Q&A 그룹화 및 일반화
        grouped_data = self.group_and_generalize(raw_qas)
        
        # 3단계: 최종 FAQ 포맷팅
        final_faqs = self.format_final_faq(grouped_data)
        
        # 마크다운으로 변환
        return self.convert_to_markdown(final_faqs)
    
    def convert_to_markdown(self, faqs: List[Dict]) -> str:
        """
        FAQ 항목을 마크다운 형식으로 변환
        
        Args:
            faqs: FAQ 항목 리스트
            
        Returns:
            마크다운 텍스트
        """
        if not faqs:
            return "# 자주 묻는 질문\n\n자주 묻는 질문이 아직 없습니다."
        
        markdown = "# 자주 묻는 질문\n\n"
        
        # 카테고리별로 정렬
        categories = {}
        for faq in faqs:
            category = faq.get("category", "일반")
            if category not in categories:
                categories[category] = []
            categories[category].append(faq)
        
        # 각 카테고리와 FAQ 항목 추가
        for category, items in categories.items():
            markdown += f"## {category}\n\n"
            
            for item in items:
                question = item.get("question", "")
                answer = item.get("answer", "")
                source_links = item.get("source_links", [])
                
                markdown += f"### {question}\n\n"
                markdown += f"{answer}\n\n"
                
                if source_links:
                    markdown += "#### 출처\n\n"
                    for link in source_links:
                        if link:  # 빈 링크는 건너뛰기
                            markdown += f"- [{link}]({link})\n"
                markdown += "\n---\n\n"
        
        return markdown