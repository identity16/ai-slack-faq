import os
import json
import re
from typing import Dict, Any, Optional
from openai import OpenAI

class UTDebriefPrompt:
    """UT 녹취록을 분석하여 Debrief 문서를 생성하는 프롬프트 클래스"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        UTDebriefPrompt 초기화
        
        Args:
            api_key: OpenAI API 키 (없으면 환경 변수에서 가져옴)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
            
        # OpenAI 클라이언트 초기화
        self.client = OpenAI(api_key=self.api_key)
    
    def analyze_transcript(self, transcript: str) -> Dict[str, Any]:
        """
        UT 녹취록 분석
        
        Args:
            transcript: UT 녹취록 텍스트
            
        Returns:
            분석 결과 데이터
        """
        if not transcript:
            return {}
            
        try:
            # 녹취록 분석
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """당신은 사용자 테스트(UT) 녹취록을 분석하는 AI입니다.

당신의 임무는:
1. 주요 논의 주제를 식별하고 요약
2. 핵심 인사이트와 문제점 추출
3. 필요한 액션 아이템 도출
4. 참가자와 역할 식별
5. 후속 조치 및 일정 추출
6. JSON 형식으로 결과 포맷팅
7. 반드시 유효한 JSON 형식으로 응답할 것

출력 형식:
{
    "meeting_overview": "회의에 대한 간략한 요약",
    "discussion_topics": [
        {
            "topic": "논의 주제 1",
            "summary": "이 주제에 대한 논의 요약",
            "key_points": ["주요 포인트 1", "주요 포인트 2"]
        }
    ],
    "key_insights": [
        "주요 인사이트 1",
        "주요 인사이트 2"
    ],
    "action_items": [
        {
            "action": "해야 할 일",
            "owner": "담당자/팀",
            "due_date": "날짜 또는 '다음 회의 전까지' 등의 타임라인"
        }
    ],
    "participants": [
        {
            "name": "참가자 이름",
            "role": "역할 또는 책임"
        }
    ],
    "next_steps": [
        "다음 단계 1",
        "다음 단계 2"
    ],
    "follow_up_meetings": [
        {
            "purpose": "회의 목적",
            "proposed_date": "제안된 날짜"
        }
    ]
}"""},
                    {"role": "user", "content": f"다음 UT 녹취록을 분석하여 주요 논의 사항, 인사이트, 액션 아이템 등을 추출해주세요. 반드시 유효한 JSON 형식으로 응답해주세요:\n\n{transcript}"}
                ],
                temperature=0.3
            )
            
            result = response.choices[0].message.content
            
            try:
                # JSON 문자열 추출 및 파싱
                json_str = self._extract_json_string(result)
                print(f"분석 결과 JSON 추출: {json_str[:100]}...")
                
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"분석 결과를 JSON으로 파싱하는 데 실패했습니다: {str(e)}")
                print(f"원본 응답: {result[:200]}...")
                return self._create_default_analysis(transcript)
                
        except Exception as e:
            print(f"녹취록 분석 중 오류 발생: {str(e)}")
            return self._create_default_analysis(transcript)
    
    def _extract_json_string(self, text: str) -> str:
        """텍스트에서 JSON 문자열 추출"""
        # JSON 블록 추출 시도
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)
            
        # 중괄호 안의 내용 추출 시도
        braces_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if braces_match:
            return braces_match.group(1)
        
        # 추출 실패시 원본 반환
        return text
    
    def _create_default_analysis(self, transcript: str) -> Dict[str, Any]:
        """기본 분석 결과 생성 (파싱 실패 시 대체용)"""
        # 트랜스크립트의 처음 200자로 간단한 개요 생성
        overview = transcript[:200] + "..." if len(transcript) > 200 else transcript
        
        return {
            "meeting_overview": f"UT 회의 녹취록 분석 (JSON 파싱 오류로 인한 기본 분석)",
            "discussion_topics": [
                {
                    "topic": "회의 내용",
                    "summary": "상세 분석을 위해서는, 녹취록을 다시 확인해주세요.",
                    "key_points": ["자동 분석 중 오류가 발생했습니다."]
                }
            ],
            "key_insights": [
                "자동 분석에 실패하여 인사이트를 추출하지 못했습니다."
            ],
            "action_items": [
                {
                    "action": "녹취록 다시 분석하기",
                    "owner": "팀",
                    "due_date": "가능한 빨리"
                }
            ],
            "participants": [],
            "next_steps": ["녹취록 재분석"],
            "follow_up_meetings": []
        }
    
    def generate_debrief(self, transcript: str) -> str:
        """
        녹취록에서 Debrief 마크다운 생성
        
        Args:
            transcript: UT 녹취록 텍스트
            
        Returns:
            Debrief 마크다운 텍스트
        """
        # 녹취록 분석
        analysis_data = self.analyze_transcript(transcript)
        
        if not analysis_data:
            return "# UT Debrief\n\n녹취록 분석 중 오류가 발생했습니다."
        
        # 마크다운으로 변환
        return self.convert_to_markdown(analysis_data)
    
    def convert_to_markdown(self, analysis_data: Dict[str, Any]) -> str:
        """
        분석 데이터를 마크다운 형식으로 변환
        
        Args:
            analysis_data: 분석 결과 데이터
            
        Returns:
            마크다운 텍스트
        """
        markdown = "# UT Debrief 요약\n\n"
        
        # 회의 개요
        meeting_overview = analysis_data.get("meeting_overview", "")
        if meeting_overview:
            markdown += f"{meeting_overview}\n\n"
        
        # 논의 주제
        discussion_topics = analysis_data.get("discussion_topics", [])
        if discussion_topics:
            markdown += "## 논의 주제\n\n"
            for i, topic in enumerate(discussion_topics, 1):
                topic_name = topic.get("topic", "")
                summary = topic.get("summary", "")
                key_points = topic.get("key_points", [])
                
                markdown += f"### {i}. {topic_name}\n\n"
                if summary:
                    markdown += f"{summary}\n\n"
                
                if key_points:
                    markdown += "주요 포인트:\n"
                    for point in key_points:
                        markdown += f"- {point}\n"
                    markdown += "\n"
        
        # 주요 인사이트
        key_insights = analysis_data.get("key_insights", [])
        if key_insights:
            markdown += "## 주요 인사이트\n\n"
            for insight in key_insights:
                markdown += f"- {insight}\n"
            markdown += "\n"
        
        # 액션 아이템
        action_items = analysis_data.get("action_items", [])
        if action_items:
            markdown += "## 액션 아이템\n\n"
            for item in action_items:
                action = item.get("action", "")
                owner = item.get("owner", "")
                due_date = item.get("due_date", "")
                
                markdown += f"- {action}"
                if owner:
                    markdown += f" (담당: {owner}"
                    if due_date:
                        markdown += f", 기한: {due_date})"
                    else:
                        markdown += ")"
                elif due_date:
                    markdown += f" (기한: {due_date})"
                markdown += "\n"
            markdown += "\n"
        
        # 역할 분담
        participants = analysis_data.get("participants", [])
        if participants:
            markdown += "## 역할 및 책임\n\n"
            for participant in participants:
                name = participant.get("name", "")
                role = participant.get("role", "")
                
                if name and role:
                    markdown += f"- {name}: {role}\n"
            markdown += "\n"
        
        # 다음 단계
        next_steps = analysis_data.get("next_steps", [])
        follow_up_meetings = analysis_data.get("follow_up_meetings", [])
        
        if next_steps or follow_up_meetings:
            markdown += "## 다음 단계 및 후속 조치\n\n"
            
            if next_steps:
                for step in next_steps:
                    markdown += f"- {step}\n"
                markdown += "\n"
            
            if follow_up_meetings:
                markdown += "### 후속 회의\n\n"
                for meeting in follow_up_meetings:
                    purpose = meeting.get("purpose", "")
                    proposed_date = meeting.get("proposed_date", "")
                    
                    if purpose:
                        markdown += f"- {purpose}"
                        if proposed_date:
                            markdown += f" ({proposed_date})"
                        markdown += "\n"
                markdown += "\n"
        
        return markdown