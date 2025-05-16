# utils/ai.py

import os
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
API_KEY = os.environ.get("API_KEY") or os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("Please set API_KEY or GEMINI_API_KEY in your environment.")

# Asia/Kolkata timezone
TZ = timezone(timedelta(hours=5, minutes=30))

class AIIntentParser:
    def __init__(self, model_name="learnlm-2.0-flash-experimental"):
        self.client = genai.Client(api_key=API_KEY)
        self.model = model_name
        self.prompt_history = []
        self.max_history = 10

        # Build the system prompt once
        now_iso = datetime.now(TZ).isoformat(timespec="seconds")
        self.system_prompt = f'''
You are an AI assistant for a Google Workspace CLI.
Current date/time (Asia/Kolkata): {now_iso}

Parse the user’s request into **one** JSON object with:
  • "service": "gmail" | "calendar" | "chat"
  • "actions": [ {{ "action": "<name>", "parameters": {{ ... }} }}, ... ]

**Supported Gmail actions**:
  • send             → to (string or [strings]), subject (string), body (string), html (opt), attachments (opt)
  • list             → count (int, opt), query/q (string, opt)
  • summarize        → count (int, opt)
  • read             → id (string, opt) OR count (int, opt)
  • attachments_info → id (string, required)
  • search           → query (string, required), max_results (int, opt)
  • list_labels      → (no parameters)
  • create_label     → name (string, required)
  • update_label     → id (string, required), name (string, required)
  • delete_label     → id (string, required)
  • list_by_label    → label_ids ([strings], required), count (int, opt)
  • mark_read        → id (string, required)
  • mark_unread      → id (string, required)
  • move             → id (string, required), label_id (string, required)
  • delete           → id (string, opt) OR ids ([strings], opt)
  • batch_mark_read  → ids ([strings], required)
  • batch_delete     → ids ([strings], required)

**Supported Calendar actions**:
  • list     → count (int, opt)
  • create   → either:
       – start (RFC3339 string) & end (RFC3339 string)
       – date (\"YYYY-MM-DD\" or \"tomorrow\") & summary (string, opt) & description (opt) & time (\"3pm\" style, opt)
    If only date is given, default to a 1‑hour slot 09:00–10:00 local time.

**Multi‑action sequencing**:
  If the user requests multiple tasks (e.g. “Send an email, then list my last 3”), list them in order in "actions".

**Chat fallback**:
  If the request is not about Gmail or Calendar, return:
    {{ "service":"chat", "actions":[] }}

Output **only** the JSON—no extra text.
'''

    def parse_prompt(self, user_prompt: str) -> dict | None:
        # Manage history
        self.prompt_history.append(user_prompt)
        if len(self.prompt_history) > self.max_history:
            self.prompt_history.clear()
            print(f"🗑️ Prompt history cleared after {self.max_history} entries.")

        # Prepare and stream
        full_prompt = self.system_prompt + "\nUser: " + user_prompt
        response_text = ""
        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=[types.Content(role="user",
                                    parts=[types.Part.from_text(text=full_prompt)])],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        ):
            if chunk.text:
                print(chunk.text, end="")
                response_text += chunk.text

        # Attempt JSON parse
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Chat fallback
            print("\n🤖 (chat fallback)")
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=[types.Content(role="user",
                                        parts=[types.Part.from_text(text=user_prompt)])]
            ):
                print(chunk.text, end="")
            return None
        
    def chat_ai(self,prompt: str) -> str:
      try:
          
          client = genai.Client(api_key=API_KEY)

          contents = [
              types.Content(
                  role="user",
                  parts=[types.Part.from_text(text=prompt)],
              )
          ]
         
          # Optional: System instruction
          system_instruction = [
              types.Part.from_text(
                  text="You are a helpful assistant for general queries. Respond clearly and concisely."
              )
          ]
          
          config = types.GenerateContentConfig(
              response_mime_type="text/plain",
              system_instruction=system_instruction,
          )

          response_text = ""
          for chunk in client.models.generate_content_stream(
              model="learnlm-2.0-flash-experimental",
              contents=contents,
              config=config,
          ):
              if chunk.text:
                  print(chunk.text, end="")  # Optional: live stream to console
                  response_text += chunk.text

          return response_text

      except Exception as e:
          return f"❌ Chat error: {e}"
