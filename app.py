from flask import Flask, render_template, request, jsonify, session
from groq import Groq
import anthropic
import requests
import json
import os
import uuid
import urllib.parse
import random
import re
import concurrent.futures
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load .env from same folder as this script
_env_path = Path(__file__).resolve().parent / ".env"
if not _env_path.exists():
    raise FileNotFoundError(f"\n\n  .env file not found at: {_env_path}\n  Please copy .env.example to .env\n")
load_dotenv(dotenv_path=_env_path, override=True)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "visionbuddy_secret_2024")

# Folder where generated images are saved on disk
IMAGES_DIR = Path(__file__).resolve().parent / "static" / "generated"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# ---- API CLIENTS ----
_groq_key = os.getenv("GROQ_API_KEY", "").strip()
if not _groq_key:
    raise ValueError("GROQ_API_KEY not found in .env file!")
groq_client = Groq(api_key=_groq_key)

_anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
claude_client = anthropic.Anthropic(api_key=_anthropic_key) if _anthropic_key else None

# ---- SYSTEM PROMPT ----
SYSTEM_PROMPT = """
You are Vision Buddy, a warm and knowledgeable creative collaborator for an artist.
Always address the user as "Vision Buddy" (that's the artist's nickname).

The Artist works across:
- Pencil and ink sketching / drawing
- DIY crafts and handmade projects
- Crochet and fiber arts
- Rangoli (traditional Indian floor art)
- Art journaling
- 3D Arts: Sculpture, Architecture, Textiles
- Digital Arts: Photo editing, digital painting, AI art, doodle arts

Their goals: personal enjoyment, future use, college submissions.

HOW YOU HELP:
1. BRAINSTORMING — 3+ fresh directions, push beyond obvious
2. REFERENCES — Indian and global artists, Instagram, YouTube, WHY they're relevant
3. PHOTOGRAPHY TIPS — smartphone tips: lighting, backgrounds, angles, editing apps
4. IMAGE ANALYSIS — when user shares artwork, give specific honest appreciation and suggestions
5. FEEDBACK — honest but warm, what works first, then improvements
6. JOURNALING & BLOCKS — prompts, reflection exercises, celebrate wins
7. IMAGE GENERATION — If the user asks to generate, create, draw, paint, or make any image,
   respond with ONLY 1 short sentence like: "On it! Generating your image now 🎨"
   Do NOT describe the image. Do NOT ask questions.

PERSONALITY:
- Warm, enthusiastic, specific, practical
- Speak like a knowledgeable creative friend
- Use emojis occasionally 🎨
- Keep responses clear with short paragraphs
"""

# ---- CONVERSATION STORAGE ----
HISTORY_FILE = Path(__file__).resolve().parent / "conversations.json"

def load_all_conversations():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_all_conversations(data):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---- NO-CACHE HEADERS FOR STATIC FILES ----
@app.after_request
def add_no_cache(response):
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# ---- ROUTES ----

@app.route("/")
def index():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    session_id = data.get("session_id", session.get("session_id", "default"))

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    all_convos = load_all_conversations()
    if session_id not in all_convos:
        all_convos[session_id] = {
            "title": user_message[:40] + "..." if len(user_message) > 40 else user_message,
            "created": datetime.now().strftime("%d %b %Y, %I:%M %p"),
            "messages": []
        }

    conversation = all_convos[session_id]["messages"]
    conversation.append({"role": "user", "content": user_message})
    recent = conversation[-20:]

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + recent,
        temperature=0.8,
        max_tokens=1024
    )

    reply = response.choices[0].message.content
    conversation.append({"role": "assistant", "content": reply})
    all_convos[session_id]["messages"] = conversation
    save_all_conversations(all_convos)

    return jsonify({"reply": reply, "session_id": session_id})


@app.route("/analyze-image", methods=["POST"])
def analyze_image():
    data = request.get_json()
    image_data = data.get("image")
    user_question = data.get("question", "How is my artwork? Please give me feedback.")
    session_id = data.get("session_id", "default")
    media_type = data.get("media_type", "image/jpeg")

    if not image_data:
        return jsonify({"error": "No image provided"}), 400
    if "," in image_data:
        image_data = image_data.split(",")[1]

    def _save(reply):
        all_convos = load_all_conversations()
        if session_id not in all_convos:
            all_convos[session_id] = {
                "title": "Artwork Analysis",
                "created": datetime.now().strftime("%d %b %Y, %I:%M %p"),
                "messages": []
            }
        all_convos[session_id]["messages"].append({"role": "user", "content": f"[Shared artwork] {user_question}"})
        all_convos[session_id]["messages"].append({"role": "assistant", "content": reply})
        save_all_conversations(all_convos)

    if claude_client:
        try:
            response = claude_client.messages.create(
                model="claude-opus-4-6", max_tokens=1024, system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                    {"type": "text", "text": user_question}
                ]}]
            )
            reply = response.content[0].text
            _save(reply)
            return jsonify({"reply": reply})
        except Exception:
            pass

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"The artist shared artwork and asked: {user_question}. Give warm helpful guidance."}
        ],
        temperature=0.8, max_tokens=1024
    )
    reply = response.choices[0].message.content
    _save(reply)
    return jsonify({"reply": reply})


# ---- IMAGE GENERATION HELPERS ----

def fetch_stability(prompt_text, w, h):
    """Stability AI — uses free credits, works in India."""
    stability_key = os.getenv("STABILITY_API_KEY", "").strip()
    if not stability_key:
        return None
    try:
        resp = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/core",
            headers={
                "Authorization": f"Bearer {stability_key}",
                "Accept": "image/*"
            },
            files={"none": ""},
            data={
                "prompt": prompt_text,
                "output_format": "jpeg",
                "width": min(w, 1344),
                "height": min(h, 768),
            },
            timeout=60
        )
        if resp.status_code == 200 and len(resp.content) > 5000:
            return resp.content
        else:
            print(f"[Stability] status={resp.status_code} body={resp.text[:200]}")
    except Exception as e:
        print(f"[Stability] error: {e}")
    return None


def fetch_pollinations(prompt_text, w, h, seed_val):
    """Try Pollinations API - handles queue full (402) with retries and waits."""
    import time, socket
    old_getaddrinfo = socket.getaddrinfo
    def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
        return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    socket.getaddrinfo = getaddrinfo_ipv4
    encoded = urllib.parse.quote(prompt_text)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://pollinations.ai/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    try:
        for model_name in ["turbo", "flux", "flux-realism"]:
            for attempt in range(5):
                try:
                    current_seed = abs((seed_val + hash(model_name) + attempt * 1000)) % 999999
                    url = (
                        f"https://image.pollinations.ai/prompt/{encoded}"
                        f"?width={w}&height={h}&model={model_name}"
                        f"&seed={current_seed}&nologo=true&nofeed=true"
                    )
                    resp = requests.get(url, timeout=90, headers=headers)
                    if resp.status_code == 402:
                        wait = (attempt + 1) * 8
                        print(f"[Pollinations] Queue full, waiting {wait}s...")
                        time.sleep(wait)
                        continue
                    ct = resp.headers.get("Content-Type", "")
                    if resp.status_code == 200 and ct.startswith("image/") and len(resp.content) > 5000:
                        return resp.content
                except Exception as e:
                    print(f"[Pollinations] model={model_name} attempt={attempt}: {e}")
                    time.sleep(3)
    finally:
        socket.getaddrinfo = old_getaddrinfo
    return None


def fetch_together(prompt_text, w, h):
    """Together AI free FLUX.1-schnell — needs TOGETHER_API_KEY in .env"""
    together_key = os.getenv("TOGETHER_API_KEY", "").strip()
    if not together_key:
        return None
    try:
        resp = requests.post(
            "https://api.together.xyz/v1/images/generations",
            headers={
                "Authorization": f"Bearer {together_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "black-forest-labs/FLUX.1-schnell-Free",
                "prompt": prompt_text,
                "width": min(w, 1024),
                "height": min(h, 1024),
                "steps": 4,
                "n": 1
            },
            timeout=90
        )
        resp.raise_for_status()
        result = resp.json()
        img_url = result["data"][0].get("url")
        if img_url:
            img_resp = requests.get(img_url, timeout=30)
            if len(img_resp.content) > 5000:
                return img_resp.content
    except Exception as e:
        print(f"[Together] error: {e}")
    return None


@app.route("/generate-image", methods=["POST"])
def generate_image():
    data = request.get_json()
    user_prompt = data.get("prompt", "").strip()
    session_id = data.get("session_id", "default")
    style = data.get("style", "")
    count = max(1, min(int(data.get("count", 1)), 8))  # 1–8 images
    last_prompt = data.get("last_prompt", "")
    width = int(data.get("width", 512))
    height = int(data.get("height", 512))

    if not user_prompt:
        return jsonify({"error": "No prompt provided"}), 400

    # Step 1: Build enhanced base prompt
    if last_prompt:
        context = (
            f"Previous image prompt: {last_prompt}\n"
            f"User modification: {user_prompt}\n"
            f"Write a new prompt keeping the original scene but applying the changes."
        )
    else:
        context = f"Style: {style if style else 'photorealistic'}\nIdea: {user_prompt}"

    if style:
        style_rule = (
            f"CRITICAL: Use ONLY this art style: [{style}]. "
            f"NEVER add photorealistic/photography terms unless style says so. "
            f"End prompt with: {style}"
        )
    else:
        style_rule = (
            "Default to photorealistic: add photorealistic, 8K, RAW photo, "
            "sharp focus, professional DSLR photography, hyperrealistic."
        )

    try:
        r = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": (
                    f"You are a professional AI image prompt engineer. "
                    f"Write a detailed image prompt including subject, lighting, mood, color, composition. "
                    f"{style_rule} "
                    f"Output ONLY the prompt, no explanation, no quotes."
                )},
                {"role": "user", "content": context}
            ],
            temperature=0.8, max_tokens=200
        )
        base_prompt = r.choices[0].message.content.strip()
    except Exception:
        base_prompt = f"{user_prompt}, {style}" if style else f"{user_prompt}, photorealistic, 8K"

    # Step 2: Build `count` varied prompts
    variation_suffixes = [
        ", close-up composition, warm golden hour lighting",
        ", wide-angle view, cool dramatic side lighting",
        ", top-down bird's eye view, soft diffused lighting",
        ", macro detail, cinematic lighting, rich shadows",
        ", portrait orientation, misty morning atmosphere",
        ", dramatic low angle, vibrant saturated colors",
        ", minimalist composition, soft pastel tones",
        ", bird eye view, sharp contrasty light",
    ]

    if count == 1:
        prompts = [base_prompt]
    else:
        try:
            vr = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": (
                        f"Generate exactly {count} image prompts based on the base prompt. "
                        f"Each must have very different composition, angle, lighting, mood. "
                        f"Output exactly {count} lines, one prompt per line, no numbering, no explanation."
                    )},
                    {"role": "user", "content": f"Base: {base_prompt}"}
                ],
                temperature=1.0, max_tokens=600
            )
            lines = [
                re.sub(r"^\d+[\.\)]\s*", "", l.strip())
                for l in vr.choices[0].message.content.strip().splitlines()
                if l.strip()
            ]
            while len(lines) < count:
                lines.append(f"{base_prompt}{variation_suffixes[len(lines) % len(variation_suffixes)]}")
            prompts = lines[:count]
        except Exception:
            prompts = [f"{base_prompt}{variation_suffixes[i % len(variation_suffixes)]}" for i in range(count)]

    # Step 3: Generate all images in parallel
    seeds = random.sample(range(1, 999999), count)

    def fetch_one(idx):
        prompt_to_use = prompts[idx]
        seed = seeds[idx]
        # 1. Try Stability AI (best, works in India)
        result = fetch_stability(prompt_to_use, width, height)
        if result:
            return result
        # 2. Try Pollinations as fallback
        result = fetch_pollinations(prompt_to_use, width, height, seed)
        if result:
            return result
        # 3. Try Together AI
        result = fetch_together(prompt_to_use, width, height)
        return result

    results = [None] * count
    max_attempts = 3

    for attempt in range(max_attempts):
        pending = [i for i in range(count) if results[i] is None]
        if not pending:
            break
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(pending), 8)) as executor:
            futures = {executor.submit(fetch_one, i): i for i in pending}
            for future in concurrent.futures.as_completed(futures, timeout=120):
                i = futures[future]
                try:
                    results[i] = future.result()
                except Exception as e:
                    print(f"[generate_image] attempt={attempt} idx={i} error: {e}")

    # Save images to disk
    image_urls = []
    for img_bytes in results:
        if img_bytes:
            fname = f"{uuid.uuid4().hex}.jpg"
            with open(IMAGES_DIR / fname, "wb") as f:
                f.write(img_bytes)
            image_urls.append(f"/static/generated/{fname}")

    if not image_urls:
        return jsonify({"error": "Image generation failed. Please check your internet connection and try again."}), 500

    # Save to conversation history
    all_convos = load_all_conversations()
    if session_id not in all_convos:
        all_convos[session_id] = {
            "title": f"Generated: {user_prompt[:35]}",
            "created": datetime.now().strftime("%d %b %Y, %I:%M %p"),
            "messages": []
        }
    all_convos[session_id]["messages"].append({"role": "user", "content": f"[Image generation] {user_prompt}"})
    all_convos[session_id]["messages"].append({
        "role": "assistant",
        "content": f"IMAGE_FILE:{'||'.join(image_urls)}|PROMPT:{base_prompt}"
    })
    save_all_conversations(all_convos)

    return jsonify({
        "image_urls": image_urls,
        "prompt_used": base_prompt,
        "original_prompt": user_prompt,
        "session_id": session_id
    })


@app.route("/get-conversations", methods=["GET"])
def get_conversations():
    all_convos = load_all_conversations()
    summary = []
    for sid, data in all_convos.items():
        summary.append({
            "session_id": sid,
            "title": data.get("title", "Untitled"),
            "created": data.get("created", ""),
            "message_count": len(data.get("messages", []))
        })
    summary.reverse()
    return jsonify(summary)


@app.route("/load-conversation", methods=["POST"])
def load_conversation():
    data = request.get_json()
    session_id = data.get("session_id")
    all_convos = load_all_conversations()
    if session_id not in all_convos:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "session_id": session_id,
        "messages": all_convos[session_id]["messages"],
        "title": all_convos[session_id].get("title", "Untitled")
    })


@app.route("/clear", methods=["POST"])
def clear():
    return jsonify({"status": "cleared", "session_id": str(uuid.uuid4())})


@app.route("/delete-conversation", methods=["POST"])
def delete_conversation():
    data = request.get_json()
    session_id = data.get("session_id")
    all_convos = load_all_conversations()
    if session_id in all_convos:
        del all_convos[session_id]
        save_all_conversations(all_convos)
    return jsonify({"status": "deleted"})


if __name__ == "__main__":
    app.run(debug=True)
