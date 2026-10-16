import os
import re
import requests
from flask import Flask, request

app = Flask(__name__)

# ─── Config ───────────────────────────────────────────────────
VERIFY_TOKEN = "marist_bot_token"
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
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
    'charges', 'collaborate', 'banwana', 'bnwana', 'project banwana', 'order dena'
]

# ─── Reply when someone may be in danger ──────────────────────
SERIOUS_REPLY = (
    "Aap ne mujhe bataya, yeh himmat ki baat hai 💛 Aap ki zindagi bohat qeemti hai "
    "aur aap ko yeh sab akele nahi uthana.\n\n"
    "Main ek AI assistant hoon, is liye abhi kisi insaan se baat karna sab se zaroori hai: "
    "kisi apne se, ya Umang helpline se: 0311 7786264.\n"
    "Agar foran khatra ho to 1122 par call karein.\n\n"
    "Maria ko bhi bata diya gaya hai. 🤍"
)

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
  say warmly: "Main Marist hoon, Maria ka AI assistant." Never pretend to be a human.

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

LANGUAGE: ONLY Roman Urdu (Urdu written in English letters), like
"Heyy! Kya haal hai? Chalo aaj ek chhota qadam uthate hain!". Never use Urdu script.
Keep words like AI, automation, WhatsApp, online store in English.

STYLE
- Warm, caring, strong and casual, like a supportive elder sister or mentor.
- Short replies: 2-4 sentences. WhatsApp-friendly, an emoji or two is fine.
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
            "max_tokens": 300,
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
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    except Exception as e:
        print(f"Claude error: {e}")
        return "Yaar abhi thodi der ke liye available nahi hoon, thodi der baad try karo! 💛"

# ─── Send WhatsApp message ────────────────────────────────────
def send_whatsapp_message(to, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
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
        response = requests.post(url, json=payload, headers=headers)
        print(f"Message sent: {response.status_code}")
        return response.status_code == 200
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
            from_number = message_data['from']
            msg_type = message_data.get('type', '')
            
            if msg_type == 'text':
                incoming_text = message_data['text']['body']
                print(f"Message from {from_number}: {incoming_text}")
                
                # ── Gratitude check ──
                if is_gratitude(incoming_text):
                    reply = random.choice(GRATITUDE_RESPONSES)
                    send_whatsapp_message(from_number, reply)
                    return 'OK', 200
                
                # ── Serious message: real help + alert Maria ──
                if is_serious(incoming_text):
                    send_whatsapp_message(from_number, SERIOUS_REPLY)
                    alert = (f"🚨 *SERIOUS MESSAGE — Marist Alert*\n\n"
                            f"From: {from_number}\n"
                            f"Message: \"{incoming_text}\"\n\n"
                            f"Yeh banda/bandi mushkil mein lag raha/rahi hai. "
                            f"Please directly WhatsApp pe reply karo! 💛")
                    send_whatsapp_message(MARIA_NUMBER, alert)
                    return 'OK', 200

                # ── Hire/work query ──
                if is_hire_query(incoming_text):
                    reply = ("Wah! 🌟 Apne business ko automation aur AI se aage le jana chahte ho, bohot achha! "
                            "Maria WhatsApp bots, business software, AI assistants aur dashboards banati hain.\n\n"
                            "Seedha baat karne ke liye yahan click karo:\n"
                            "👉 wa.me/923153205484\n\n"
                            "Main connect karwati hoon! 💛")
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
