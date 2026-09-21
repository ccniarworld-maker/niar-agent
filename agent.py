import os
import re
import json
import time
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
OPENROUTER_KEY = os.environ["OPENROUTER_API_KEY"]

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
OPENROUTER_API = "https://openrouter.ai/api/v1/chat/completions"

# Free AI models
OPENROUTER_MODELS = [
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
    "cohere/north-mini-code:free",
    "openrouter/free",
]

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
    try:
        r = requests.get(
            f"{TG_API}/getUpdates",
            params={"offset": offset, "timeout": 5},
            timeout=15
        )
        return r.json().get("result", [])
    except Exception:
        return []


def send_message(text):
    try:
        requests.post(
            f"{TG_API}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": text[:4000]
            },
            timeout=15
        )
    except Exception:
        pass


def ask_ai(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://niar-agent.vercel.app",
        "X-Title": "MHN's Agent",
    }

    body = {
        "models": OPENROUTER_MODELS,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
    }

    last_error = None

    # Try up to 3 times
    for attempt in range(3):

        try:
            r = requests.post(
                OPENROUTER_API,
                headers=headers,
                json=body,
                timeout=180
            )

            data = r.json()

            # Successful response
            if r.status_code == 200:
                try:
                    content = data["choices"][0]["message"]["content"]

                    if content:
                        return content

                except Exception:
                    last_error = data

            else:
                last_error = data

                # Rate limit / temporary provider overload
                if r.status_code in [429, 502, 503, 504]:
                    time.sleep(5)
                    continue

                # Authentication or other permanent error
                return f"AI error: {json.dumps(data)[:1000]}"

        except Exception as e:
            last_error = str(e)
            time.sleep(3)

    return f"AI error: {json.dumps(last_error)[:1000]}"


def clean_code(text):
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"```$", "", text)
    return text.strip()


def handle_website(task_text):
    prompt = (
        f'Generate a complete, polished, single-file HTML website '
        f'for this request: "{task_text}"\n\n'

        "Requirements:\n"
        "- Return ONLY raw HTML code.\n"
        "- No markdown code fences.\n"
        "- No explanation outside the HTML.\n"
        "- Include all CSS inside <style>.\n"
        "- Include all JavaScript inside <script>.\n"
        "- Make the design modern and professional.\n"
        "- Make it fully responsive for desktop and mobile.\n"
        "- Add smooth animations and useful interactions.\n"
        "- Do not use a backend.\n"
        "- Make sure the HTML can run directly as index.html."
    )

    raw = ask_ai(prompt)

    if raw.startswith("AI error:"):
        send_message(f"❌ {raw}")
        return

    html = clean_code(raw)

    os.makedirs("public", exist_ok=True)

    with open(
        "public/index.html",
        "w",
        encoding="utf-8"
    ) as f:
        f.write(html)

    send_message(
        "✅ Website generated!\n\n"
        "📁 public/index.html\n"
        "🚀 Vercel will auto-deploy shortly."
    )


def handle_post(task_text):
    prompt = (
        f'Write a short, catchy social media caption '
        f'with 3-5 relevant hashtags for: "{task_text}"\n'
        "Return ONLY the caption text, nothing else."
    )

    caption = ask_ai(prompt).strip()

    if caption.startswith("AI error:"):
        send_message(f"❌ {caption}")
        return

    img_prompt = re.sub(
        r"\s+",
        "%20",
        task_text.strip()
    )

    image_url = (
        f"https://image.pollinations.ai/prompt/{img_prompt}"
    )

    send_message(
        f"📝 Caption:\n{caption}\n\n"
        f"🖼️ Image:\n{image_url}"
    )


def classify(task_text):
    t = task_text.lower()

    website_kw = [
        "website",
        "site",
        "webpage",
        "ওয়েবসাইট",
        "সাইট",
        "পেজ"
    ]

    post_kw = [
        "post",
        "caption",
        "পোস্ট",
        "ক্যাপশন",
        "ছবি"
    ]

    if any(k in t for k in website_kw):
        return "website"

    if any(k in t for k in post_kw):
        return "post"

    return "chat"


def handle_chat(task_text):
    answer = ask_ai(task_text)
    send_message(answer)


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
