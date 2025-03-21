"""
노션 데이터 소스 접근 모듈
"""
import os
import re
from typing import Dict, Any

class NotionRepository:
    """
    노션 API를 통해 데이터를 가져오는 Repository 클래스
    """
    
    def __init__(self):
        """노션 API 클라이언트 초기화"""
        notion_token = os.environ.get("NOTION_API_KEY")
        if not notion_token:
            raise ValueError("NOTION_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        # 노션 SDK 사용 시 아래 코드 활성화
        # from notion_client import Client
        # self.client = Client(auth=notion_token)
    
    def extract_doc_id(self, url_or_id: str) -> str:
        """
        노션 URL에서 문서 ID 추출
        
        Args:
            url_or_id: 노션 문서 URL 또는 ID
            
        Returns:
            노션 문서 ID
        """
        if "notion.so" in url_or_id:
            # URL에서 ID 추출 (UUID 형식)
            match = re.search(r"([a-f0-9]{32})", url_or_id)
            if match:
                return match.group(1)
                
            # 또는 다른 형식의 ID 추출
            match = re.search(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", url_or_id)
            if match:
                return match.group(1)
                
        return url_or_id  # 이미 ID 형태인 경우
    
    def get_ut_transcript(self, doc_id: str) -> Dict[str, Any]:
        """
        노션 UT 문서에서 녹취록 가져오기
        
        Args:
            doc_id: 노션 문서 ID 또는 URL
            
        Returns:
            녹취록 데이터
        """
        doc_id = self.extract_doc_id(doc_id)
        
        try:
            # 실제 노션 API 연동 코드로 대체 필요
            # 예시 데이터로 구현
            print(f"노션 문서 ID {doc_id}에서 UT 녹취록을 가져옵니다.")
            
            # 예시 데이터 - 실제 구현 시 노션 API 호출 결과로 대체
            transcript = {
                "title": "사용자 테스트 녹취록",
                "date": "2023-05-15",
                "participants": ["진행자: 김테스터", "참가자A: 이사용자", "참가자B: 박체험"],
                "sections": [
                    {
                        "title": "인트로 및 소개",
                        "content": "안녕하세요, 오늘은 새로운 기능에 대한 사용자 테스트를 진행하겠습니다."
                    },
                    {
                        "title": "주요 과제 1: 회원가입 프로세스",
                        "content": "참가자A: 회원가입 버튼을 찾기 어려웠어요.\n진행자: 어디를 먼저 보셨나요?\n참가자A: 오른쪽 상단을 먼저 확인했는데 없어서 헤맸습니다."
                    },
                    {
                        "title": "주요 과제 2: 상품 검색",
                        "content": "참가자B: 검색 필터가 너무 많아서 헷갈렸어요.\n진행자: 어떤 부분이 특히 어려웠나요?\n참가자B: 가격대 설정하는 부분이 직관적이지 않았습니다."
                    },
                    {
                        "title": "주요 과제 3: 결제 프로세스",
                        "content": "참가자A: 결제 방식을 선택하는 부분이 명확했어요.\n참가자B: 배송지 입력할 때 주소 검색이 편리했습니다."
                    },
                    {
                        "title": "종합 피드백",
                        "content": "참가자A: 전반적으로 사용하기 쉬웠지만, 초기 회원가입 부분이 개선되면 좋겠어요.\n참가자B: 검색 기능이 보완되면 훨씬 사용하기 좋을 것 같습니다."
                    }
                ],
                "raw_text": "전체 녹취록 원문 텍스트..."
            }
            
            return transcript
            
        except Exception as e:
            print(f"노션 문서 가져오기 실패: {e}")
            return {} 