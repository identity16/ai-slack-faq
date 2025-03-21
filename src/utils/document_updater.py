"""문서 업데이트 유틸리티"""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from openai import OpenAI

class DocumentUpdater:
    """LLM을 활용하여 문서 업데이트를 담당하는 클래스"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        DocumentUpdater 초기화
        
        Args:
            api_key: OpenAI API 키 (없으면 환경 변수에서 가져옴)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
            
        # OpenAI 클라이언트 초기화
        self.client = OpenAI(api_key=self.api_key)
    
    def update_faq_document(self, file_path: str, new_content: str) -> str:
        """
        FAQ 문서를 업데이트합니다.
        
        Args:
            file_path: 기존 파일 경로
            new_content: 새로운 문서 내용
            
        Returns:
            병합된 내용
        """
        print("기존 FAQ 문서를 새로운 내용과 병합합니다...")
        
        # 기존 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
        
        # LLM을 사용하여 문서 병합
        return self._merge_documents_with_llm(
            existing_content, 
            new_content, 
            "FAQ", 
            "어떤 질문-답변 쌍도 손실되지 않아야 하며, 중복된 질문이 있을 경우 가장 상세한 답변을 유지합니다."
        )
    
    def update_ut_document(self, file_path: str, new_content: str) -> str:
        """
        UT Debrief 문서를 업데이트합니다.
        
        Args:
            file_path: 기존 파일 경로
            new_content: 새로운 문서 내용
            
        Returns:
            병합된 내용
        """
        print("기존 UT Debrief 문서를 새로운 내용과 병합합니다...")
        
        # 기존 파일 읽기
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()
        
        # LLM을 사용하여 문서 병합
        return self._merge_documents_with_llm(
            existing_content, 
            new_content, 
            "UT Debrief", 
            "주요 인사이트와 액션 아이템을 모두 포함해야 합니다. 중복되는 내용은 통합하되 정보 손실이 없어야 합니다."
        )
    
    def _merge_documents_with_llm(self, existing_content: str, new_content: str, doc_type: str, merge_instructions: str) -> str:
        """
        LLM을 사용하여 두 문서를 병합합니다.
        
        Args:
            existing_content: 기존 문서 내용
            new_content: 새로운 문서 내용
            doc_type: 문서 유형 (예: "FAQ", "UT Debrief")
            merge_instructions: 병합 지침
            
        Returns:
            병합된 문서 내용
        """
        # 날짜 정보 추가
        now = datetime.now().strftime("%Y년 %m월 %d일")
        
        system_prompt = f"""당신은 마크다운 문서를 병합하는 전문가입니다. {doc_type} 문서의 기존 내용과 새로운 내용을 효과적으로 병합해야 합니다.

병합 시 다음 지침을 따르세요:
1. {merge_instructions}
2. 문서의 구조와 형식을 일관되게 유지하세요.
3. 중복된 내용은 통합하되, 서로 보완하는 정보는 모두 포함시키세요.
4. 최종 문서에는 마지막 업데이트 날짜({now})를 포함하세요.
5. 문서의 모든 부분을 확인하고 어떤 정보도 손실되지 않도록 하세요.
6. 최종 출력은 완전한 마크다운 문서여야 합니다.

출력은 기존 문서와 새 문서의 내용을 잘 통합한 완전한 마크다운 형식이어야 합니다."""

        user_prompt = f"""여기 두 개의 {doc_type} 문서가 있습니다. 이 두 문서를 병합하여 하나의 포괄적인 문서를 만들어주세요.

# 기존 문서:
```markdown
{existing_content}
```

# 새 문서:
```markdown
{new_content}
```

위 두 문서의 내용을 병합한 완전한 마크다운 문서를 작성해주세요. 모든 중요한 정보가 포함되고, 구조적으로 일관되게 만들어 주세요."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # 높은 품질의 병합을 위해 최신 모델 사용
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,  # 일관된 출력을 위해 낮은 온도 설정
                max_tokens=4000  # 충분한 토큰 할당
            )
            
            merged_content = response.choices[0].message.content
            
            # 마크다운 코드 블록이 있을 경우 제거
            if merged_content.startswith("```markdown") and merged_content.endswith("```"):
                merged_content = merged_content[12:-3].strip()
            elif merged_content.startswith("```") and merged_content.endswith("```"):
                merged_content = merged_content[3:-3].strip()
                
            return merged_content
            
        except Exception as e:
            print(f"문서 병합 중 오류 발생: {str(e)}")
            print("기본 병합 방식을 사용합니다...")
            return self._fallback_merge(existing_content, new_content, now)
    
    def _fallback_merge(self, existing_content: str, new_content: str, date: str) -> str:
        """
        LLM 병합에 실패했을 때 사용하는 기본 병합 방법
        
        Args:
            existing_content: 기존 문서 내용
            new_content: 새로운 문서 내용
            date: 업데이트 날짜
            
        Returns:
            병합된 문서 내용
        """
        # 제목 추출
        title_match = existing_content.split('\n', 1)[0]
        
        # 간단한 병합 (기존 문서 + 업데이트 정보 + 새 문서)
        merged_content = f"{title_match}\n\n*마지막 업데이트: {date}*\n\n"
        merged_content += "## 기존 내용\n\n"
        merged_content += existing_content.split('\n', 1)[1].strip()
        merged_content += "\n\n## 추가된 내용\n\n"
        merged_content += new_content.split('\n', 1)[1].strip()
        
        return merged_content 