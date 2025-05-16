from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import base64
import mimetypes
from email.message import EmailMessage
from email import policy
from email.parser import BytesParser


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
        email_data.append({
            'id': msg['id'],
            'from': from_,
            'subject': subject,
            'snippet': snippet
        })

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

def send_email(service, to: str, subject: str, body_text: str, body_html: str = None, attachments: list = None):
    """Send an email via Gmail API with optional HTML and attachments."""
    message = EmailMessage()
    message['To'] = to
    message['Subject'] = subject
    message.set_content(body_text)

    if body_html:
        message.add_alternative(body_html, subtype='html')

    # Add attachments if provided
    if attachments:
        for filepath in attachments:
            content_type, _ = mimetypes.guess_type(filepath)
            maintype, subtype = content_type.split('/', 1) if content_type else ('application', 'octet-stream')
            with open(filepath, 'rb') as f:
                message.add_attachment(f.read(),
                                       maintype=maintype,
                                       subtype=subtype,
                                       filename=os.path.basename(filepath))

    # Encode and send
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()
    print(f'✅ Email sent to {to} with subject "{subject}".')

def read_email_by_id(service, message_id):
    """Read full email by message ID with MIME parsing."""
    message = service.users().messages().get(userId='me', id=message_id, format='raw').execute()
    msg_str = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))
    mime_msg = BytesParser(policy=policy.default).parsebytes(msg_str)

    subject = mime_msg['subject']
    sender = mime_msg['from']
    body_parts = {
        'plain': None,
        'html': None
    }

    for part in mime_msg.walk():
        content_type = part.get_content_type()
        if content_type == 'text/plain' and body_parts['plain'] is None:
            body_parts['plain'] = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
        elif content_type == 'text/html' and body_parts['html'] is None:
            body_parts['html'] = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')

    return {
        'subject': subject,
        'from': sender,
        'body': body_parts
    }

def get_attachments_info(service, message_id):
    message = service.users().messages().get(userId='me', id=message_id).execute()
    parts = message.get('payload', {}).get('parts', [])
    attachments = []

    for part in parts:
        filename = part.get('filename')
        body = part.get('body', {})
        mime_type = part.get('mimeType')
        size = body.get('size', 0)
        if filename:
            attachments.append({
                'filename': filename,
                'type': mime_type,
                'size': size
            })
    return attachments

def search_emails(service, query, max_results=10):
    results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    return results.get('messages', [])


def list_labels(service):
    return service.users().labels().list(userId='me').execute().get('labels', [])

def create_label(service, name):
    label = {'name': name, 'labelListVisibility': 'labelShow', 'messageListVisibility': 'show'}
    return service.users().labels().create(userId='me', body=label).execute()

def delete_label(service, label_id):
    service.users().labels().delete(userId='me', id=label_id).execute()

def update_label(service, label_id, new_name):
    body = {'name': new_name}
    return service.users().labels().update(userId='me', id=label_id, body=body).execute()

def list_emails_by_label(service, label_ids, count=10):
    results = service.users().messages().list(userId='me', labelIds=label_ids, maxResults=count).execute()
    return results.get('messages', [])


def modify_labels(service, message_id, add_labels=[], remove_labels=[]):
    body = {
        'addLabelIds': add_labels,
        'removeLabelIds': remove_labels
    }
    service.users().messages().modify(userId='me', id=message_id, body=body).execute()

def mark_as_read(service, message_id):
    modify_labels(service, message_id, remove_labels=['UNREAD'])

def mark_as_unread(service, message_id):
    modify_labels(service, message_id, add_labels=['UNREAD'])


def move_email_to_label(service, message_id, label_id):
    modify_labels(service, message_id, add_labels=[label_id])


def batch_mark_as_read(service, message_ids):
    for message_id in message_ids:
        mark_as_read(service, message_id)

def delete_email(service, message_id):
    service.users().messages().trash(userId='me', id=message_id).execute()



def batch_delete_emails(service, message_ids):
    for message_id in message_ids:
        delete_email(service, message_id)
