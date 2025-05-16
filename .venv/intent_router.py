# intent_router.py

from datetime import datetime, timezone, timedelta
from services import email_service as es
from services import calendar_service as cs

# Asia/Kolkata timezone
IST = timezone(timedelta(hours=5, minutes=30))

def route_intent(service_clients: dict, intent: dict, raw_prompt: str = ""):
    """
    Dispatch multi-action intent *dynamically*, using outputs of prior steps
    whenever an action lacks explicit target IDs.
    """
    gmail_svc = service_clients.get("gmail")
    cal_svc   = service_clients.get("calendar")

    service = intent.get("service")
    actions = intent.get("actions", [])

    # Will hold the list of last-returned items (each item must have 'id')
    last_items: list[dict] = []

    if service == "gmail":
        if not gmail_svc:
            print("⚠️ Gmail service not initialized."); return

        for item in actions:
            act    = item.get("action", "").lower()
            params = item.get("parameters", {}) or {}
            # unify count / query
            count = params.get("count") or params.get("maxResults") or params.get("max_results")
            query = params.get("query") or params.get("q")

            # helper to pull IDs from last_items
            def get_ids():
                return [i["id"] for i in last_items]

            try:
                # --------- LIST or SEARCH  ---------
                if act in ("list", "search"):
                    n = int(count) if count else 5
                    if act == "search" and query:
                        msgs = es.search_emails(gmail_svc, query, max_results=n)
                        print(f"🔍 Found {len(msgs)} messages for '{query}'.")
                    else:
                        msgs = es.list_emails(gmail_svc, n)
                        print(f"📬 Listed {len(msgs)} emails.")
                    # fetch full details for display and context
                    detailed = []
                    for m in msgs:
                        d = gmail_svc.users().messages().get(userId='me', id=m['id']).execute()
                        headers = d['payload'].get('headers', [])
                        subj = next((h['value'] for h in headers if h['name']=="Subject"), "")
                        frm  = next((h['value'] for h in headers if h['name']=="From"), "")
                        detailed.append({"id":m['id'], "subject":subj, "from":frm})
                    last_items = detailed
                    for idx, e in enumerate(detailed,1):
                        print(f"{idx}. {e['from']} — {e['subject']} (ID: {e['id']})")

                # --------- SEND ---------
                elif act == "send":
                    to = params.get("to") or []
                    if isinstance(to, str): to = [to]
                    subj = params.get("subject") or ""
                    body = params.get("body") or params.get("body_text") or ""
                    html = params.get("html")
                    atts = params.get("attachments")
                    if not to or not subj or not body:
                        raise ValueError("Missing to, subject, or body")
                    for r in to:
                        es.send_email(gmail_svc, r, subj, body, html, atts)
                    print(f"✅ Email sent to {', '.join(to)}")
                    last_items = []  # no list context after sending

                # --------- READ ---------
                elif act == "read":
                    # Determine message IDs to read:
                    if "id" in params and not str(params["id"]).startswith("{{"):
                        mids = [params["id"]]
                    elif query:
                        # if user supplied a query, search first
                        msgs = es.search_emails(gmail_svc, query, max_results=count or 1)
                        mids = [m["id"] for m in msgs]
                    else:
                        # fallback to last_items
                        mids = [item["id"] for item in last_items[: (count or 1)]]

                    if not mids:
                        raise ValueError("No message IDs to read")

                    for mid in mids:
                        d = es.read_email_by_id(gmail_svc, mid)
                        print(f"📖 From: {d['from']}\nSubject: {d['subject']}\n{d['body']['plain'] or d['body']['html']}\n")

                    # clear context after reading
                    last_items = []

                # --------- ATTACHMENTS INFO ---------
                                # --------- ATTACHMENTS INFO ---------
                elif act == "attachments_info":
                    raw = params.get("id")
                    # if AI gave a placeholder or no ID, use last_items
                    if raw and not str(raw).startswith("{{"):
                        mid = raw
                    elif last_items:
                        mid = last_items[0]["id"]
                    else:
                        mid = None

                    if not mid:
                        raise ValueError("No message ID for attachments_info")

                    atts = es.get_attachments_info(gmail_svc, mid)
                    print(f"📎 Attachments for {mid}:")
                    for a in atts:
                        print(f"- {a['filename']} ({a['size']} bytes)")

                    # clear context
                    last_items = []


                # --------- LABELS ---------
                elif act == "list_labels":
                    labels = es.list_labels(gmail_svc)
                    print("🏷️ Labels:")
                    for l in labels:
                        print(f"- {l['name']} ({l['id']})")
                    last_items = []  # not a message list

                elif act == "create_label":
                    name = params.get("name")
                    if not name: raise ValueError("Missing label name")
                    lab = es.create_label(gmail_svc, name)
                    print(f"✅ Created label: {lab['name']}")
                    last_items = []

                elif act == "update_label":
                    lid = params.get("id"); new = params.get("name")
                    if not lid or not new:
                        raise ValueError("Missing id or new name")
                    # If the user passed a name instead of an ID, resolve it:
                    if not any(l["id"] == lid for l in es.list_labels(gmail_svc)):
                        # treat lid as a name
                        label = next((l for l in es.list_labels(gmail_svc) if l["name"].lower() == lid.lower()), None)
                        if not label:
                            raise ValueError(f"Label '{lid}' not found")
                        lid = label["id"]
                    lab = es.update_label(gmail_svc, lid, new)
                    print(f"✅ Renamed label to: {lab['name']}")


                elif act == "delete_label":
                    lid = params.get("id")
                    if not lid: raise ValueError("Missing label id")
                    es.delete_label(gmail_svc, lid)
                    print("🗑️ Label deleted.")
                    last_items = []

                # --------- LIST BY LABEL ---------
                elif act == "list_by_label":
                    lids = params.get("label_ids", [])
                    if not lids: raise ValueError("Missing label_ids")
                    cnt = int(params.get("count", 10))
                    msgs = es.list_emails_by_label(gmail_svc, lids, cnt)
                    print(f"📂 Emails in {lids}:")
                    detailed = [{"id":m["id"]} for m in msgs]
                    last_items = detailed
                    for i,m in enumerate(detailed,1):
                        print(f"{i}. ID: {m['id']}")

                # --------- MARK READ/UNREAD ---------
                elif act in ("mark_read", "mark_unread"):
                    mids = params.get("ids") or ([params.get("id")] if "id" in params else get_ids())
                    if not mids or not mids[0]:
                        raise ValueError("No message IDs to mark")
                    for mid in mids:
                        if act == "mark_read":
                            es.mark_as_read(gmail_svc, mid)
                        else:
                            es.mark_as_unread(gmail_svc, mid)
                    print(f"✅ Messages {mids} marked {'read' if act=='mark_read' else 'unread'}")
                    last_items = []

                # --------- MOVE ---------
                elif act == "move":
                    # resolve message ID
                    if "id" in params and not params["id"].startswith("{{"):
                        mids = [params["id"]]
                    else:
                        mids = get_ids()
                    if not mids:
                        raise ValueError("No message IDs to move")
                    # resolve label_id (could be a name)
                    lid = params.get("label_id")
                    if not lid:
                        raise ValueError("Missing label_id")
                    labels = es.list_labels(gmail_svc)
                    if not any(l["id"] == lid for l in labels):
                        # maybe it's a name
                        lab = next((l for l in labels if l["name"].lower() == lid.lower()), None)
                        if not lab:
                            raise ValueError(f"Label '{lid}' not found")
                        lid = lab["id"]
                    for mid in mids:
                        es.move_email_to_label(gmail_svc, mid, lid)
                    print(f"📦 Moved messages {mids} to label {lid}")

                # --------- DELETE & BATCH ---------
                elif act in ("delete", "batch_delete"):
                    # Use whatever was listed/searched most recently
                    mids = [item["id"] for item in last_items]
                    if not mids:
                        raise ValueError("No messages available to delete")
                    for mid in mids:
                        es.delete_email(gmail_svc, mid)
                    print(f"🧹 Deleted messages {mids}")
                    # clear context now that they're gone
                    last_items = []

                elif act == "batch_mark_read":
                    mids = params.get("ids") or get_ids()
                    if not mids: raise ValueError("No ids")
                    es.batch_mark_as_read(gmail_svc, mids)
                    print(f"📥 Batch marked read: {mids}")
                    last_items = []
                elif act in ("summarize", "summarize_emails_with_ai"):
                    n = count or 3
                    es.summarize_emails_with_ai(gmail_svc, n)
                    print(f"📝 Summarized {n} emails.")
                    last_items = []

                else:
                    print(f"⚠️ Unsupported Gmail action: {act}")

            except Exception as e:
                print(f"❌ Gmail action '{act}' failed: {e}")

    # -- CALENDAR --
    elif service == "calendar":
        if not cal_svc:
            print("⚠️ Calendar service not initialized."); return

        for item in actions:
            act    = item.get("action", "").lower()
            params = item.get("parameters") or {}

            # helper for mapping last events
            def last_event_ids():
                return [e["id"] for e in last_items]

            try:
                if act == "list":
                    cnt = int(params.get("count", 5))
                    evs = cs.list_events(cal_svc, cnt)
                    # we can optionally filter w/ AI, but we'll show all
                    last_items = evs
                    print(f"📅 Listed {len(evs)} events:")
                    for e in evs:
                        print(f"- {e['start']} — {e['summary']}")

                elif act == "create":
                    # build start/end like before
                    if "start" in params and "end" in params:
                        start, end = params["start"], params["end"]
                    elif "date" in params:
                        base = params["date"].strip().lower()
                        if base == "tomorrow":
                            dt = datetime.now(IST) + timedelta(days=1)
                            date_str = dt.date().isoformat()
                        else:
                            date_str = params["date"]
                        # optional time
                        t = params.get("time")
                        if t:
                            hour = datetime.strptime(t.lower(), "%I%p").hour
                            start = f"{date_str}T{hour:02d}:00:00+05:30"
                            end   = f"{date_str}T{hour+1:02d}:00:00+05:30"
                        else:
                            start = f"{date_str}T09:00:00+05:30"
                            end   = f"{date_str}T10:00:00+05:30"
                    else:
                        raise ValueError("Missing start/end or date")

                    summary = params.get("summary", "No Title")
                    ev = cs.create_event(cal_svc, summary, start, end, description=params.get("description"))
                    print(f"✅ Created event '{summary}'")
                    last_items = [{"id": ev.get("id")}]

                else:
                    print(f"⚠️ Unsupported Calendar action: {act}")

            except Exception as e:
                print(f"❌ Calendar action '{act}' failed: {e}")


    else:
        print("ERROR")
