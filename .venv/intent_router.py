from services import email_service as es

def route_intent(gmail_svc,intent: dict):
    service = intent.get("service")
    action = intent.get("action")
    params = intent.get("parameters", {})

    if service == 'gmail':
        if action == 'send':
            es.send_email(gmail_svc, params.get('to', ''), params.get('subject', ''), params.get('body', ''))
        elif action == 'read':
            count = int(params.get('count', 5))
            emails = es.list_emails(gmail_svc, count)
            print("📥 Recent Emails:")
            for i, mail in enumerate(emails, 1):
                print(f"{i}. From: {mail['from']} | Subject: {mail['subject']}\n   Snippet: {mail['snippet']}\n")
        elif action == 'summarize':
            es.summarize_emails_with_ai(gmail_svc, int(params.get('count', 3)))
        else:
            print(f"⚠️ Unsupported Gmail action: {action}")