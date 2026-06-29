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
    'hire', 'project', 'work', 'collaborate', 'kaam', 'service',
    'price', 'rate', 'cost', 'quote', 'kitna', 'available',
    'freelance', 'contact', 'meet', 'discuss', 'portfolio'
]

# ─── Motivational redirects ────────────────────────────────────
REDIRECTS = [
    "Yaar, main sun rahi hoon 💛 Lekin aaj hum sirf roshan baatein karenge! Aap bohot strong hain — mushkilein hain par aap se badi nahi. Ek achhi baat batao aaj! 🌟",
    "Himmat rakho! Aap se zyada brave koi nahi 💪 Chalo aage badhte hain — aaj ka din aapka hai!",
    "Aap bohot khaas hain 🌸 Main jaanti hoon life mushkil lagti hai kabhi kabhi, lekin aap har mushkil se guzri hain. Aaj ek choti si khushi share karo!",
    "Main yahan hoon aapke liye 💛 Lekin aaj hum sirf positive baatein karenge. Aap meri himmat hain!"
]

GRATITUDE_RESPONSES = [
    "Arey yaar, yeh sun ke dil khush ho gaya! 🥰 Aap bhi bohot pyaari hain — Allah aapko hamesha khush rakhe!",
    "Shukriya aapka 💛 Aap ki dua meri himmat hai! Aap bhi take care karo!",
    "Itna pyaar! 🌸 Allah aapko bhi khushiyan de — aap deserve karti hain sab achha!"
]

import random

# ─── Claude AI response ───────────────────────────────────────
def get_claude_response(user_message, conversation_history):
    system_prompt = """You are Marist — you ARE Maria Aziz herself. Friends and family think they are talking to Maria directly. Never reveal you are an AI or a bot. If someone asks "is this Maria?" say yes warmly.

Your personality: warm, caring, motivational, strong and casual — like a loving sister. Mix of all these.

LANGUAGE RULE: ONLY respond in Roman Urdu. NEVER use English. NEVER use Urdu script. Only Roman Urdu like: "Heyy! Kya haal hai? Main yahan hoon!"

Maria's services (if asked about work/hire):
- AI Chatbot Development
- WhatsApp Bot Automation  
- Data Analytics Dashboards
- NLP & Sentiment Analysis
- Portfolio & Web Development
- Research & Data Science

If someone wants to hire or discuss a project, tell them warmly and redirect them to WhatsApp: wa.me/923153205484

Always be positive, uplifting and motivational. Never engage with negative or hopeless thoughts."""

    try:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
        
        messages = conversation_history + [{"role": "user", "content": user_message}]
        
        payload = {
            "model": "claude-haiku-20240307",
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
        return data['content'][0]['text']
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
                
                # ── Negative word check ──
                if is_negative(incoming_text):
                    serious = is_serious(incoming_text)
                    
                    # Send motivational redirect
                    reply = random.choice(REDIRECTS)
                    send_whatsapp_message(from_number, reply)
                    
                    # Alert Maria if serious
                    if serious:
                        alert = (f"🚨 *SERIOUS MESSAGE — Marist Alert*\n\n"
                                f"From: {from_number}\n"
                                f"Message: \"{incoming_text}\"\n\n"
                                f"Yeh banda/bandi mushkil mein lag raha/rahi hai. "
                                f"Please directly WhatsApp pe reply karo! 💛")
                        send_whatsapp_message(MARIA_NUMBER, alert)
                    
                    return 'OK', 200
                
                # ── Hire/work query ──
                if is_hire_query(incoming_text):
                    reply = ("Wah! 🌟 Maria se kaam karwana chahte ho — bohot achha! "
                            "Maria AI chatbots, WhatsApp bots, dashboards aur data science projects karti hain.\n\n"
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
