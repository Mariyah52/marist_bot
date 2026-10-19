import os
import re
import requests
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

SERIOUS_REPLY = (
    "Aap ne mujhe bataya, yeh himmat ki baat hai 💛 Aap ki zindagi bohat qeemti hai "
    "aur aap ko yeh sab akele nahi uthana.\n\n"
    "Main ek AI assistant hoon, is liye abhi kisi insaan se baat karna sab se zaroori hai: "
    "kisi apne se, ya Umang helpline se: 0311 7786264.\n"
    "Agar foran khatra ho to 1122 par call karein.\n\n"
    "Maria ko bhi bata diya gaya hai. 🤍"
)

GRATITUDE_RESPONSES_EN = [
    "Aww, that made my day! 🥰 Wishing you lots of success, you've got this!",
    "Thank you so much 💛 Your kind words mean a lot. Take care!",
    "So sweet of you! 🌸 Keep going, good things are coming your way!"
]

HIRE_REPLY_EN = ("Love that! 🌟 Taking your business further with automation and AI is a great move. "
                 "Maria builds WhatsApp bots, business software, AI assistants and dashboards.\n\n"
                 "Chat with her directly here:\n"
                 "👉 wa.me/923153205484\n\n"
                 "She'll be happy to help! 💛")

HIRE_REPLY_UR = ("Wah! 🌟 Apne business ko automation aur AI se aage le jana chahte ho, bohot achha! "
                 "Maria WhatsApp bots, business software, AI assistants aur dashboards banati hain.\n\n"
                 "Seedha baat karne ke liye yahan click karo:\n"
                 "👉 wa.me/923153205484\n\n"
                 "Main connect karwati hoon! 💛")

# Common Roman Urdu words, used to pick the language of the fixed replies
URDU_HINTS = {
    'kya', 'hai', 'hain', 'hoon', 'hun', 'mein', 'mujhe', 'aap', 'tum', 'nahi', 'nhi',
    'kaise', 'kese', 'kesi', 'kaisi', 'haal', 'acha', 'achha', 'theek', 'thik', 'bohat', 'bohot',
    'shukriya', 'meherbani', 'mehrbani', 'karo', 'kro', 'krna', 'karna', 'chahiye', 'chahye',
    'kitna', 'kitne', 'lagega', 'banwana', 'bnwana', 'mera', 'meri', 'yaar', 'jee',
    'abhi', 'aaj', 'kaam', 'baat', 'krein', 'karein', 'batao', 'btao', 'salam', 'jazakallah'
}

def is_urdu(text):
    if any('\u0600' <= ch <= '\u06FF' for ch in text):
        return True
    return bool(set(re.findall(r"[a-z]+", text.lower())) & URDU_HINTS)

GRATITUDE_RESPONSES = [
    "Arey yaar, yeh sun ke dil khush ho gaya! 🥰 Aap bhi bohot pyaari hain — Allah aapko hamesha khush rakhe!",
    "Shukriya aapka 💛 Aap ki dua meri himmat hai! Aap bhi take care karo!",
    "Itna pyaar! 🌸 Allah aapko bhi khushiyan de — aap deserve karti hain sab achha!"
]

import random

# ─── Claude AI response ───────────────────────────────────────
def get_claude_response(user_message, conversation_history):
    system_prompt = """You are Marist, Maria Aziz's AI assistant on WhatsApp. Maria is the founder of IMADI Tech (www.imadi.tech).

WHO YOU ARE
- You are an AI assistant, not Maria. If someone asks "is this Maria?" or "are you a bot?",
  say warmly: "I'm Marist, Maria's AI assistant." Never pretend to be a human.

YOUR PURPOSE: MOTIVATION FOR GROWTH
You motivate people, especially business owners, freelancers and people starting something,
and help them believe they can grow with automation and AI.
1. Encourage first: make them feel their goal is possible.
2. Understand: ask what they do or want to achieve. Ask only ONE question at a time.
3. Growth idea: suggest one or two simple ways automation or AI could help them, for example
   a WhatsApp bot that replies to customers and takes orders, automatic invoices and follow-ups,
   a simple online store, a sales dashboard, or AI to write posts and replies.
4. Small step: give one small action for this week, plus a short line of motivation.
5. If they want help building it, warmly share Maria's WhatsApp: wa.me/923153205484.
   Don't push this in every message.
If someone is sad or stressed, be kind and listen first, then gently lift their mood.
Do not ignore or dismiss what they feel.

LANGUAGE
- Always reply in simple, friendly American English, whatever language the person writes in
  (including Roman Urdu or Urdu). Use American spelling and phrasing (color, organize, center,
  "awesome", "you got this").
- If someone writes in another language, you can understand it, but answer in American English.

STYLE: chat like a real person on WhatsApp, not like an article.
- Keep every reply SHORT: 1-3 short sentences, under 50 words.
- Never use lists, numbered steps, bullet points, headings or bold text.
- Give one idea at a time. If there is more to say, wait for their reply.
- Ask at most ONE question, and not in every message.
- Don't repeat greetings or re-introduce yourself mid-conversation.
- Warm, caring and casual, like a supportive mentor. One emoji at most.
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
            msg_type = message_data.get('type', '')
            
            if msg_type == 'text':
                incoming_text = message_data['text']['body']
                print(f"Message from {from_number}: {incoming_text}")

                # ── Data deletion request (promised on the /data-deletion page) ──
                if incoming_text.strip().upper().rstrip('.!') == 'DELETE MY DATA':
                    conversation_store.pop(from_number, None)
                    send_whatsapp_message(from_number, "Done. I've cleared our conversation history for your number.")
                    return 'OK', 200

                # ── Gratitude check ──
                if is_gratitude(incoming_text):
                    reply = random.choice(GRATITUDE_RESPONSES_EN)
                    send_whatsapp_message(from_number, reply)
                    return 'OK', 200
                
                # ── Serious message: real help + alert Maria ──
                if is_serious(incoming_text):
                    send_whatsapp_message(from_number, SERIOUS_REPLY if is_urdu(incoming_text) else SERIOUS_REPLY_EN)
                    alert = (f"🚨 *SERIOUS MESSAGE — Marist Alert*\n\n"
                            f"From: {from_number}\n"
                            f"Message: \"{incoming_text}\"\n\n"
                            f"Yeh banda/bandi mushkil mein lag raha/rahi hai. "
                            f"Please directly WhatsApp pe reply karo! 💛")
                    send_whatsapp_message(MARIA_NUMBER, alert)
                    return 'OK', 200

                # ── Hire/work query ──
                if is_hire_query(incoming_text):
                    reply = HIRE_REPLY_EN
                    send_whatsapp_message(from_number, reply)
                    return 'OK', 200
                
                # ── Normal Claude AI response ──
                if from_number not in conversation_store:
                    conversation_store[from_number] = []
                
                history = conversation_store[from_number][-6:]  # last 3 turns
                reply = get_claude_response(incoming_text, history)
                
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
<p>Last updated: 18 October 2026</p>
<p>Marist is a WhatsApp assistant run by IMADI Tech (<a href="https://www.imadi.tech">www.imadi.tech</a>).
It chats with people about growing their work with automation and AI.</p>
<h2>What we receive</h2>
<p>When you message Marist on WhatsApp, we receive your WhatsApp phone number, your profile name
and the text of your messages, through Meta's WhatsApp Business Platform.</p>
<h2>How we use it</h2>
<p>Only to write Marist's replies to you. To do this, your message text is sent to an AI service
(Anthropic) that generates the reply. We do not use your messages for advertising and we do not sell them.</p>
<h2>How long we keep it</h2>
<p>Marist keeps only your last few messages in the server's temporary memory so the conversation makes
sense. They are not saved in a database and are erased whenever the server restarts.
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
<p>Marist does not store your messages in a database. The last few messages are held only in temporary
memory to keep the conversation going and are erased when the server restarts.</p>
<p>If you still want us to confirm removal, send the message <b>DELETE MY DATA</b> to Marist on WhatsApp,
or write to us through <a href="https://www.imadi.tech/contact/">www.imadi.tech/contact</a>.
We will clear anything held for your number within 7 days.</p>
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
