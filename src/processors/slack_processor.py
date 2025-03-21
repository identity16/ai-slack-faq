"""
슬랙 데이터 처리 모듈 - 원본 슬랙 데이터 정제/분류/분석
"""
import os
from typing import List, Dict, Any
from datetime import datetime
from .data_store import DataStore

class SlackProcessor:
    """
    슬랙 데이터를 처리하는 클래스
    """
    
    def __init__(self):
        """처리기 초기화"""
        # OpenAI API 키 설정
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
            
        # 데이터 저장소 초기화
        self.data_store = DataStore()
    
    def process_threads(self, threads: List[Dict[str, Any]]) -> str:
        """
        슬랙 스레드 처리 및 FAQ 생성
        
        Args:
            threads: 슬랙 스레드 목록
            
        Returns:
            생성된 FAQ 마크다운
        """
        if not threads:
            return "처리할 스레드가 없습니다."
        
        # 스레드 데이터 처리/정제
        processed_threads = self._process_thread_data(threads)
        
        # 처리된 데이터 저장
        if processed_threads and "channel" in processed_threads[0]:
            channel = processed_threads[0]["channel"]
            self.data_store.save_processed_slack_data(channel, processed_threads)
        
        # FAQ 생성
        faq_markdown = self._generate_faq_content(processed_threads)
        
        return faq_markdown
    
    def _process_thread_data(self, threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        스레드 데이터 처리 및 정제
        
        Args:
            threads: 원본 스레드 목록
            
        Returns:
            정제된 스레드 목록
        """
        processed_data = []
        
        for thread in threads:
            # 불필요한 포맷팅/마크업 제거
            question = self._clean_message_text(thread.get("question", ""))
            answer = self._clean_message_text(thread.get("answer", ""))
            
            # 유효한 Q&A 쌍만 포함
            if not question or not answer:
                continue
            
            # 질문 유형 분류 (주제 태그 추가)
            tags = self._classify_question(question)
            
            # 처리된 데이터 저장
            processed_thread = {
                "channel": thread.get("channel", ""),
                "question": question,
                "answer": answer,
                "questioner": thread.get("questioner", "Unknown"),
                "answerer": thread.get("answerer", "Unknown"),
                "datetime": thread.get("datetime", ""),
                "tags": tags
            }
            
            processed_data.append(processed_thread)
        
        return processed_data
    
    def _clean_message_text(self, text: str) -> str:
        """
        메시지 텍스트 정제
        
        Args:
            text: 원본 텍스트
            
        Returns:
            정제된 텍스트
        """
        # 특수 문자 및 HTML 태그 정리
        # 실제 정제 로직 구현 필요
        return text.strip()
    
    def _classify_question(self, question: str) -> List[str]:
        """
        질문 내용 분류 및 태그 생성
        
        Args:
            question: 질문 내용
            
        Returns:
            주제 태그 목록
        """
        # 실제로는 AI 모델을 사용하여 질문 유형 분류
        # 예시 구현
        tags = []
        
        # 간단한 키워드 기반 분류 예시
        keywords = {
            "설치": ["설치", "인스톨", "다운로드"],
            "오류": ["에러", "오류", "문제", "안됨"],
            "기능": ["기능", "사용법", "어떻게"],
            "계정": ["계정", "로그인", "가입"]
        }
        
        for category, words in keywords.items():
            if any(word in question for word in words):
                tags.append(category)
        
        # 태그가 없으면 기본 태그 추가
        if not tags:
            tags.append("기타")
            
        return tags
    
    def _generate_faq_content(self, processed_threads: List[Dict[str, Any]]) -> str:
        """
        처리된 스레드로 FAQ 마크다운 생성
        
        Args:
            processed_threads: 처리된 스레드 목록
            
        Returns:
            FAQ 마크다운 텍스트
        """
        if not processed_threads:
            return "# FAQ\n\n처리된 데이터가 없습니다."
            
        # 채널 정보 가져오기
        channel = processed_threads[0].get("channel", "일반")
        
        # 태그별로 질문 그룹화
        tagged_questions = {}
        for thread in processed_threads:
            for tag in thread.get("tags", ["기타"]):
                if tag not in tagged_questions:
                    tagged_questions[tag] = []
                tagged_questions[tag].append(thread)
        
        # 마크다운 생성
        now = datetime.now().strftime("%Y-%m-%d")
        
        markdown = f"# {channel} 채널 FAQ\n\n"
        markdown += f"*생성일: {now}*\n\n"
        markdown += "## 목차\n\n"
        
        # 목차 생성
        for tag in sorted(tagged_questions.keys()):
            markdown += f"- [{tag}](#{tag.lower()})\n"
        
        markdown += "\n"
        
        # 카테고리별 FAQ 내용 생성
        for tag in sorted(tagged_questions.keys()):
            markdown += f"## {tag}\n\n"
            
            for i, thread in enumerate(tagged_questions[tag], 1):
                markdown += f"### Q{i}: {thread['question']}\n\n"
                markdown += f"{thread['answer']}\n\n"
                if "answerer" in thread and thread["answerer"] != "Unknown":
                    markdown += f"*답변자: {thread['answerer']}*\n\n"
        
        return markdown 