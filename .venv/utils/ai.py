import os, json
from google import genai
from google.genai import types
from dotenv import load_dotenv

GEMINI_MODEL = "learnlm-2.0-flash-experimental"
load_dotenv()

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