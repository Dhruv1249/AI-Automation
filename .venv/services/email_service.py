from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

GEMINI_MODEL = "learnlm-2.0-flash-experimental"
load_dotenv()

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