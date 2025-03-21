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
                model="gpt-4o-mini",
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
            model="gpt-4o-mini",
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
            model="gpt-4o-mini",
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

def convert_to_markdown(faqs: List[Dict]) -> str:
    """Convert FAQ items to markdown format"""
    if not faqs:
        return ""
    
    # Group FAQs by category
    categories = {}
    for faq in faqs:
        category = faq.get("category", "기타")
        if category not in categories:
            categories[category] = []
        categories[category].append(faq)
    
    # Generate markdown
    markdown = "# 자주 묻는 질문 (FAQ)\n\n"
    
    # Add table of contents
    markdown += "## 목차\n\n"
    for category in categories.keys():
        markdown += f"- [{category}](#{category.replace(' ', '-')})\n"
    markdown += "\n---\n\n"
    
    # Add FAQ items by category
    for category, items in categories.items():
        markdown += f"## {category}\n\n"
        for item in items:
            markdown += f"### {item['question']}\n\n"
            markdown += f"{item['answer']}\n\n"
            
            # Add related information if available
            if "related_info" in item:
                related_info = item["related_info"]
                if "참고 사항" in related_info:
                    markdown += "**참고 사항:**\n"
                    for ref in related_info["참고 사항"]:
                        markdown += f"- {ref}\n"
                    markdown += "\n"
                
                if "관련 주제" in related_info:
                    markdown += "**관련 주제:**\n"
                    for topic in related_info["관련 주제"]:
                        markdown += f"- {topic}\n"
                    markdown += "\n"
                
                if "자주 묻는 질문" in related_info:
                    markdown += "**관련 질문:**\n"
                    for q in related_info["자주 묻는 질문"]:
                        markdown += f"- {q}\n"
                    markdown += "\n"
            
            markdown += "---\n\n"
    
    # Add metadata
    markdown += f"\n*마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
    return markdown

def update_markdown_file(new_faqs: List[Dict], markdown_file: str = "FAQ.md"):
    """Update markdown file with new FAQs"""
    existing_faqs = []
    
    # Read existing markdown file if it exists
    if os.path.exists(markdown_file):
        print(f"\n기존 FAQ 문서를 읽는 중...")
        try:
            # Convert existing markdown back to FAQ format
            response = client_openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """You are an AI that converts markdown FAQ documentation back to structured JSON format.
Your task is to:
1. Extract FAQ items from the markdown
2. Preserve all information including categories and related info
3. Format the output as a JSON array of FAQ items using the same structure as before

Output format should match:
{
    "faqs": [
        {
            "category": "환경 설정",
            "question": "환경 변수 설정은 어떻게 관리해야 하나요?",
            "answer": "환경 변수 관리를 위한 모범 사례는...",
            "related_info": {
                "참고 사항": ["환경 변수 암호화 가이드", ...],
                "관련 주제": ["보안", ...],
                "자주 묻는 질문": ["프로덕션 배포 전 체크리스트가 있나요?", ...]
            }
        }
    ]
}"""},
                    {"role": "user", "content": f"Please convert this markdown FAQ document to JSON format:\n\n{open(markdown_file, 'r', encoding='utf-8').read()}"}
                ],
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            if isinstance(result, dict) and "faqs" in result:
                existing_faqs = result["faqs"]
                print(f"기존 FAQ {len(existing_faqs)}개를 읽었습니다.")
        except Exception as e:
            print(f"기존 FAQ 읽기 실패: {str(e)}")
            print("새로운 FAQ 문서를 시작합니다.")
    
    # Merge existing and new FAQs
    if existing_faqs:
        print("\nFAQ 병합 중...")
        try:
            response = client_openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """You are an AI that merges FAQ items intelligently.
Your task is to:
1. Combine existing and new FAQ items
2. Remove duplicates and merge similar items
3. Preserve all unique information
4. Maintain consistent categorization
5. Format the output as a JSON array of FAQ items"""},
                    {"role": "user", "content": f"Please merge these two sets of FAQ items:\n\nExisting FAQs:\n{json.dumps(existing_faqs, indent=2, ensure_ascii=False)}\n\nNew FAQs:\n{json.dumps(new_faqs, indent=2, ensure_ascii=False)}"}
                ],
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            if isinstance(result, dict) and "faqs" in result:
                merged_faqs = result["faqs"]
                print(f"FAQ 병합 완료: 총 {len(merged_faqs)}개 항목")
            else:
                merged_faqs = existing_faqs + new_faqs
                print("FAQ 자동 병합 실패. 단순 병합으로 진행합니다.")
        except Exception as e:
            print(f"FAQ 병합 중 오류 발생: {str(e)}")
            merged_faqs = existing_faqs + new_faqs
    else:
        merged_faqs = new_faqs
    
    # Convert to markdown and save
    markdown_content = convert_to_markdown(merged_faqs)
    with open(markdown_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    print(f"\nFAQ 문서가 {markdown_file}에 업데이트되었습니다.")

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
    
    # Save results to CSV
    df = pd.DataFrame(faqs)
    output_file = f"faq_{channel_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"FAQs saved to {output_file}")
    
    # Update markdown documentation
    update_markdown_file(faqs)

if __name__ == "__main__":
    main()