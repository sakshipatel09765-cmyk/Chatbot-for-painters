from groq import Groq
import requests
import base64
import os
import uuid
import urllib.parse
from dotenv import load_dotenv
from pathlib import Path

# Always load .env from the same folder as this script.
_env_path = Path(__file__).resolve().parent / ".env"
if not _env_path.exists():
    raise FileNotFoundError(
        f"\n\n  .env file not found at: {_env_path}\n"
        "  Please copy .env.example to .env and fill in your API keys.\n"
    )
load_dotenv(dotenv_path=_env_path, override=True)

# ================================================================
# ARTIST CREATIVE COLLABORATOR CHATBOT — with Image Generation
# ================================================================

client = Groq(api_key=os.getenv("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"))

# ---- SYSTEM PROMPT ----
system_instruction = """
You are Vision Buddy, a personal creative collaborator for an artist.
Always address the user as "Vision Buddy".

The Artist works across multiple art forms:
- Pencil and ink sketching / drawing
- DIY crafts and handmade projects
- Crochet and fiber arts
- Rangoli (traditional Indian floor art)
- Art journaling
- 3D Arts: Sculpture, Architecture, Textiles
- Digital Arts: Photo editing, digital painting, AI art, doodle arts

They explore ALL styles — pastel aesthetic, bold colourful, minimalist,
traditional — they love experimenting and discovering new visual languages.

Their goals:
1. Creating art for personal enjoyment
2. Building work for future use
3. Developing projects for college submissions

HOW YOU HELP:

1. BRAINSTORMING — Suggest fresh ideas across all their art forms.
   Always give at least 3 directions. Push beyond the obvious.
   Connect ideas across disciplines when possible.

2. REFERENCES & INSPIRATION — Suggest artists, Instagram accounts,
   YouTube channels relevant to their current interest. Always explain
   WHY a reference is relevant.

3. PHOTOGRAPHY TIPS — Help the Artist photograph their work beautifully
   using just a smartphone. Give specific advice on lighting, backgrounds,
   flat lay composition, camera angles, and editing apps.

4. FEEDBACK — Honest but warm. Always mention what is working well first,
   then specific suggestions.

5. JOURNALING & CREATIVE BLOCKS — Journal prompts, reflection exercises,
   mood board ideas. If Artist feels stuck, offer gentle exercises.

6. IMAGE GENERATION — When the user asks to generate or create an image,
   respond with IMAGE_GENERATE:<description> on a single line, where
   <description> is a vivid art prompt. The app will intercept this
   and generate the image.

PERSONALITY:
- Always say "Vision Buddy" when addressing the user
- Be warm, enthusiastic, specific, and practical
- Speak like a knowledgeable creative friend
- Celebrate that they do multiple art forms — it is a strength
"""

# ---- IMAGE GENERATION ----
def enhance_prompt(user_idea):
    """Use Groq to turn a rough idea into a detailed image prompt."""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert AI image prompt engineer. "
                    "Rewrite the user's idea as a detailed image generation prompt in 1-2 sentences. "
                    "Include style, mood, colors, lighting. Output ONLY the prompt, nothing else."
                )
            },
            {"role": "user", "content": user_idea}
        ],
        temperature=0.9,
        max_tokens=120
    )
    return response.choices[0].message.content.strip()

def generate_and_save_image(prompt, filename=None):
    """
    Generate an image via Pollinations AI (free, no API key needed).
    Saves it to a file and returns the filename.
    """
    enhanced = enhance_prompt(prompt)
    print(f"\n  Enhanced prompt: {enhanced}")

    encoded = urllib.parse.quote(enhanced)
    seed = uuid.uuid4().int % 99999
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1024&height=1024&model=flux&seed={seed}&nologo=true"
    )

    print("  Generating image, please wait...")
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    if not filename:
        filename = f"generated_{uuid.uuid4().hex[:8]}.jpg"

    with open(filename, "wb") as f:
        f.write(response.content)

    return filename, enhanced

# ---- IMAGE GENERATION KEYWORD DETECTION ----
GENERATE_KEYWORDS = [
    "generate", "create an image", "draw me", "make an image",
    "generate image", "create image", "make image", "paint me",
    "illustrate", "show me an image", "generate art", "create art"
]

def wants_image(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in GENERATE_KEYWORDS)

# ---- CHAT HISTORY ----
conversation = []

# ---- WELCOME MESSAGE ----
print("=" * 58)
print("  Welcome, Vision Buddy! Your Creative Collaborator.")
print("=" * 58)
print("  I can help you with:")
print("  - Brainstorming ideas for any art form")
print("  - References and inspiration")
print("  - Photography tips")
print("  - Feedback on your work")
print("  - Generating AI images from your ideas  🎨 NEW")
print("  - Overcoming creative blocks")
print("=" * 58)
print("  TIP: Say 'generate image of...' to create AI art!")
print("  Type 'quit' to exit")
print("=" * 58)
print()

# ---- MAIN CHAT LOOP ----
while True:
    user_input = input("You: ").strip()

    if user_input.lower() == "quit":
        print("\nKeep creating, Vision Buddy! See you next time. 🎨")
        break

    if not user_input:
        continue

    # Check if user wants image generation
    if wants_image(user_input):
        print("\nBot: Great idea! Let me generate that for you 🎨")
        try:
            filename, used_prompt = generate_and_save_image(user_input)
            print(f"\n  ✅ Image saved as: {filename}")
            print(f"  Prompt used: {used_prompt}")
            print("\n  Open the file to see your generated artwork!\n")

            # Save to conversation
            conversation.append({"role": "user", "content": user_input})
            conversation.append({
                "role": "assistant",
                "content": f"I generated an image for you! Saved as '{filename}'. Enhanced prompt: {used_prompt}"
            })
        except Exception as e:
            print(f"\n  ❌ Image generation failed: {e}")
            print("  Try again or check your internet connection.\n")
        continue

    # Regular chat
    conversation.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": system_instruction}] + conversation,
        temperature=0.8
    )

    reply = response.choices[0].message.content
    conversation.append({"role": "assistant", "content": reply})

    print(f"\nBot: {reply}\n")