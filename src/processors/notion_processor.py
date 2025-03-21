"""
노션 데이터 처리 모듈 - 원본 노션 데이터 정제/분류/분석
"""
import os
from typing import Dict, Any, List
from datetime import datetime
from .data_store import DataStore

class NotionProcessor:
    """
    노션 데이터를 처리하는 클래스
    """
    
    def __init__(self):
        """처리기 초기화"""
        # OpenAI API 키 설정
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
            
        # 데이터 저장소 초기화
        self.data_store = DataStore()
    
    def process_transcript(self, transcript: Dict[str, Any]) -> str:
        """
        노션 UT 녹취록 처리 및 Debrief 생성
        
        Args:
            transcript: 녹취록 데이터
            
        Returns:
            생성된 Debrief 마크다운
        """
        if not transcript:
            return "처리할 녹취록이 없습니다."
        
        # 녹취록 데이터 처리/정제
        processed_data = self._process_transcript_data(transcript)
        
        # 처리된 데이터 저장
        doc_id = "unknown"  # 실제 구현에서는 transcript에서 doc_id 추출
        self.data_store.save_processed_notion_data(doc_id, processed_data)
        
        # Debrief 생성
        debrief_markdown = self._generate_debrief_content(processed_data)
        
        return debrief_markdown
    
    def _process_transcript_data(self, transcript: Dict[str, Any]) -> Dict[str, Any]:
        """
        녹취록 데이터 처리 및 정제
        
        Args:
            transcript: 원본 녹취록 데이터
            
        Returns:
            정제된 녹취록 데이터
        """
        # 데이터 구조화 및 정제
        processed_data = {
            "title": transcript.get("title", "UT 녹취록"),
            "date": transcript.get("date", datetime.now().strftime("%Y-%m-%d")),
            "participants": transcript.get("participants", []),
            "sections": [],
            "insights": [],
            "issues": [],
            "action_items": []
        }
        
        # 섹션 처리
        for section in transcript.get("sections", []):
            section_title = section.get("title", "")
            section_content = section.get("content", "")
            
            # 섹션 저장
            processed_data["sections"].append({
                "title": section_title,
                "content": self._clean_transcript_text(section_content)
            })
            
            # 섹션 내용 분석
            insights = self._extract_insights(section_content)
            issues = self._extract_issues(section_content)
            actions = self._extract_action_items(section_content)
            
            processed_data["insights"].extend(insights)
            processed_data["issues"].extend(issues)
            processed_data["action_items"].extend(actions)
        
        return processed_data
    
    def _clean_transcript_text(self, text: str) -> str:
        """
        녹취록 텍스트 정제
        
        Args:
            text: 원본 텍스트
            
        Returns:
            정제된 텍스트
        """
        # 실제 정제 로직 구현 필요
        return text.strip()
    
    def _extract_insights(self, text: str) -> List[str]:
        """
        텍스트에서 인사이트 추출
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            추출된 인사이트 목록
        """
        # 실제 구현에서는 AI 모델을 사용하여 인사이트 추출
        # 간단한 예시 구현
        insights = []
        
        # 키워드 기반 간단한 분석 (실제로는 NLP 모델 사용)
        if "어려웠" in text or "불편" in text:
            insights.append("사용자가 불편을 겪는 부분이 있음")
        
        if "좋았" in text or "편리" in text:
            insights.append("사용자가 긍정적으로 평가한 부분 있음")
            
        return insights
    
    def _extract_issues(self, text: str) -> List[str]:
        """
        텍스트에서 이슈 추출
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            추출된 이슈 목록
        """
        # 실제 구현에서는 AI 모델을 사용하여 이슈 추출
        issues = []
        
        if "문제" in text or "오류" in text:
            issues.append("사용자가 오류/문제를 경험함")
            
        return issues
    
    def _extract_action_items(self, text: str) -> List[str]:
        """
        텍스트에서 액션 아이템 추출
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            추출된 액션 아이템 목록
        """
        # 실제 구현에서는 AI 모델을 사용하여 액션 아이템 추출
        actions = []
        
        if "개선" in text or "수정" in text:
            actions.append("개선 필요 사항 확인")
            
        return actions
    
    def _generate_debrief_content(self, processed_data: Dict[str, Any]) -> str:
        """
        처리된 데이터로 Debrief 마크다운 생성
        
        Args:
            processed_data: 처리된 녹취록 데이터
            
        Returns:
            Debrief 마크다운 텍스트
        """
        title = processed_data.get("title", "UT Debrief")
        date = processed_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        
        markdown = f"# {title} - Debrief\n\n"
        markdown += f"*일자: {date}*\n\n"
        
        # 참가자 정보
        markdown += "## 참가자\n\n"
        for participant in processed_data.get("participants", []):
            markdown += f"- {participant}\n"
        markdown += "\n"
        
        # 주요 인사이트
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