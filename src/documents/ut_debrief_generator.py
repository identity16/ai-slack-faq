"""
UT Debrief 생성 모듈 - 정제된 노션 데이터로 Debrief 문서 생성
"""
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

class UTDebriefGenerator:
    """
    노션 UT 데이터를 기반으로 Debrief 문서를 생성하는 클래스
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
    
    def generate_debrief(self, processed_data: Dict[str, Any]) -> str:
        """
        Debrief 문서 생성
        
        Args:
            processed_data: 처리된 노션 UT 데이터
            
        Returns:
            생성된 Debrief 마크다운
        """
        if not processed_data:
            return "# UT Debrief\n\n처리된 데이터가 없습니다."
        
        # 마크다운 생성
        debrief_markdown = self._create_debrief_markdown(processed_data)
        
        # AI를 사용한 문서 보강 (선택적)
        # debrief_markdown = self.enhance_debrief_with_llm(debrief_markdown)
        
        return debrief_markdown
    
    def save_debrief_document(self, debrief_content: str, custom_filename: Optional[str] = None) -> str:
        """
        Debrief 문서 저장
        
        Args:
            debrief_content: Debrief 문서 내용
            custom_filename: 사용자 지정 파일명 (None이면 자동 생성)
            
        Returns:
            저장된 파일 경로
        """
        if custom_filename:
            filename = custom_filename if custom_filename.endswith('.md') else f"{custom_filename}.md"
        else:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"ut_debrief_{timestamp}.md"
            
        file_path = self.documents_dir / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(debrief_content)
            
        return str(file_path)
    
    def enhance_debrief_with_llm(self, debrief_content: str) -> str:
        """
        LLM을 사용하여 Debrief 문서 개선
        
        Args:
            debrief_content: 기본 Debrief 내용
            
        Returns:
            개선된 Debrief 내용
        """
        try:
            # 프롬프트 작성
            prompt = f"""
다음 UT Debrief 문서의 품질을 향상시켜주세요:
1. 주요 인사이트를 더 명확하게 표현하고 불필요한 내용은 제거해주세요
2. 액션 아이템에 담당자와 일정을 추가하는 등 더 구체적으로 만들어주세요
3. 전체적인 가독성과 구성을 개선해주세요
4. 마크다운 형식을 유지해주세요

UT Debrief 문서:
```
{debrief_content}
```

개선된 UT Debrief 문서를 마크다운 형식으로 제공해주세요.
"""
            
            # OpenAI API 호출 (실제 구현에서 활성화)
            # response = openai.chat.completions.create(
            #     model="gpt-4o",
            #     messages=[
            #         {"role": "system", "content": "당신은 사용자 테스트 문서와 회의록을 개선하는 전문가입니다."},
            #         {"role": "user", "content": prompt}
            #     ],
            #     temperature=0.5,
            #     max_tokens=4000
            # )
            # 
            # return response.choices[0].message.content
            
            # 개발 중에는 원본 반환
            return debrief_content
            
        except Exception as e:
            print(f"Debrief 개선 중 오류 발생: {e}")
            return debrief_content
    
    def _create_debrief_markdown(self, processed_data: Dict[str, Any]) -> str:
        """
        처리된 데이터로 Debrief 마크다운 생성
        
        Args:
            processed_data: 처리된 UT 데이터
            
        Returns:
            마크다운 형식의 Debrief
        """
        title = processed_data.get("title", "UT Debrief")
        date = processed_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        
        # 문서 헤더
        markdown = f"# {title} - Debrief\n\n"
        markdown += f"*일자: {date}*\n\n"
        
        # 참가자 정보
        markdown += "## 참가자\n\n"
        for participant in processed_data.get("participants", []):
            markdown += f"- {participant}\n"
        markdown += "\n"
        
        # 요약 및 주요 인사이트
        markdown += "## 주요 인사이트\n\n"
        if processed_data.get("insights"):
            for insight in processed_data.get("insights", []):
                markdown += f"- {insight}\n"
        else:
            markdown += "주요 인사이트가 추출되지 않았습니다.\n"
        markdown += "\n"
        
        # 발견된 이슈
        markdown += "## 발견된 이슈\n\n"
        if processed_data.get("issues"):
            for issue in processed_data.get("issues", []):
                markdown += f"- {issue}\n"
        else:
            markdown += "발견된 이슈가 없습니다.\n"
        markdown += "\n"
        
        # 액션 아이템
        markdown += "## 액션 아이템\n\n"
        if processed_data.get("action_items"):
            for action in processed_data.get("action_items", []):
                markdown += f"- [ ] {action}\n"
        else:
            markdown += "액션 아이템이 추출되지 않았습니다.\n"
        markdown += "\n"
        
        # 상세 내용
        markdown += "## 상세 내용\n\n"
        for section in processed_data.get("sections", []):
            markdown += f"### {section.get('title', '섹션')}\n\n"
            markdown += f"{section.get('content', '')}\n\n"
        
        return markdown 