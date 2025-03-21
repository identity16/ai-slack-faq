"""
슬랙 FAQ 생성 모듈 - 정제된 슬랙 데이터로 FAQ 문서 생성
"""
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

class SlackFAQGenerator:
    """
    슬랙 데이터를 기반으로 FAQ 문서를 생성하는 클래스
    """
    
    def __init__(self):
        """생성기 초기화"""
        # OpenAI API 키 설정
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        # 문서 저장 디렉토리
        self.documents_dir = Path("results")
        os.makedirs(self.documents_dir, exist_ok=True)
    
    def generate_faq(self, processed_data: List[Dict[str, Any]], channel_name: str = "일반") -> str:
        """
        FAQ 문서 생성
        
        Args:
            processed_data: 처리된 슬랙 데이터
            channel_name: 슬랙 채널 이름
            
        Returns:
            생성된 FAQ 마크다운
        """
        if not processed_data:
            return "# FAQ\n\n처리된 데이터가 없습니다."
        
        # 질문을 카테고리별로 그룹화
        categorized_questions = self._categorize_questions(processed_data)
        
        # FAQ 마크다운 생성
        faq_markdown = self._create_faq_markdown(categorized_questions, channel_name)
        
        return faq_markdown
    
    def save_faq_document(self, faq_content: str, channel_name: str, custom_filename: Optional[str] = None) -> str:
        """
        FAQ 문서 저장
        
        Args:
            faq_content: FAQ 문서 내용
            channel_name: 채널 이름
            custom_filename: 사용자 지정 파일명 (None이면 자동 생성)
            
        Returns:
            저장된 파일 경로
        """
        if custom_filename:
            filename = custom_filename if custom_filename.endswith('.md') else f"{custom_filename}.md"
        else:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"faq_{channel_name}_{timestamp}.md"
            
        file_path = self.documents_dir / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(faq_content)
            
        return str(file_path)
    
    def enhance_faq_with_llm(self, faq_content: str) -> str:
        """
        LLM을 사용하여 FAQ 문서 개선
        
        Args:
            faq_content: 기본 FAQ 내용
            
        Returns:
            개선된 FAQ 내용
        """
        try:
            # 프롬프트 작성
            prompt = f"""
다음 FAQ 문서의 품질을 향상시켜주세요:
1. 비슷한 질문을 통합하고 더 일반적인 형태로 만들어주세요
2. 답변을 명확하고 포괄적으로 개선해주세요
3. 필요한 경우 추가 컨텍스트나 예시를 추가해주세요
4. 전체적인 가독성과 구조를 개선해주세요
5. 마크다운 형식을 유지해주세요

FAQ 문서:
```
{faq_content}
```

개선된 FAQ 문서를 마크다운 형식으로 제공해주세요.
"""
            
            # OpenAI API 호출 (실제 구현에서 활성화)
            # response = openai.chat.completions.create(
            #     model="gpt-4o",
            #     messages=[
            #         {"role": "system", "content": "당신은 기술 문서와 FAQ를 개선하는 전문가입니다."},
            #         {"role": "user", "content": prompt}
            #     ],
            #     temperature=0.5,
            #     max_tokens=4000
            # )
            # 
            # return response.choices[0].message.content
            
            # 개발 중에는 원본 반환
            return faq_content
            
        except Exception as e:
            print(f"FAQ 개선 중 오류 발생: {e}")
            return faq_content
    
    def _categorize_questions(self, processed_data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        질문을 카테고리별로 분류
        
        Args:
            processed_data: 처리된 Q&A 데이터
            
        Returns:
            카테고리별 질문 그룹
        """
        categorized = {}
        
        for item in processed_data:
            # 태그가 있으면 사용, 없으면 '기타' 카테고리
            tags = item.get("tags", ["기타"])
            
            # 각 태그에 질문 추가
            for tag in tags:
                if tag not in categorized:
                    categorized[tag] = []
                    
                categorized[tag].append(item)
        
        return categorized
    
    def _create_faq_markdown(self, categorized_questions: Dict[str, List[Dict[str, Any]]], channel_name: str) -> str:
        """
        카테고리별 질문으로 FAQ 마크다운 생성
        
        Args:
            categorized_questions: 카테고리별 Q&A 목록
            channel_name: 채널 이름
            
        Returns:
            마크다운 형식의 FAQ
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 문서 헤더
        markdown = f"# {channel_name} 채널 FAQ\n\n"
        markdown += f"*생성일: {today}*\n\n"
        
        # 목차 생성
        markdown += "## 목차\n\n"
        for category in sorted(categorized_questions.keys()):
            markdown += f"- [{category}](#{category.lower()})\n"
        
        markdown += "\n"
        
        # 카테고리별 콘텐츠 생성
        for category in sorted(categorized_questions.keys()):
            questions = categorized_questions[category]
            
            markdown += f"## {category}\n\n"
            
            # 각 질문-답변 쌍 추가
            for i, item in enumerate(questions, 1):
                question = item.get("question", "")
                answer = item.get("answer", "")
                answerer = item.get("answerer", "")
                
                markdown += f"### Q{i}: {question}\n\n"
                markdown += f"{answer}\n\n"
                
                if answerer and answerer != "Unknown":
                    markdown += f"*답변자: {answerer}*\n\n"
        
        return markdown 