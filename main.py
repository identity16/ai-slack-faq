import os
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from tqdm import tqdm
from openai import OpenAI
import json
import ssl
import certifi

ssl._create_default_https_context = ssl._create_unverified_context

ssl_context = ssl.create_default_context(cafile=certifi.where())

# Load environment variables
load_dotenv(override=True)

# Initialize Slack client
SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
if not SLACK_TOKEN:
    raise ValueError("SLACK_BOT_TOKEN not found in environment variables")
print(f"Token loaded: {SLACK_TOKEN[:10]}...")  # 토큰의 처음 10자만 출력

client = WebClient(token=SLACK_TOKEN)

# Initialize OpenAI client
client_openai = OpenAI()  # 환경 변수에서 자동으로 API 키를 가져옵니다
if not client_openai.api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

def get_channel_id(channel_name: str) -> str:
    """Get channel ID from channel name"""
    try:
        # Initialize variables for pagination
        all_channels = []
        cursor = None
        
        while True:
            # Get next page of channels
            if cursor:
                result = client.conversations_list(cursor=cursor, limit=1000)
            else:
                result = client.conversations_list(limit=1000)
            
            all_channels.extend(result["channels"])
            print(f"Found {len(all_channels)} channels so far...")
            
            # Check if there are more channels to fetch
            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        
        print(f"Total channels found: {len(all_channels)}")
        # Search for the channel in the complete list
        for channel in all_channels:
            if channel["name"] == channel_name:
                return channel["id"]
                
        print(f"Channel '{channel_name}' not found in the list of accessible channels")
    except SlackApiError as e:
        print(f"Slack API Error: {e.response['error']}")
    return None

def get_conversation_history(
    channel_id: str,
    start_time: datetime,
    end_time: datetime
) -> List[Dict]:
    """Get conversation history for a specific time period"""
    messages = []
    try:
        result = client.conversations_history(
            channel=channel_id,
            oldest=start_time.timestamp(),
            latest=end_time.timestamp(),
            limit=1000
        )
        messages.extend(result["messages"])
        
        # Handle pagination
        while result.get("has_more", False):
            result = client.conversations_history(
                channel=channel_id,
                oldest=start_time.timestamp(),
                latest=end_time.timestamp(),
                cursor=result["response_metadata"]["next_cursor"],
                limit=1000
            )
            messages.extend(result["messages"])
            
    except SlackApiError as e:
        print(f"Error: {e}")
    
    return messages

def get_thread_replies(channel_id: str, thread_ts: str) -> List[Dict]:
    """Get all replies in a thread"""
    try:
        result = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts
        )
        return result["messages"]
    except SlackApiError as e:
        print(f"Error: {e}")
        return []

def extract_faq_with_llm(threads: List[Dict]) -> List[Dict]:
    """Extract FAQ using OpenAI's API in three steps:
    1. Extract Q&A pairs from threads
    2. Group and generalize similar questions
    3. Format them into comprehensive Korean FAQ documentation
    """
    raw_qas = []
    
    # Step 1: Extract Q&A pairs from threads
    for thread in tqdm(threads, desc="1단계: 스레드에서 Q&A 추출 중"):
        thread_text = "\n".join([msg.get("text", "") for msg in thread])
        
        if len(thread_text.split()) < 10:
            print(f"\nSkipping short thread ({len(thread_text.split())} words)")
            continue
            
        print(f"\n{'='*50}")
        print(f"Analyzing thread with {len(thread_text.split())} words:")
        print(f"Thread content (first 200 chars): {thread_text[:200]}...")
            
        try:
            # First pass: Extract raw Q&A
            response = client_openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": """You are an AI that analyzes Slack conversations and extracts question-answer pairs.
Your task is to:
1. Identify if the conversation contains a clear question and its corresponding answer
2. Extract the core question and answer, preserving technical accuracy
3. Format the output as a JSON object with "question", "answer", and "context" fields
4. If the conversation doesn't contain a clear Q&A, return {"question": null, "answer": null, "context": null}

Example output format:
{
    "question": "How can I fix the deployment error in staging?",
    "answer": "The deployment error was caused by missing environment variables. Adding DATABASE_URL to the .env.staging file resolved the issue.",
    "context": "Deployment, Environment Variables, Staging Environment"
}"""},
                    {"role": "user", "content": f"Please analyze this Slack thread and extract the core question and answer if present:\n\n{thread_text}"}
                ],
                temperature=0.3
            )
            
            result = response.choices[0].message.content
            print(f"First pass result:\n{result}\n")
            
            try:
                qa_item = json.loads(result)
                if qa_item and isinstance(qa_item, dict):
                    if qa_item.get("question") and qa_item.get("answer"):
                        raw_qas.append(qa_item)
                        print("Successfully extracted Q&A pair")
                    else:
                        print("No clear Q&A found in this thread")
            except json.JSONDecodeError:
                print("Failed to parse JSON response")
                continue
                
        except Exception as e:
            print(f"Error in first pass: {str(e)}")
            continue
        
        print(f"{'='*50}\n")
    
    print(f"\n총 {len(raw_qas)}개의 Q&A 쌍을 추출했습니다.")
    
    # Step 2: Group and generalize similar questions
    if not raw_qas:
        return []
        
    print("\n2단계: Q&A 분석 및 일반화 중...")
    try:
        response = client_openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": """You are an AI that analyzes and generalizes Q&A pairs into comprehensive FAQ items.

Your task is to:
1. Group similar questions together
2. Generalize specific questions into more broadly applicable ones
3. Enhance answers with additional context and best practices
4. Format the output as a JSON array of grouped FAQ items

Example output format:
{
    "grouped_faqs": [
        {
            "category": "환경 설정",
            "items": [
                {
                    "general_question": "환경 변수 설정은 어떻게 관리해야 하나요?",
                    "specific_examples": ["스테이징 환경에서 DB_URL 설정", "프로덕션 환경의 API 키 관리"],
                    "comprehensive_answer": "환경 변수 관리 모범 사례:\n1. 환경별 .env 파일 사용 (.env.staging, .env.production)\n2. 민감한 정보는 암호화하여 저장\n3. 환경 변수 템플릿 (.env.example) 제공\n4. 주기적인 키 로테이션 실행",
                    "best_practices": ["환경 변수 암호화", "정기적인 키 갱신", "접근 권한 제한"],
                    "related_topics": ["보안", "설정 관리", "배포 프로세스"]
                }
            ]
        }
    ]
}"""},
                {"role": "user", "content": f"Please analyze and group these Q&A pairs into comprehensive FAQ items:\n\n{json.dumps(raw_qas, indent=2, ensure_ascii=False)}"}
            ],
            temperature=0.3
        )
        
        grouped_result = response.choices[0].message.content
        print(f"\nGrouping result:\n{grouped_result}\n")
        
        # Step 3: Format into final Korean FAQ documentation
        print("\n3단계: 최종 FAQ 문서화 진행 중...")
        response = client_openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": """You are an AI that creates well-formatted Korean FAQ documentation.

Your task is to:
1. Convert the grouped FAQ items into final documentation format
2. Make the documentation clear and professional:
   - Use natural, professional Korean
   - Ensure questions are concise but descriptive
   - Format answers with clear structure and examples
   - Include relevant context and best practices
3. Format the output as a JSON array of FAQ items

Example output format:
{
    "faqs": [
        {
            "category": "환경 설정",
            "question": "환경 변수 설정은 어떻게 관리해야 하나요?",
            "answer": "환경 변수 관리를 위한 모범 사례는 다음과 같습니다:\n\n1. 환경별 설정 파일 관리\n   - .env.staging: 스테이징 환경 설정\n   - .env.production: 프로덕션 환경 설정\n\n2. 보안 관리\n   - 민감한 정보는 반드시 암호화\n   - 정기적인 키 로테이션 실행\n   - 접근 권한 제한 설정\n\n3. 문서화\n   - .env.example 템플릿 제공\n   - 필수 환경 변수 목록 관리",
            "related_info": {
                "참고 사항": ["환경 변수 암호화 가이드", "키 관리 정책", "접근 권한 설정 방법"],
                "관련 주제": ["보안", "설정 관리", "배포 프로세스"],
                "자주 묻는 질문": ["프로덕션 배포 전 체크리스트가 있나요?", "환경 변수 동기화는 어떻게 하나요?"]
            }
        }
    ]
}"""},
                {"role": "user", "content": f"Please convert these grouped FAQ items into final Korean documentation:\n\n{grouped_result}"}
            ],
            temperature=0.3
        )
        
        result = response.choices[0].message.content
        print(f"\nFinal documentation result:\n{result}\n")
        
        formatted_faqs = json.loads(result)
        if isinstance(formatted_faqs, dict) and "faqs" in formatted_faqs:
            print(f"\n총 {len(formatted_faqs['faqs'])}개의 FAQ 항목이 생성되었습니다.")
            return formatted_faqs["faqs"]
            
    except Exception as e:
        print(f"Error in documentation process: {str(e)}")
        return []
    
    return []

def main():
    # Get user inputs
    channel_name = input("Enter Slack channel name (without #): ")
    days_ago = int(input("Enter number of days to look back: "))
    
    # Calculate time range
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days_ago)
    
    # Get channel ID
    channel_id = get_channel_id(channel_name)
    if not channel_id:
        print(f"Channel {channel_name} not found!")
        return
    
    # Get messages
    print(f"Fetching messages from {start_time} to {end_time}...")
    messages = get_conversation_history(channel_id, start_time, end_time)
    
    # Get threads
    threads = []
    for msg in tqdm(messages, desc="Fetching threads"):
        if "thread_ts" in msg:
            thread_messages = get_thread_replies(channel_id, msg["thread_ts"])
            if thread_messages:
                threads.append(thread_messages)
    
    # Extract FAQs
    print("Analyzing threads with LLM...")
    faqs = extract_faq_with_llm(threads)
    
    # Save results
    df = pd.DataFrame(faqs)
    output_file = f"faq_{channel_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"FAQs saved to {output_file}")

if __name__ == "__main__":
    main()