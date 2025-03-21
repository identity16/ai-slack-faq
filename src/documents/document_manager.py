"""
문서 관리 모듈 - 문서 업데이트, 병합 등 관리 기능
"""
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

class DocumentManager:
    """
    문서 관리 클래스
    """
    
    def __init__(self):
        """문서 관리자 초기화"""
        # OpenAI API 키 설정
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        # 문서 저장 디렉토리
        self.documents_dir = Path("results")
        os.makedirs(self.documents_dir, exist_ok=True)
    
    def update_faq_document(self, existing_file: str, new_content: str) -> str:
        """
        기존 FAQ 문서 업데이트
        
        Args:
            existing_file: 기존 문서 파일 경로
            new_content: 새로운 문서 내용
            
        Returns:
            병합된 문서 내용
        """
        try:
            # 기존 문서 읽기
            with open(existing_file, "r", encoding="utf-8") as f:
                existing_content = f.read()
            
            # 문서 병합 (LLM 사용)
            merged_content = self._merge_documents_with_llm(
                existing_content, 
                new_content, 
                "FAQ 문서"
            )
            
            # 생성 날짜 업데이트
            today = datetime.now().strftime("%Y-%m-%d")
            if "*생성일:" in merged_content:
                merged_content = merged_content.replace(
                    "*생성일:", 
                    f"*생성일: {today}, 최종 업데이트:"
                )
            elif "*최종 업데이트:" in merged_content:
                # 이미 업데이트된 문서인 경우, 날짜만 변경
                merged_content = merged_content.replace(
                    "*최종 업데이트:", 
                    f"*최종 업데이트: {today},"
                )
            
            return merged_content
            
        except Exception as e:
            print(f"문서 업데이트 중 오류 발생: {e}")
            return new_content
    
    def update_ut_document(self, existing_file: str, new_content: str) -> str:
        """
        기존 UT Debrief 문서 업데이트
        
        Args:
            existing_file: 기존 문서 파일 경로
            new_content: 새로운 문서 내용
            
        Returns:
            병합된 문서 내용
        """
        try:
            # 기존 문서 읽기
            with open(existing_file, "r", encoding="utf-8") as f:
                existing_content = f.read()
            
            # 문서 병합 (LLM 사용)
            merged_content = self._merge_documents_with_llm(
                existing_content, 
                new_content, 
                "UT Debrief 문서"
            )
            
            # 업데이트 날짜 추가
            today = datetime.now().strftime("%Y-%m-%d")
            if "*일자:" in merged_content:
                merged_content = merged_content.replace(
                    "*일자:", 
                    f"*일자: {today}, 최종 업데이트:"
                )
            elif "*최종 업데이트:" in merged_content:
                # 이미 업데이트된 문서인 경우, 날짜만 변경
                merged_content = merged_content.replace(
                    "*최종 업데이트:", 
                    f"*최종 업데이트: {today},"
                )
            
            return merged_content
            
        except Exception as e:
            print(f"문서 업데이트 중 오류 발생: {e}")
            return new_content
    
    def _merge_documents_with_llm(self, existing_content: str, new_content: str, doc_type: str = "문서") -> str:
        """
        LLM을 사용하여 두 문서 내용 병합
        
        Args:
            existing_content: 기존 문서 내용
            new_content: 새로운 문서 내용
            doc_type: 문서 유형
            
        Returns:
            병합된 문서 내용
        """
        # 실제 구현에서는 OpenAI API 호출
        print(f"LLM을 사용하여 {doc_type}를 병합합니다.")
        
        # 프롬프트 작성
        prompt = f"""
두 개의 마크다운 {doc_type}를 하나로 병합해주세요.
기존 문서의 구조를 유지하면서 새로운 내용을 적절히 통합해야 합니다.
중복되는 내용은 제거하고, 상충되는 정보가 있으면 최신 문서의 정보를 우선적으로 사용하세요.

기존 문서:
```
{existing_content}
```

새로운 문서:
```
{new_content}
```

병합된 문서를 마크다운 형식으로 제공해주세요. 메타데이터(제목, 날짜 등)는 최신 정보로 업데이트하되,
문서의 내용적 가치를 최대한 보존하는 것이 중요합니다.
"""
        
        try:
            # OpenAI API 호출 (실제 구현에서 활성화)
            # response = openai.chat.completions.create(
            #     model="gpt-4o",
            #     messages=[
            #         {"role": "system", "content": "당신은 마크다운 문서를 효과적으로 병합하는 전문가입니다."},
            #         {"role": "user", "content": prompt}
            #     ],
            #     temperature=0.3,
            #     max_tokens=4000
            # )
            # 
            # return response.choices[0].message.content
            
            # 임시 구현 (실제 통합 시에는 제거)
            return self._simulate_merge(existing_content, new_content)
            
        except Exception as e:
            print(f"LLM을 사용한 문서 병합 중 오류 발생: {e}")
            # 오류 시 새 문서 반환
            return new_content
    
    def _simulate_merge(self, existing_content: str, new_content: str) -> str:
        """실제 LLM 호출 없이 병합 시뮬레이션 (개발용)"""
        # 실제 구현에서는 삭제됨
        # 간단한 병합 예시 (헤더 유지 + 내용 붙이기)
        lines = existing_content.split('\n')
        header_end = 0
        
        # 헤더 찾기 (첫 번째 # 아닌 줄까지)
        for i, line in enumerate(lines):
            if line.startswith('#'):
                header_end = i + 1
        
        # 헤더와 새 내용 결합
        if header_end > 0:
            merged = '\n'.join(lines[:header_end]) + '\n\n## 업데이트된 내용\n\n' + new_content
        else:
            merged = new_content
            
        return merged
    
    def list_documents(self, doc_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        문서 목록 조회
        
        Args:
            doc_type: 문서 유형 필터 ('faq', 'ut', None=전체)
            
        Returns:
            문서 목록 (메타데이터 포함)
        """
        documents = []
        
        # 문서 유형에 따른 파일 패턴
        if doc_type == 'faq':
            pattern = 'faq_*.md'
        elif doc_type == 'ut':
            pattern = 'ut_*.md'
        else:
            pattern = '*.md'
        
        # 문서 검색
        for file_path in self.documents_dir.glob(pattern):
            modified_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            size_kb = file_path.stat().st_size / 1024
            
            # 문서 메타데이터 추출
            title = file_path.stem
            doc_info = {
                "filename": file_path.name,
                "title": title,
                "modified": modified_time.strftime("%Y-%m-%d %H:%M:%S"),
                "size_kb": f"{size_kb:.1f}",
                "path": str(file_path)
            }
            
            documents.append(doc_info)
        
        # 수정일 기준 정렬
        documents.sort(key=lambda x: x["modified"], reverse=True)
        
        return documents
    
    def get_document_content(self, filename: str) -> str:
        """
        문서 내용 조회
        
        Args:
            filename: 문서 파일명
            
        Returns:
            문서 내용
        """
        file_path = self.documents_dir / filename
        
        if not file_path.exists():
            return f"문서를 찾을 수 없습니다: {filename}"
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"문서 읽기 오류: {e}"
    
    def delete_document(self, filename: str) -> bool:
        """
        문서 삭제
        
        Args:
            filename: 문서 파일명
            
        Returns:
            삭제 성공 여부
        """
        file_path = self.documents_dir / filename
        
        if not file_path.exists():
            return False
        
        try:
            file_path.unlink()
            return True
        except Exception as e:
            print(f"문서 삭제 오류: {e}")
            return False 