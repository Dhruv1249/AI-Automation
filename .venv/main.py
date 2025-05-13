
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
    'https://www.googleapis.com/auth/gmail.modify',
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
You are a JSON-outputting assistant for Google Workspace. Return a valid JSON with:
- `service`: One of [gmail]
- `action`: One of [send, read, summarize]
- `parameters`: Dict with required fields for the action.

Examples:
1. Send email:
{
  "service": "gmail",
  "action": "send",
  "parameters": {
    "to": "someone@example.com",
    "subject": "Hello",
    "body": "This is a test"
  }
}

2. Read emails:
{
  "service": "gmail",
  "action": "read",
  "parameters": {
    "count": 5
  }
}

3. Summarize emails:
{
  "service": "gmail",
  "action": "summarize",
  "parameters": {
    "count": 3
  }
}
Only output raw JSON.
""" )
    ]

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

def list_emails(service, count=5):
    """List recent emails."""
    results = service.users().messages().list(userId='me', maxResults=count).execute()
    messages = results.get('messages', [])
    email_data = []

    for msg in messages:
        msg_detail = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = msg_detail['payload'].get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        from_ = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
        snippet = msg_detail.get('snippet', '')
        email_data.append({'from': from_, 'subject': subject, 'snippet': snippet})
    
    return email_data


def summarize_emails_with_ai(service, count=3):
    """Summarize recent emails and identify spam using Gemini."""
    emails = list_emails(service, count)
    summary_prompt = "Summarize the following emails and indicate which ones look like spam:\n\n"
    for idx, email in enumerate(emails, 1):
        summary_prompt += f"{idx}. From: {email['from']}\nSubject: {email['subject']}\nSnippet: {email['snippet']}\n\n"

    client = genai.Client(api_key=os.environ['API_KEY'])
    contents = [
        types.Content(role='user', parts=[types.Part.from_text(text=summary_prompt)])
    ]
    response = ""
    for chunk in client.models.generate_content_stream(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type='text/plain')
    ):
        response += chunk.text
    print("📬 Email summary:\n", response)

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
    if service == 'gmail':
        if action == 'send':
            send_email(gmail_svc, params.get('to', ''), params.get('subject', ''), params.get('body', ''))
        elif action == 'read':
            count = int(params.get('count', 5))
            emails = list_emails(gmail_svc, count)
            print("📥 Recent Emails:")
            for i, mail in enumerate(emails, 1):
                print(f"{i}. From: {mail['from']} | Subject: {mail['subject']}\n   Snippet: {mail['snippet']}\n")
        elif action == 'summarize':
            summarize_emails_with_ai(gmail_svc, int(params.get('count', 3)))
        else:
            print(f"⚠️ Unsupported Gmail action: {action}")



if __name__ == '__main__':
    main()

