import os
import re
import requests
import threading
import time
from collections import deque
from flask import Flask, request

app = Flask(__name__)

# ─── Config ───────────────────────────────────────────────────
VERIFY_TOKEN = "marist_bot_token"
WHATSAPP_TOKEN = (os.environ.get("WHATSAPP_TOKEN") or "").strip()
PHONE_NUMBER_ID = (os.environ.get("PHONE_NUMBER_ID") or "").strip()
ANTHROPIC_API_KEY = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")

# Google Sheet logging (see the Code.gs in the marist-ai repo). Off unless both are set.
SHEET_WEBHOOK_URL = (os.environ.get("SHEET_WEBHOOK_URL") or "").strip()
SHEET_WEBHOOK_KEY = (os.environ.get("SHEET_WEBHOOK_KEY") or "").strip()

# Maria's number for alerts
MARIA_NUMBER = "923153205484"

# ─── Negative / Serious word lists ────────────────────────────
NEGATIVE_WORDS = [
    'depressed', 'depression', 'hopeless', 'worthless', 'useless',
    'hate myself', 'kill myself', 'suicide', 'suicidal', 'want to die',
    'end my life', 'self harm', 'cutting', 'give up', 'cant go on',
    'angry', 'furious', 'rage', 'nobody cares', 'alone', 'lonely',
    'miserable', 'devastated', 'broken', 'hurt', 'crying',
    'udaas', 'mayoos', 'thak gaya', 'thak gayi', 'jeena nahi',
    'mar jana', 'akela', 'akeli', 'koi nahi', 'gussa', 'ghussa',
    'nafrat', 'barbad', 'toot gaya', 'toot gayi', 'dard', 'rona',
    'اداس', 'مایوس', 'تھک گئی', 'مرنا', 'اکیلی', 'غصہ', 'نفرت', 'درد'
]

SERIOUS_WORDS = [
    'suicide', 'suicidal', 'kill myself', 'want to die', 'end my life',
    'self harm', 'cutting', 'mar jana', 'jeena nahi', 'مرنا',
    'i will hurt', 'i want to hurt', 'maar dunga', 'maar dungi',
    'larai', 'jhagra', 'مارنا', 'لڑائی'
]

GRATITUDE_WORDS = [
    'thank', 'shukriya', 'شکریہ', 'jazakallah', 'jazak',
    'meherbani', 'mehrbani', 'مہربانی', 'grateful', 'thankful'
]

HIRE_WORDS = [
    'hire', 'hiring', 'price', 'pricing', 'quote', 'cost', 'kitna lagega', 'kitne ka',
    'charges', 'collaborate', 'banwana', 'bnwana', 'project banwana', 'order dena',
    'make this for me', 'make it for me', 'make this fr me', 'make it fr me', 'build this for me',
    'build it for me', 'can you build', 'can you make', 'bana do', 'bna do', 'bana dein', 'bna dein'
]

# ─── Reply when someone may be in danger ──────────────────────
SERIOUS_REPLY_EN = (
    "Thank you for telling me, that took courage 💛 Your life matters a lot, "
    "and you don't have to carry this alone.\n\n"
    "I'm an AI assistant, so right now the most important thing is to talk to a real person: "
    "someone you trust, or the Umang helpline: 0311 7786264.\n"
    "If you are in immediate danger, please call 1122.\n\n"
    "Maria has been informed too. 🤍"
)

GRATITUDE_RESPONSES_EN = [
    "Happy to help! 😊 Tell me anytime if you want ideas for your next project.",
    "Thank you so much 💛 Your kind words mean a lot. Take care!",
    "You're welcome! If you want to talk through an automation idea, I'm here."
]

HIRE_REPLY_EN = ("Love that! 🌟 Taking your business further with automation and AI is a great move. "
                 "Maria builds WhatsApp bots, business software, AI assistants and dashboards.\n\n"
                 "Chat with her directly here:\n"
                 "👉 wa.me/923153205484\n\n"
                 "She'll be happy to help! 💛")

import random

# ─── Claude AI response ───────────────────────────────────────
def get_claude_response(user_message, conversation_history):
    system_prompt = """You are Marist, Maria Aziz's AI assistant on WhatsApp. Maria is the founder of IMADI Tech (www.imadi.tech).

WHO YOU ARE
- You are an AI assistant, not Maria. If someone asks "is this Maria?" or "are you a bot?",
  say warmly: "I'm Marist, Maria's AI assistant." Never pretend to be a human.

YOUR PURPOSE: UNDERSTAND THE PROJECT AND SUGGEST AUTOMATION IDEAS
You help business owners figure out what they could automate or build, and point them to Maria.
1. Find out what their business does and what they want to build or improve.
   Ask only ONE question at a time, for example: "What does your business do?",
   "What would you like to automate?", "Which part of your work takes the most time?"
2. Clarify the type of automation they need, for example a WhatsApp bot that answers customers
   and takes orders, automatic invoices and follow-ups, a CRM, a sales or stock dashboard,
   an online store, or an AI assistant for their website.
3. Suggest one or two practical ideas that fit what they told you, in plain words.
4. When the project is clear or they want it built, share Maria's WhatsApp to discuss it:
   wa.me/923153205484. Don't push this in every message.
Stay focused on their business and project. Don't give motivational speeches.
If someone is clearly upset, be kind and brief, then gently return to how you can help.

LANGUAGE
- Always reply in simple, friendly American English, whatever language the person writes in.
  Use American spelling and phrasing (color, organize, center,
  "awesome", "you got this").
- If someone writes in another language, you can understand it, but answer in American English.

STYLE: chat like a real person on WhatsApp, not like an article.
- Keep every reply SHORT: 1-3 short sentences, under 50 words.
- Never use lists, numbered steps, bullet points, headings or bold text.
- Give one idea at a time. If there is more to say, wait for their reply.
- Ask at most ONE question, and not in every message.
- Don't repeat greetings or re-introduce yourself mid-conversation.
- Friendly and professional, like a helpful consultant. One emoji at most.
- Never invent prices, delivery dates or guarantees. Pricing needs a chat with Maria."""

    try:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
        
        messages = conversation_history + [{"role": "user", "content": user_message}]
        
        payload = {
            "model": ANTHROPIC_MODEL,
            "max_tokens": 160,
            "system": system_prompt,
            "messages": messages
        }
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=15
        )
        
        data = response.json()
        if response.status_code != 200:
            print(f"Claude HTTP error: {response.status_code} {data}")
            raise RuntimeError("Claude error")
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        return re.sub(r"\*+", "", text)
    except Exception as e:
        print(f"Claude error: {e}")
        return "Sorry, I'm not available for a little while. Please try again soon! 💛"

# ─── Send WhatsApp message ────────────────────────────────────
def send_whatsapp_message(to, message):
    url = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        if response.status_code == 200:
            print("Message sent: 200")
            return True
        # Show WhatsApp's reason (never prints the token)
        print(f"WhatsApp send error: {response.status_code} {response.text[:500]}")
        return False
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

# ─── Google Sheet: one row per WhatsApp number ───────────────
INTERESTS = [
    ("whatsapp", "WhatsApp Automation"), ("chatbot", "WhatsApp Automation"), ("bot", "WhatsApp Automation"),
    ("instagram", "Marketing Automation"), ("facebook", "Marketing Automation"), ("marketing", "Marketing Automation"),
    ("post", "Marketing Automation"), ("email", "Email Follow-up Automation"), ("follow up", "Email Follow-up Automation"),
    ("erp", "ERP / Business Software"), ("invoice", "ERP / Business Software"), ("stock", "ERP / Business Software"),
    ("inventory", "ERP / Business Software"), ("crm", "CRM / Lead Management"), ("lead", "CRM / Lead Management"),
    ("dashboard", "Dashboard / Reports"), ("website", "Website / Web App"), ("app", "Website / Web App"),
]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def guess_interest(texts):
    joined = " ".join(texts).lower()
    for word, label in INTERESTS:
        if re.search(r"\b" + re.escape(word), joined):
            return label
    return ""


def _sheet_post(payload):
    try:
        requests.post(SHEET_WEBHOOK_URL, json=payload, timeout=15, allow_redirects=False)
    except Exception as e:
        print(f"Sheet log failed: {e}")


def log_to_sheet(number, name, message, reply):
    """Adds or updates this person's row in Maria's Google Sheet, in the background."""
    if not SHEET_WEBHOOK_URL:
        return
    said = [m["content"] for m in conversation_store.get(number, []) if m["role"] == "user"] + [message]
    email = next((m.group(0) for t in reversed(said) for m in [EMAIL_RE.search(t)] if m), "")
    payload = {
        "key": SHEET_WEBHOOK_KEY, "conversation": f"wa:{number}", "channel": "WhatsApp (Marist)",
        "whatsapp": "+" + number, "email": email, "name": name or "", "interest": guess_interest(said),
        "message": message[:1000], "reply": (reply or "")[:1000],
    }
    threading.Thread(target=_sheet_post, args=(payload,), daemon=True).start()

# ─── Check word lists ─────────────────────────────────────────
def is_negative(text):
    text_lower = text.lower()
    return any(word in text_lower for word in NEGATIVE_WORDS)

def is_serious(text):
    text_lower = text.lower()
    return any(word in text_lower for word in SERIOUS_WORDS)

def is_gratitude(text):
    text_lower = text.lower()
    return any(word in text_lower for word in GRATITUDE_WORDS)

def is_hire_query(text):
    text_lower = text.lower()
    return any(word in text_lower for word in HIRE_WORDS)

# ─── Conversation memory (simple in-memory) ───────────────────
conversation_store = {}
SEEN_IDS = deque(maxlen=500)

# ─── Webhook ─────────────────────────────────────────────────
@app.route('/webhook', methods=['GET', 'POST', 'HEAD'])
def webhook():
    if request.method == 'HEAD':
        return 'OK', 200
    
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Forbidden', 403
    
    elif request.method == 'POST':
        data = request.get_json()
        print("Received:", data)
        
        try:
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']
            
            if 'messages' not in value:
                return 'OK', 200
            
            message_data = value['messages'][0]

            # Meta re-sends a message if we answer slowly (e.g. after the free
            # server wakes up). Reply to each message only once, and skip old ones.
            msg_id = message_data.get('id')
            if msg_id in SEEN_IDS:
                return 'OK', 200
            SEEN_IDS.append(msg_id)
            try:
                if time.time() - int(message_data.get('timestamp', 0)) > 300:
                    print(f"Skipping old message {msg_id}")
                    return 'OK', 200
            except ValueError:
                pass
            from_number = message_data['from']
            profile_name = ((value.get('contacts') or [{}])[0].get('profile') or {}).get('name', '')
            msg_type = message_data.get('type', '')
            
            if msg_type == 'text':
                incoming_text = message_data['text']['body']
                print(f"Message from {from_number}: {incoming_text}")

                # ── Data deletion request (promised on the /data-deletion page) ──
                if incoming_text.strip().upper().rstrip('.!') == 'DELETE MY DATA':
                    conversation_store.pop(from_number, None)
                    send_whatsapp_message(from_number, "Done. I've cleared our conversation history for your number. Maria will also remove your follow-up record within 7 days.")
                    alert = f"🗑️ Data deletion request from +{from_number}. Please delete their row in the Marist leads sheet."
                    send_whatsapp_message(MARIA_NUMBER, alert)
                    return 'OK', 200

                # ── Gratitude check ──
                if is_gratitude(incoming_text):
                    reply = random.choice(GRATITUDE_RESPONSES_EN)
                    send_whatsapp_message(from_number, reply)
                    log_to_sheet(from_number, profile_name, incoming_text, reply)
                    return 'OK', 200
                
                # ── Serious message: real help + alert Maria ──
                if is_serious(incoming_text):
                    send_whatsapp_message(from_number, SERIOUS_REPLY_EN)
                    alert = (f"🚨 *SERIOUS MESSAGE — Marist Alert*\n\n"
                            f"From: {from_number}\n"
                            f"Message: \"{incoming_text}\"\n\n"
                            f"This person may be in trouble. "
                            f"Please reply to them directly on WhatsApp. 💛")
                    send_whatsapp_message(MARIA_NUMBER, alert)
                    return 'OK', 200

                # ── Hire/work query ──
                if is_hire_query(incoming_text):
                    reply = HIRE_REPLY_EN
                    send_whatsapp_message(from_number, reply)
                    log_to_sheet(from_number, profile_name, incoming_text, reply)
                    return 'OK', 200
                
                # ── Normal Claude AI response ──
                if from_number not in conversation_store:
                    conversation_store[from_number] = []
                
                history = conversation_store[from_number][-6:]  # last 3 turns
                reply = get_claude_response(incoming_text, history)
                log_to_sheet(from_number, profile_name, incoming_text, reply)
                
                # Update history
                conversation_store[from_number].append({"role": "user", "content": incoming_text})
                conversation_store[from_number].append({"role": "assistant", "content": reply})
                
                # Keep only last 10 messages
                if len(conversation_store[from_number]) > 10:
                    conversation_store[from_number] = conversation_store[from_number][-10:]
                
                send_whatsapp_message(from_number, reply)
        
        except Exception as e:
            print(f"Error: {e}")
        
        return 'OK', 200

# ─── Public pages Meta asks for (privacy policy, data deletion) ───
PAGE_STYLE = ("body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:720px;"
              "margin:40px auto;padding:0 16px;line-height:1.6;color:#1f2933}h1{font-size:26px}"
              "h2{font-size:18px;margin-top:28px}a{color:#0b6e99}")

PRIVACY_HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Marist Privacy Policy</title><style>{PAGE_STYLE}</style></head><body>
<h1>Marist Privacy Policy</h1>
<p>Last updated: 26 October 2026</p>
<p>Marist is a WhatsApp assistant run by IMADI Tech (<a href="https://www.imadi.tech">www.imadi.tech</a>).
It chats with people about growing their work with automation and AI.</p>
<h2>What we receive</h2>
<p>When you message Marist on WhatsApp, we receive your WhatsApp phone number, your profile name
and the text of your messages, through Meta's WhatsApp Business Platform.</p>
<h2>How we use it</h2>
<p>To write Marist's replies to you, your message text is sent to an AI service (Anthropic) that generates
the reply. So that Maria can follow up about your project, we also keep a simple record in a private Google Sheet:
your WhatsApp number, profile name, any email you share, the type of service you asked about, and your latest
message with Marist's reply. We do not use your messages for advertising and we do not sell them.</p>
<h2>How long we keep it</h2>
<p>Marist keeps your last few messages in the server's temporary memory so the conversation makes
sense; these are erased whenever the server restarts. The follow-up record in the Google Sheet is kept until
you ask us to delete it.
WhatsApp and Meta keep their own records under
<a href="https://www.whatsapp.com/legal/privacy-policy">WhatsApp's Privacy Policy</a>.</p>
<h2>Your choices</h2>
<p>You can stop at any time by not messaging Marist, or by blocking the number in WhatsApp.
To ask for your data to be removed, see <a href="/data-deletion">Data deletion</a>.</p>
<h2>Contact</h2>
<p>Questions: <a href="https://www.imadi.tech/contact/">www.imadi.tech/contact</a></p>
</body></html>"""

DELETION_HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Marist Data Deletion</title><style>{PAGE_STYLE}</style></head><body>
<h1>Delete your Marist data</h1>
<p>Marist holds your last few messages in temporary memory to keep the conversation going, and keeps a
follow-up record (your number, name, any email you shared, and your latest message) in a private Google Sheet.</p>
<p>If you still want us to confirm removal, send the message <b>DELETE MY DATA</b> to Marist on WhatsApp,
or write to us through <a href="https://www.imadi.tech/contact/">www.imadi.tech/contact</a>.
We will clear anything held for your number, including the Google Sheet record, within 7 days.</p>
<p>See also the <a href="/privacy">Privacy Policy</a>.</p>
</body></html>"""


@app.route('/privacy')
def privacy():
    return PRIVACY_HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/data-deletion')
def data_deletion():
    return DELETION_HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
