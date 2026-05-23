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
app.secret_key = os.getenv("FLASK_SECRET", "Sakshi's_chatbot_1523")

# Folder where generated images are saved on disk
IMAGES_DIR = Path(__file__).resolve().parent / "static" / "generated"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# ---- API CLIENTS ----
groq_client = Groq(api_key=os.getenv("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"))
_anthropic_key = os.getenv("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", "").strip()
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
    # Only keep last 20 messages to avoid token limits
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


@app.route("/generate-image", methods=["POST"])
def generate_image():
    data = request.get_json()
    user_prompt = data.get("prompt", "").strip()
    session_id = data.get("session_id", "default")
    style = data.get("style", "")
    count = max(1, min(int(data.get("count", 1)), 4))  # clamp between 1-4
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
    ]

    if count == 1:
        prompts = [base_prompt]
    else:
        # Try Groq to generate distinct prompts
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
            # Pad to count if Groq returned fewer lines
            while len(lines) < count:
                lines.append(f"{base_prompt}{variation_suffixes[len(lines) % len(variation_suffixes)]}")
            prompts = lines[:count]
        except Exception:
            prompts = [f"{base_prompt}{variation_suffixes[i % len(variation_suffixes)]}" for i in range(count)]

    # Step 3: Generate all images in parallel
    seeds = random.sample(range(1, 999999), count)

    def fetch_one(idx):
        prompt_to_use = prompts[idx]
        encoded = urllib.parse.quote(prompt_to_use)
        seed = seeds[idx]
        for model_name in ["turbo", "flux"]:
            try:
                url = (
                    f"https://image.pollinations.ai/prompt/{encoded}"
                    f"?width={width}&height={height}&model={model_name}&seed={seed}&nologo=true"
                )
                resp = requests.get(url, timeout=90)
                resp.raise_for_status()
                if len(resp.content) > 1000:  # valid image
                    return resp.content
            except Exception:
                continue
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as executor:
        futures = {executor.submit(fetch_one, i): i for i in range(count)}
        results = [None] * count
        for future in concurrent.futures.as_completed(futures):
            i = futures[future]
            results[i] = future.result()

    # Save images to disk
    image_urls = []
    for img_bytes in results:
        if img_bytes:
            fname = f"{uuid.uuid4().hex}.jpg"
            with open(IMAGES_DIR / fname, "wb") as f:
                f.write(img_bytes)
            image_urls.append(f"/static/generated/{fname}")

    if not image_urls:
        return jsonify({"error": "Image generation failed. Please try again."}), 500

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