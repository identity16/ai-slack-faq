"""
Slack Raw Data Collector

슬랙 채널에서 대화 데이터를 수집하는 모듈입니다.
"""

import os
from typing import List, Dict, Any
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import asyncio
from functools import partial

class SlackCollector:
    """
    슬랙 API를 통해 채널 및 스레드 데이터를 수집하는 Collector 클래스
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        슬랙 클라이언트 초기화
        
        Args:
            config: 설정 정보 (옵션)
        """
        slack_token = config.get("slack_token") if config else os.environ.get("SLACK_BOT_TOKEN")
        if not slack_token:
            raise ValueError("Slack 토큰이 설정되지 않았습니다.")
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
            # 채널 이름에서 '#' 제거
            channel_name = channel_name.lstrip('#')
            print(f"채널 '{channel_name}' 검색 중...")
            
            # 공개 채널 검색
            cursor = None
            while True:
                result = self.client.conversations_list(
                    types="public_channel",
                    cursor=cursor,
                    limit=1000
                )
                for channel in result["channels"]:
                    if channel["name"] == channel_name:
                        print(f"공개 채널 '{channel_name}' (ID: {channel['id']})를 찾았습니다.")
                        return channel["id"]
                
                cursor = result.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            
            # 비공개 채널 검색
            cursor = None
            while True:
                result = self.client.conversations_list(
                    types="private_channel",
                    cursor=cursor,
                    limit=1000
                )
                for channel in result["channels"]:
                    if channel["name"] == channel_name:
                        print(f"비공개 채널 '{channel_name}' (ID: {channel['id']})를 찾았습니다.")
                        return channel["id"]
                
                cursor = result.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            
            print(f"채널 '{channel_name}'을(를) 찾을 수 없습니다.")
            print("가능한 원인:")
            print("1. 채널 이름이 잘못되었습니다.")
            print("2. 봇이 해당 채널에 초대되지 않았습니다.")
            print("3. 봇이 해당 채널을 볼 수 있는 권한이 없습니다.")
            return ""
            
        except SlackApiError as e:
            error_message = str(e)
            print(f"채널 ID 조회 중 에러 발생: {error_message}")
            if "not_authed" in error_message:
                print("Slack 토큰이 유효하지 않습니다.")
            elif "invalid_auth" in error_message:
                print("Slack 토큰이 만료되었거나 권한이 없습니다.")
            elif "channel_not_found" in error_message:
                print("채널을 찾을 수 없습니다. 채널 이름을 확인해주세요.")
            return ""

    async def _run_sync(self, func, *args, **kwargs):
        """
        동기 함수를 비동기적으로 실행
        
        Args:
            func: 실행할 함수
            *args: 함수 인자
            **kwargs: 함수 키워드 인자
            
        Returns:
            함수 실행 결과
        """
        loop = asyncio.get_event_loop()
        try:
            print(f"[DEBUG] _run_sync 시작: {func.__name__}, 인자: {args}, 키워드 인자: {kwargs}")
            # 타임아웃 60초 설정
            result = await asyncio.wait_for(
                loop.run_in_executor(None, partial(func, *args, **kwargs)),
                timeout=60.0
            )
            print(f"[DEBUG] _run_sync 완료: {func.__name__}")
            return result
        except asyncio.TimeoutError:
            print(f"[ERROR] _run_sync 타임아웃 (60초): {func.__name__}, 인자: {args}, 키워드 인자: {kwargs}")
            raise TimeoutError(f"{func.__name__} 함수 실행 시간이 초과되었습니다 (60초). 네트워크 연결을 확인하거나 Slack API 응답 시간을 확인하세요.")
        except Exception as e:
            print(f"[ERROR] _run_sync 예외 발생: {func.__name__}, 오류: {str(e)}")
            import traceback
            print(traceback.format_exc())
            raise

    async def collect(self, channel_name: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        최근 N일 동안의 스레드 데이터 수집
        
        Args:
            channel_name: 채널 이름 (# 제외)
            days: 검색할 일자 (기본값: 7)
            
        Returns:
            수집된 스레드 목록
        """
        try:
            print(f"[DEBUG] SlackCollector.collect 시작: 채널={channel_name}, 기간={days}일")
            channel_id = await self._run_sync(self.get_channel_id, channel_name)
            if not channel_id:
                print(f"채널을 찾을 수 없습니다: {channel_name}")
                return []
            
            # 검색 기간 설정
            oldest = (datetime.now() - timedelta(days=days)).timestamp()
            print(f"[DEBUG] 검색 기간 설정: {datetime.fromtimestamp(oldest).strftime('%Y-%m-%d')}부터")
            
            try:
                # 채널 내 메시지 가져오기
                print("[DEBUG] 채널 메시지 가져오기 시작")
                threads = []
                result = await self._run_sync(
                    self.client.conversations_history,
                    channel=channel_id,
                    oldest=oldest,
                    limit=100
                )
                print(f"[DEBUG] conversations_history API 호출 완료")
                
                messages = result["messages"]
                threaded_messages = [msg for msg in messages if msg.get("thread_ts")]
                
                print(f"총 {len(threaded_messages)}개의 스레드를 처리합니다.")
                
                # 각 스레드의 답변 수집
                for i, msg in enumerate(threaded_messages, 1):
                    thread_ts = msg.get("thread_ts")
                    print(f"[DEBUG] 스레드 처리 {i}/{len(threaded_messages)}: {thread_ts}")
                    
                    try:
                        print(f"[DEBUG] conversations_replies API 호출 시작: {thread_ts}")
                        replies = await self._run_sync(
                            self.client.conversations_replies,
                            channel=channel_id,
                            ts=thread_ts
                        )
                        print(f"[DEBUG] conversations_replies API 호출 완료: {len(replies['messages'])} 메시지")
                        
                        if len(replies["messages"]) > 1:
                            print(f"[DEBUG] 스레드 처리 시작: {thread_ts}")
                            thread_info = await self._run_sync(
                                self._process_thread,
                                channel_name=channel_name,
                                messages=replies["messages"],
                                thread_ts=thread_ts
                            )
                            threads.append(thread_info)
                            print(f"[DEBUG] 스레드 처리 완료: {thread_ts}")
                    
                    except SlackApiError as e:
                        print(f"스레드 {thread_ts} 가져오기 실패: {e}")
                    
                    print(f"스레드 처리 중: {i}/{len(threaded_messages)}", end="\r")
                
                print(f"\n총 {len(threads)}개의 유효한 스레드를 수집했습니다.")
                print(f"[DEBUG] SlackCollector.collect 완료")
                return threads
                
            except SlackApiError as e:
                print(f"Slack API 에러: {e}")
                return []
        except Exception as e:
            print(f"예기치 않은 에러 발생: {e}")
            import traceback
            print(traceback.format_exc())
            return []

    def _process_thread(self, channel_name: str, messages: List[Dict], thread_ts: str) -> Dict[str, Any]:
        """
        스레드 메시지를 처리하여 구조화된 데이터로 변환
        
        Args:
            channel_name: 채널 이름
            messages: 스레드 메시지 목록
            thread_ts: 스레드 타임스탬프
            
        Returns:
            구조화된 스레드 정보
        """
        # 원본 메시지 (질문)
        question = messages[0]["text"]
        answer = messages[1]["text"]
        
        # 사용자 정보 조회
        questioner = self._get_username(messages[0].get("user", "Unknown"))
        answerer = self._get_username(messages[1].get("user", "Unknown"))
        
        return {
            "channel": channel_name,
            "question": question,
            "answer": answer,
            "questioner": questioner,
            "answerer": answerer,
            "timestamp": float(thread_ts),
            "datetime": datetime.fromtimestamp(float(thread_ts)).strftime("%Y-%m-%d %H:%M"),
            "type": "slack_thread"
        }
    
    def _get_username(self, user_id: str) -> str:
        """
        사용자 ID로 사용자 이름 조회
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            사용자 이름
        """
        if user_id == "Unknown":
            return "Unknown"
            
        try:
            user_info = self.client.users_info(user=user_id)
            return user_info["user"]["name"]
        except SlackApiError:
            return "Unknown" 