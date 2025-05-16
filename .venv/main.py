
"""
AI-Driven Google Workspace CLI Script (Gemini-powered)

Features:
1. OAuth 2.0 desktop flow with token persistence
2. Prompting the user for natural-language commands
3. AI intent generation via Google Gemini (google-genai library)
4. Execution of a Gmail "send email" action based on the intent

Prerequisites:
- client_secret.json in the same directory
- .env file with GEMINI_API_KEY
- Install dependencies:
    pip install python-dotenv googl
    e-auth-oauthlib google-api-python-client google-genai
"""

import os
import json
import base64
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google import genai
from google.genai import types
from intent_router import route_intent
from utils.ai import AIIntentParser
from datetime import datetime, timezone, timedelta
from google.auth.exceptions import RefreshError

# Load environment variables
load_dotenv()

# Constants
TOKEN_PATH = 'token.json'
CLIENT_SECRETS = '.venv/client_secret.json'
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.modify',     # ✅ needed for delete, mark, move
    'https://www.googleapis.com/auth/gmail.readonly',   # optional, covered by modify
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly',
]

GEMINI_MODEL = 'learnlm-2.0-flash-experimental'


def get_credentials():
    creds = None

    # Step 1: Load existing credentials
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception as e:
            print(f"⚠️ Failed to load token file: {e}")
            creds = None

    # Step 2: Refresh if possible
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            print("🔁 Token refreshed successfully.")
        except RefreshError as e:
            print(f"⚠️ Failed to refresh token: {e}")
            creds = None  # Fall back to new flow
    elif not creds or not creds.valid:
        # Step 3: Fallback to OAuth flow
        print("🔑 Launching OAuth flow...")
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
        creds = flow.run_local_server(port=0)

    # Step 4: Save credentials back
    if creds:
        try:
            with open(TOKEN_PATH, "w") as token_file:
                token_file.write(creds.to_json())
        except Exception as e:
            print(f"⚠️ Failed to write token file: {e}")

    return creds


def main():
    print(' Authenticating with Google...')
    creds = get_credentials()
    gmail_svc = build('gmail', 'v1', credentials=creds)
    calendar_svc = build('calendar', 'v3', credentials=creds)
    print(' Authentication successful.')
    prompt = " "
    ai = AIIntentParser()
    while(prompt!='q'):
        prompt = input(' Enter your prompt for AI-driven action: ')
        intent = ai.parse_prompt(prompt)
        if not intent:
            print('❌ No intent returned from AI.')
            return
        if intent.get('service') == 'chat':
            answer = ai.chat_ai(prompt)
            print(f" {answer}")
        else:
            route_intent(
            {'gmail': gmail_svc, 'calendar': calendar_svc},
            intent,
            raw_prompt=prompt
        )
    



if __name__ == '__main__':
    main()

