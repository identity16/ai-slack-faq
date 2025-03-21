import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from tqdm import tqdm
import ssl
import certifi

class SlackFetcher:
    """슬랙 API를 통해 스레드 데이터를 가져오는 클래스"""
    
    def __init__(self, token: Optional[str] = None):
        """
        SlackFetcher 초기화
        
        Args:
            token: 슬랙 봇 토큰 (없으면 환경 변수에서 가져옴)
        """
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        if not self.token:
            raise ValueError("SLACK_BOT_TOKEN not found in environment variables")
            
        # SSL 설정
        ssl._create_default_https_context = ssl._create_unverified_context
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        # 슬랙 클라이언트 초기화
        self.client = WebClient(token=self.token)
    
    def get_channel_id(self, channel_name: str) -> Optional[str]:
        """채널 이름으로 채널 ID 가져오기"""
        try:
            # 페이지네이션을 위한 변수 초기화
            all_channels = []
            cursor = None
            
            while True:
                # 다음 페이지의 채널 가져오기
                if cursor:
                    result = self.client.conversations_list(cursor=cursor, limit=1000)
                else:
                    result = self.client.conversations_list(limit=1000)
                
                all_channels.extend(result["channels"])
                
                # 더 가져올 채널이 있는지 확인
                cursor = result.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            
            # 전체 리스트에서 채널 검색
            for channel in all_channels:
                if channel["name"] == channel_name:
                    return channel["id"]
                    
            print(f"채널 '{channel_name}'을 접근 가능한 채널 목록에서 찾을 수 없습니다.")
        except SlackApiError as e:
            print(f"Slack API 오류: {e.response['error']}")
        return None
    
    def get_conversation_history(
        self,
        channel_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """특정 기간의 대화 이력 가져오기"""
        messages = []
        try:
            result = self.client.conversations_history(
                channel=channel_id,
                oldest=start_time.timestamp(),
                latest=end_time.timestamp(),
                limit=1000
            )
            messages.extend(result["messages"])
            
            # 페이지네이션 처리
            while result.get("has_more", False):
                cursor = result.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
                    
                result = self.client.conversations_history(
                    channel=channel_id,
                    oldest=start_time.timestamp(),
                    latest=end_time.timestamp(),
                    cursor=cursor,
                    limit=1000
                )
                messages.extend(result["messages"])
                
        except SlackApiError as e:
            print(f"오류: {e}")
        
        return messages
    
    def get_thread_replies(self, channel_id: str, thread_ts: str) -> List[Dict]:
        """스레드의 모든 답글 가져오기"""
        try:
            result = self.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts
            )
            return result["messages"]
        except SlackApiError as e:
            print(f"오류: {e}")
            return []
    
    def fetch_recent_threads(self, channel_name: str, days: int) -> List[Tuple[str, str, str]]:
        """
        최근 N일간의 스레드를 가져와 질문-답변 형태로 변환
        
        Args:
            channel_name: 채널 이름
            days: 검색할 기간(일)
            
        Returns:
            [(질문, 답변, 출처 링크)] 형태의 리스트
        """
        # 채널 ID 가져오기
        channel_id = self.get_channel_id(channel_name)
        if not channel_id:
            print(f"채널 '{channel_name}'을 찾을 수 없습니다.")
            return []
        
        # 기간 설정
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        print(f"채널: {channel_name}")
        print(f"기간: {start_time.strftime('%Y-%m-%d')} ~ {end_time.strftime('%Y-%m-%d')}")
        
        # 대화 이력 가져오기
        messages = self.get_conversation_history(channel_id, start_time, end_time)
        print(f"총 {len(messages)}개의 메시지를 찾았습니다.")
        
        # 스레드만 필터링
        threaded_messages = [msg for msg in messages if msg.get("thread_ts") and msg.get("thread_ts") == msg.get("ts")]
        print(f"총 {len(threaded_messages)}개의 스레드를 찾았습니다.")
        
        results = []
        
        # 각 스레드의 응답 분석
        for msg in tqdm(threaded_messages, desc="스레드 분석 중"):
            thread_ts = msg.get("ts")
            
            # 스레드의 모든 답글 가져오기
            thread_replies = self.get_thread_replies(channel_id, thread_ts)
            
            if len(thread_replies) <= 1:
                # 답글이 없는 스레드는 건너뛰기
                continue
            
            # 첫 메시지는 질문으로 간주
            question = thread_replies[0].get("text", "").strip()
            
            # 나머지 메시지는 답변으로 간주
            answer = "\n".join([reply.get("text", "") for reply in thread_replies[1:]])
            
            # 스레드 링크 생성
            thread_link = f"https://slack.com/archives/{channel_id}/p{thread_ts.replace('.', '')}"
            
            # 질문과 답변이 모두 있는 경우만 추가
            if question and answer:
                results.append((question, answer, thread_link))
        
        print(f"총 {len(results)}개의 질문-답변 쌍을 추출했습니다.")
        return results