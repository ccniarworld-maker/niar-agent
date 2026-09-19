import os
import re
import json
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
GEMINI_API = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"

OFFSET_FILE = "offset.txt"


def get_offset():
    if os.path.exists(OFFSET_FILE):
        content = open(OFFSET_FILE).read().strip()
        return int(content) if content else 0
    return 0


def save_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))


def get_updates(offset):
    r = requests.get(f"{TG_API}/getUpdates", params={"offset": offset, "timeout": 5})
    return r.json().get("result", [])


def send_message(text):
    requests.post(f"{TG_API}/sendMessage", data={"chat_id": CHAT_ID, "text": text[:4000]})


def ask_gemini(prompt):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(GEMINI_API, json=body)
    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return f"Gemini error: {json.dumps(data)[:500]}"


def clean_code(text):
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"```$", "", text)
    return text.strip()


def handle_website(task_text):
    prompt = (
        f'Generate a complete, polished, single-file HTML website for this request: "{task_text}"\n'
        "Include inline CSS and JS in the same file. Make it visually modern and responsive.\n"
        "Return ONLY raw HTML code, no markdown code fences, no explanation."
    )
    raw = ask_gemini(prompt)
    if raw.startswith("Gemini error:"):
        send_message(f"❌ {raw}")
        return
    html = clean_code(raw)
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    send_message("✅ Website generated -> public/index.html. Vercel will auto-deploy in ~1 min.")


def handle_post(task_text):
    prompt = (
        f'Write a short, catchy social media caption with 3-5 relevant hashtags for: "{task_text}"\n'
        "Return ONLY the caption text, nothing else."
    )
    caption = ask_gemini(prompt).strip()
    if caption.startswith("Gemini error:"):
        send_message(f"❌ {caption}")
        return
    img_prompt = re.sub(r"\s+", "%20", task_text.strip())
    image_url = f"https://image.pollinations.ai/prompt/{img_prompt}"
    send_message(f"📝 Caption:\n{caption}\n\n🖼️ Image:\n{image_url}")


def classify(task_text):
    t = task_text.lower()
    website_kw = ["website", "site", "webpage", "ওয়েবসাইট", "সাইট", "পেজ"]
    post_kw = ["post", "caption", "পোস্ট", "ক্যাপশন", "ছবি"]
    if any(k in t for k in website_kw):
        return "website"
    if any(k in t for k in post_kw):
        return "post"
    return "chat"


def handle_chat(task_text):
    send_message(ask_gemini(task_text))


def main():
    offset = get_offset()
    updates = get_updates(offset)
    for u in updates:
        offset = u["update_id"] + 1
        msg = u.get("message", {})
        text = msg.get("text", "")
        if not text or text.startswith("/start"):
            continue
        kind = classify(text)
        if kind == "website":
            handle_website(text)
        elif kind == "post":
            handle_post(text)
        else:
            handle_chat(text)
    save_offset(offset)


if __name__ == "__main__":
    main()
