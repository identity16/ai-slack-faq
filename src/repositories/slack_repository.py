"""
슬랙 데이터 소스 접근 모듈
"""
import os
from typing import List, Dict, Any
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackRepository:
    """
    슬랙 API를 통해 채널 및 스레드 데이터를 가져오는 Repository 클래스
    """
    
    def __init__(self):
        """슬랙 클라이언트 초기화"""
        slack_token = os.environ.get("SLACK_BOT_TOKEN")
        if not slack_token:
            raise ValueError("SLACK_BOT_TOKEN 환경 변수가 설정되지 않았습니다.")
        self.client = WebClient(token=slack_token)
    
    def get_channel_id(self, channel_name: str) -> str:
        """
        채널 이름으로 채널 ID 조회
        
        Args:
            channel_name: 채널 이름 (# 제외)
            
        Returns:
            채널 ID 또는 빈 문자열
        """
        try:
            result = self.client.conversations_list()
            for channel in result["channels"]:
                if channel["name"] == channel_name:
                    return channel["id"]
            
            # 공개 채널에서 찾지 못한 경우 비공개 채널 검색
            result = self.client.conversations_list(types="private_channel")
            for channel in result["channels"]:
                if channel["name"] == channel_name:
                    return channel["id"]
                    
            return ""
        except SlackApiError as e:
            print(f"슬랙 API 에러: {e}")
            return ""
    
    def fetch_recent_threads(self, channel_name: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        최근 N일 동안의 스레드를 가져오기
        
        Args:
            channel_name: 채널 이름 (# 제외)
            days: 검색할 일자 (기본값: 7)
            
        Returns:
            스레드 목록 (질문-답변 쌍)
        """
        channel_id = self.get_channel_id(channel_name)
        if not channel_id:
            print(f"채널을 찾을 수 없습니다: {channel_name}")
            return []
        
        # 검색 기간 설정
        oldest = (datetime.now() - timedelta(days=days)).timestamp()
        
        try:
            # 채널 내 메시지 가져오기
            threads = []
            result = self.client.conversations_history(
                channel=channel_id,
                oldest=oldest,
                limit=100
            )
            
            messages = result["messages"]
            
            # 스레드 있는 메시지 필터링
            threaded_messages = [msg for msg in messages if msg.get("thread_ts")]
            
            # 진행 상태 표시
            total = len(threaded_messages)
            print(f"총 {total}개의 스레드를 처리합니다.")
            
            # 각 스레드의 모든 답변 가져오기
            for i, msg in enumerate(threaded_messages, 1):
                thread_ts = msg.get("thread_ts")
                
                # 스레드 답변 가져오기
                try:
                    replies = self.client.conversations_replies(
                        channel=channel_id,
                        ts=thread_ts
                    )
                    
                    # 스레드가 2개 이상의 메시지를 가진 경우만 처리 (질문 + 답변)
                    if len(replies["messages"]) > 1:
                        # 원본 메시지 (질문)
                        question = replies["messages"][0]["text"]
                        
                        # 첫 번째 답변 (가장 신뢰성 높은 답변으로 가정)
                        answer = replies["messages"][1]["text"]
                        
                        # 메시지에 사용자 정보가 있는 경우, 이름으로 변환
                        if "user" in replies["messages"][0]:
                            user_id = replies["messages"][0]["user"]
                            user_info = self.client.users_info(user=user_id)
                            questioner = user_info["user"]["name"]
                        else:
                            questioner = "Unknown"
                            
                        if "user" in replies["messages"][1]:
                            user_id = replies["messages"][1]["user"]
                            user_info = self.client.users_info(user=user_id)
                            answerer = user_info["user"]["name"]
                        else:
                            answerer = "Unknown"
                        
                        # 스레드 정보 저장
                        thread_info = {
                            "channel": channel_name,
                            "question": question,
                            "answer": answer,
                            "questioner": questioner,
                            "answerer": answerer,
                            "timestamp": float(thread_ts),
                            "datetime": datetime.fromtimestamp(float(thread_ts)).strftime("%Y-%m-%d %H:%M")
                        }
                        
                        threads.append(thread_info)
                
                except SlackApiError as e:
                    print(f"스레드 {thread_ts} 가져오기 실패: {e}")
                
                # 진행 상태 업데이트
                print(f"스레드 처리 중: {i}/{total}", end="\r")
            
            print(f"\n총 {len(threads)}개의 유효한 스레드를 가져왔습니다.")
            return threads
            
        except SlackApiError as e:
            print(f"슬랙 API 에러: {e}")
            return [] 