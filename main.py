import os
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from tqdm import tqdm
import openai
import json

# Load environment variables
load_dotenv()

# Initialize Slack client
SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=SLACK_TOKEN)

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_channel_id(channel_name: str) -> str:
    """Get channel ID from channel name"""
    try:
        result = client.conversations_list()
        for channel in result["channels"]:
            if channel["name"] == channel_name:
                return channel["id"]
    except SlackApiError as e:
        print(f"Error: {e}")
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
    """Extract FAQ using OpenAI's API"""
    faqs = []
    
    for thread in tqdm(threads, desc="Analyzing threads"):
        # Combine thread messages into a single text
        thread_text = "\n".join([msg.get("text", "") for msg in thread])
        
        # Skip if thread is too short
        if len(thread_text.split()) < 10:
            continue
            
        try:
            response = openai.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are an AI that analyzes Slack conversations and extracts potential FAQ questions and answers. If the conversation doesn't contain a clear question and answer, return null."},
                    {"role": "user", "content": f"Please analyze this Slack thread and extract a potential FAQ question and answer if applicable. If not applicable, return null:\n\n{thread_text}"}
                ],
                temperature=0.3
            )
            
            result = response.choices[0].message.content
            
            try:
                # Try to parse the response as JSON
                faq_item = json.loads(result)
                if faq_item and isinstance(faq_item, dict):
                    faqs.append(faq_item)
            except json.JSONDecodeError:
                # If response is not JSON, skip it
                continue
                
        except Exception as e:
            print(f"Error processing thread: {e}")
            continue
    
    return faqs

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