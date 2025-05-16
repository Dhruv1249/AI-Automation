# services/calendar_service.py

from googleapiclient.discovery import build
from datetime import datetime, timezone
import json,os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta


GEMINI_MODEL = "learnlm-2.0-flash-experimental"
load_dotenv()


def list_events(calendar_svc, count=5):
    """List the next `count` upcoming events in the user’s primary calendar."""
    now = datetime.now(timezone.utc).isoformat()
    events_result = calendar_svc.events().list(
        calendarId='primary',
        timeMin=now,
        maxResults=count,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    if not events:
        print("📭 No upcoming events found.")
        return []
    # Format a simple summary
    summary = []
    for ev in events:
        start = ev['start'].get('dateTime', ev['start'].get('date'))
        summary.append({
            'start': start,
            'summary': ev.get('summary', 'No Title'),
            'id': ev['id']
        })
    return summary

def print_event_list(events):
    """Helper to nicely print the list of events."""
    for i, ev in enumerate(events, 1):
        print(f"{i}. {ev['start']} — {ev['summary']}")

from googleapiclient.errors import HttpError

def create_event(calendar_svc, summary, start, end, description=None):
    """
    Create a calendar event in the user's primary calendar.
    Both start and end must be RFC3339 dateTime strings.
    Uses Asia/Kolkata timezone.
    """
    event_body = {
        'summary': summary,
        'start': {
            'dateTime': start,
            'timeZone': 'Asia/Kolkata'
        },
        'end': {
            'dateTime': end,
            'timeZone': 'Asia/Kolkata'
        }
    }
    if description:
        event_body['description'] = description

    print("🗓️ Creating event with payload:")
    print(json.dumps(event_body, indent=2))

    try:
        ev = calendar_svc.events().insert(
            calendarId='primary',
            body=event_body
        ).execute()
        print(f"📅 Event created: {ev.get('htmlLink')}")
        return ev   # <--- return the event object now
    except HttpError as e:
        error_content = e.content.decode() if hasattr(e, 'content') else str(e)
        print("❌ Failed to create event:", e)
        print("Details:", error_content)
        return None



def filter_events_with_ai(events: list, user_prompt: str) -> list:
    """
    Send the list of events and the user's filter prompt to Gemini,
    and return the filtered sub‑list as Python objects.
    """
    api_key = os.environ['API_KEY']
    client  = genai.Client(api_key=api_key)

    # Build system instruction
    system_text = f"""
You are an assistant that filters calendar events.  
Given a JSON array of events (each with 'start' and 'summary'), and a user prompt,  
return a JSON array of only those events that match the user's request.

Events:
{json.dumps(events, indent=2)}

User request: "{user_prompt}"

Output ONLY the filtered JSON array. If none match, output an empty array [].
"""

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=[ types.Part.from_text(text=system_text) ]
    )
    contents = [ types.Content(role='user', parts=[ types.Part.from_text(text=user_prompt) ]) ]

    # Stream & collect
    response = ""
    for chunk in client.models.generate_content_stream(
        model=GEMINI_MODEL, contents=contents, config=config
    ):
        if chunk.text:
            response += chunk.text

    # Clean code fences
    text = response.strip("`\n ")
    return json.loads(text)
