# Slack FAQ Generator

This script generates FAQs automatically by analyzing conversations in a Slack channel.

## Features

- Collects conversation data from a specific Slack channel for a specified period
- Analyzes only threaded conversations
- Converts the data into FAQ format using GPT-4
- Saves the results in a CSV file

## Installation

1. Install the required packages:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
- Copy the `.env.example` file to `.env`
- Set the following values:
  - `SLACK_BOT_TOKEN`: Slack bot token
  - `OPENAI_API_KEY`: OpenAI API key

## Slack Bot Setup

1. Create a new app on the [Slack API website](https://api.slack.com/apps)
2. Add the following Bot Token Scopes:
   - channels:history
   - channels:read
   - groups:history
   - groups:read
3. Install the app to your workspace and copy the Bot Token

## Usage

1. Run the script:
```bash
python main.py
```

2. Enter the inputs as prompted:
   - Channel name (exclude the #)
   - Search period (in days)

3. The results will be saved in the format `faq_channelname_date.csv`.

## Notes

- Processing time may be longer if there are many messages in the channel.
- Costs may be incurred based on OpenAI API usage.
- The bot must be invited to the channel.