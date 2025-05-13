
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

# Load environment variables
load_dotenv()

# Constants
TOKEN_PATH = 'token.json'
CLIENT_SECRETS = '.venv/client_secret.json'
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    # Extend scopes for Drive, Sheets, Docs, Calendar, Keep
]
GEMINI_MODEL = 'learnlm-2.0-flash-experimental'


def get_credentials():
    """
    Handles OAuth flow and token persistence.
    Loads existing tokens from TOKEN_PATH or runs local server flow if needed.
    """
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
        creds = flow.run_local_server(port=0)
    # Save tokens for next run
    with open(TOKEN_PATH, 'w') as token_file:
        token_file.write(creds.to_json())
    return creds


def call_ai(prompt: str) -> dict:
    """
    Calls Google Gemini to generate a JSON intent based on the prompt.
    """
    api_key = os.environ.get('API_KEY')
    if not api_key:
        raise RuntimeError('Please set GEMINI_API_KEY in your environment (.env file).')

    client = genai.Client(api_key=api_key)
    print("AI STARTED")
    # Prepare conversation
    user_content = types.Content(role='user', parts=[types.Part.from_text(text=prompt)])
    config = types.GenerateContentConfig(
        response_mime_type='text/plain',
        system_instruction=[
            types.Part.from_text(text="""
You are a JSON-outputting assistant. Given a user prompt, emit a single valid JSON object with keys: service, action, parameters.
Example schema:
{
  "service": "gmail",
  "action": "send",
  "parameters": { "to": "...", "subject": "...", "body": "..." }
}
""")
        ],
    )

    # Stream response
    response_text = ''
    for chunk in client.models.generate_content_stream(
            model=GEMINI_MODEL,
            contents=[user_content],
            config=config):
        response_text += chunk.text

    # Clean code fences if present
    text = response_text.strip()
    if text.startswith('```'):
        text = text[text.find('\n')+1:]
    if text.endswith('```'):
        text = text[:text.rfind('```')]
    text = text.strip()

    # Parse JSON
    print(text)
    try:
        intent = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f'Failed to parse intent JSON: {e}\nResponse was: {text}')
    return intent


def send_email(service, to: str, subject: str, body: str):
    """Send an email via Gmail API."""
    raw = base64.urlsafe_b64encode(f"To: {to}\r\nSubject: {subject}\r\n\r\n{body}".encode()).decode()
    message = {'raw': raw}
    service.users().messages().send(userId='me', body=message).execute()
    print(f'✅ Email sent to {to} with subject "{subject}".')


def main():
    print('🔐 Authenticating with Google...')
    creds = get_credentials()
    gmail_svc = build('gmail', 'v1', credentials=creds)
    print('✅ Authentication successful.')

    prompt = input('💬 Enter your prompt for AI-driven action: ')
    intent = call_ai(prompt)
    if not intent:
        print('❌ No intent returned from AI.')
        return

    service = intent.get('service')
    action = intent.get('action')
    params = intent.get('parameters', {})

    # Basic routing
    if service == 'gmail' and action == 'send':
        send_email(gmail_svc, params.get('to', ''), params.get('subject', ''), params.get('body', ''))
    else:
        print('❌ Unsupported intent:')
        print(json.dumps(intent, indent=2))


if __name__ == '__main__':
    main()

