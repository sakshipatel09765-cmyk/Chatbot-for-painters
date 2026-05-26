const messagesContainer = document.getElementById("messages");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

let currentSessionId = null;
let chatStarted = false;
let lastGeneratedPrompt = "";

// =============================================
// LANDING → CHAT TRANSITION
// =============================================

function activateChat() {
  if (chatStarted) return;
  chatStarted = true;
  document.getElementById("landing-screen").classList.add("hidden");
  document.getElementById("chat-header").style.display = "flex";
  document.getElementById("input-area").classList.add("visible");
  document.getElementById("messages").classList.add("visible");
  setTimeout(() => userInput.focus(), 400);
}

function handleLandingKey(e) {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendFromLanding(); }
}

function sendFromLanding() {
  const li = document.getElementById("landing-input");
  const text = li.value.trim();
  if (!text) return;
  li.value = "";
  userInput.value = text;
  activateChat();
  setTimeout(() => sendMessage(), 100);
}

function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  const btn = document.getElementById("sidebar-toggle");
  sidebar.classList.toggle("collapsed");
  btn.innerHTML = sidebar.classList.contains("collapsed")
    ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`
    : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 140) + "px";
}

function handleKey(e) {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

function sendQuick(text) {
  activateChat();
  userInput.value = text;
  setTimeout(() => sendMessage(), 150);
}

function botAvatarHTML() {
  return `<div class="avatar bot-avatar">🤖</div>`;
}

// =============================================
// RENDER MESSAGES
// =============================================

function addMessage(text, isUser) {
  const msg = document.createElement("div");
  msg.className = `message ${isUser ? "user-message" : "bot-message"}`;

  if (isUser) {
    msg.innerHTML = `<div class="avatar user-avatar">💗</div>
                     <div class="bubble user-bubble">${formatText(text)}</div>`;

  } else if (text.startsWith("IMAGE_FILE:")) {
    // Format: IMAGE_FILE:url1||url2|PROMPT:prompt text
    const withoutPrefix = text.replace("IMAGE_FILE:", "");
    const promptSplit = withoutPrefix.split("|PROMPT:");
    const urls = promptSplit[0].split("||").filter(Boolean);

    const imgsHtml = urls.map((u, i) => `
      <div style="display:inline-flex;flex-direction:column;gap:6px;align-items:flex-start;">
        <img src="${u}" alt="Generated art" class="generated-image"
             style="cursor:pointer;" onclick="window.open('${u}','_blank')"
             title="Click to view full size"/>
        <a href="${u}" download="visionbuddy_art_${i + 1}.jpg"
           style="display:inline-flex;align-items:center;gap:4px;
                  background:linear-gradient(135deg,#2563EB,#7C3AED);
                  color:#fff;font-size:11px;font-weight:600;
                  padding:5px 14px;border-radius:999px;
                  text-decoration:none;">⬇ Download</a>
      </div>`).join("");

    msg.innerHTML = `
      ${botAvatarHTML()}
      <div class="bubble bot-bubble" style="padding:10px;">
        <div style="display:flex;flex-wrap:wrap;gap:10px;">${imgsHtml}</div>
      </div>`;

  } else {
    msg.innerHTML = `${botAvatarHTML()}
                     <div class="bubble bot-bubble">${formatText(text)}</div>`;
  }

  messagesContainer.appendChild(msg);
  scrollToBottom();
}

// =============================================
// PROGRESS BAR (replaces typing for image gen)
// =============================================

let progressInterval = null;

function showProgressBar(label) {
  hideProgressBar();
  const msg = document.createElement("div");
  msg.className = "message bot-message";
  msg.id = "progress-msg";
  msg.innerHTML = `
    ${botAvatarHTML()}
    <div class="bubble bot-bubble" style="min-width:240px;">
      <p style="font-size:13px;margin-bottom:8px;">🎨 ${label}</p>
      <div style="background:#e8e8ec;border-radius:999px;height:6px;overflow:hidden;">
        <div id="progress-bar" style="height:100%;width:0%;
             background:linear-gradient(90deg,#2563EB,#7C3AED);
             border-radius:999px;transition:width 0.5s ease;"></div>
      </div>
      <p id="progress-pct" style="font-size:11px;color:#aaa;margin-top:5px;">0%</p>
    </div>`;
  messagesContainer.appendChild(msg);
  scrollToBottom();

  let pct = 0;
  progressInterval = setInterval(() => {
    const step = pct < 50 ? 5 : pct < 75 ? 2 : pct < 88 ? 0.8 : 0;
    pct = Math.min(pct + step, 88);
    const bar = document.getElementById("progress-bar");
    const lbl = document.getElementById("progress-pct");
    if (bar) bar.style.width = pct + "%";
    if (lbl) lbl.textContent = Math.round(pct) + "%";
  }, 300);
}

function hideProgressBar() {
  clearInterval(progressInterval);
  progressInterval = null;
  const el = document.getElementById("progress-msg");
  if (el) {
    const bar = document.getElementById("progress-bar");
    const lbl = document.getElementById("progress-pct");
    if (bar) bar.style.width = "100%";
    if (lbl) lbl.textContent = "100%";
    setTimeout(() => { if (el.parentNode) el.remove(); }, 400);
  }
}

function showTyping() {
  hideTyping();
  const msg = document.createElement("div");
  msg.className = "message bot-message";
  msg.id = "typing-indicator";
  msg.innerHTML = `${botAvatarHTML()}<div class="bubble bot-bubble typing-bubble">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span></div>`;
  messagesContainer.appendChild(msg);
  scrollToBottom();
}

function hideTyping() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

function scrollToBottom() {
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function formatText(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br/>")
    .replace(/^/, "<p>")
    .replace(/$/, "</p>");
}

// =============================================
// DETECT COUNT — how many images user wants
// =============================================

function detectCount(text) {
  const t = text.toLowerCase();
  const digitMatch = t.match(/\b([2-4])\b/);
  if (digitMatch) {
    return parseInt(digitMatch[1], 10);
  }

  const wordCounts = {
    two: 2,
    three: 3,
    four: 4,
    couple: 2,
    several: 3,
    many: 4
  };
  for (const [word, num] of Object.entries(wordCounts)) {
    if (t.includes(` ${word} `) || t.startsWith(`${word} `) || t.endsWith(` ${word}`)) {
      return num;
    }
  }

  if (t.includes("a few") || t.includes("some") || t.includes("multiple") || t.includes("variations") || t.includes("versions")) {
    return 3;
  }

  return 1;
}

// =============================================
// DETECT STYLE — what art style user wants
// =============================================

function detectStyle(text) {
  const t = text.toLowerCase();
  if (t.includes("pencil") || t.includes("sketch") || t.includes("graphite") || t.includes("hand drawn") || t.includes("line art"))
    return "pencil sketch on white paper, hand drawn graphite, fine line art, black and white, detailed cross-hatching, sketchbook style, no color";
  if (t.includes("watercolor") || t.includes("water color"))
    return "watercolor painting, soft color washes, wet on wet, flowing pigments, paper texture, painterly edges";
  if (t.includes("oil paint") || t.includes("oil painting"))
    return "oil painting on canvas, impasto thick brushstrokes, rich saturated colors, classical painting style";
  if (t.includes("charcoal"))
    return "charcoal drawing, black charcoal on white paper, smudged shading, high contrast monochrome";
  if (t.includes("ink wash") || t.includes("ink art"))
    return "ink wash painting, brush and ink, sumi-e style, minimal strokes, black ink on white paper";
  if (t.includes("cartoon") || t.includes("anime") || t.includes("illustration"))
    return "anime cartoon illustration, bold outlines, flat cel shading, vibrant colors, no photorealism";
  if (t.includes("rangoli"))
    return "traditional Indian rangoli art, vibrant powder colors, geometric symmetrical patterns, flower motifs, top-down view";
  if (t.includes("3d") || t.includes("render"))
    return "3D render, octane renderer, physically based materials, studio lighting, high detail CGI";
  if (t.includes("realistic") || t.includes("real") || t.includes("photo") || t.includes("photograph"))
    return "photorealistic, 8K resolution, RAW photo, sharp focus, professional DSLR photography, hyperrealistic";
  if (t.includes("painting") || t.includes("painted") || t.includes("acrylic"))
    return "digital painting, concept art, painterly brushwork, vibrant artistic colors";
  if (t.includes("minimal") || t.includes("minimalist"))
    return "minimalist art, clean composition, simple shapes, flat design, white background";
  if (t.includes("vintage") || t.includes("retro"))
    return "vintage retro style, film grain, muted tones, aged photograph look";
  return ""; // no style keyword — backend defaults to photorealistic
}

// =============================================
// DETECT IMAGE EDIT vs NEW GENERATION
// =============================================

function isImageRequest(text) {
  const t = text.toLowerCase();
  const keywords = [
    "generate", "create image", "make image", "draw", "illustrate",
    "create art", "image of", "picture of", "art of",
    "create a", "make a", "paint", "render", "show me"
  ];
  return keywords.some(k => t.includes(k));
}

function isImageEdit(text) {
  if (!lastGeneratedPrompt) return false;
  const t = text.toLowerCase();
  const editWords = [
    "change", "make it", "add", "remove", "background",
    "make the", "now make", "instead", "more", "less",
    "darker", "brighter", "different", "another", "same but",
    "without", "replace", "edit", "modify", "update", "but"
  ];
  return editWords.some(k => t.includes(k));
}

// =============================================
// API CALLS
// =============================================

async function callGenerateImage(prompt, lastPrompt, style, count) {
  const response = await fetch("/generate-image", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: prompt,
      last_prompt: lastPrompt,
      style: style,
      count: count,
      width: 512,
      height: 512,
      session_id: currentSessionId
    })
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error || "Image generation failed");
  }
  const data = await response.json();
  if (data.session_id) currentSessionId = data.session_id;
  return data;
}

async function callChat(message) {
  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: currentSessionId })
  });
  const data = await response.json();
  if (data.session_id) currentSessionId = data.session_id;
  return data.reply || "";
}

// =============================================
// SEND MESSAGE — main handler
// =============================================

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  activateChat();
  sendBtn.disabled = true;
  userInput.value = "";
  userInput.style.height = "auto";
  addMessage(text, true);

  const isEdit = isImageEdit(text);
  const isImg = isImageRequest(text);

  try {
    if (isImg || isEdit) {
      const count = isEdit ? 1 : detectCount(text);
      const style = isEdit ? "" : detectStyle(text);
      const label = count > 1
        ? `Generating ${count} images... (~${count * 6} sec)`
        : "Generating your image... (~8 sec)";

      showProgressBar(label);

      const result = await callGenerateImage(
        text,
        isEdit ? lastGeneratedPrompt : "",
        style,
        count
      );

      hideProgressBar();
      lastGeneratedPrompt = result.prompt_used || text;

      const urls = result.image_urls || [];
      if (urls.length === 0) {
        addMessage("❌ No images were generated. Please try again.", false);
      } else {
        addMessage(`IMAGE_FILE:${urls.join("||")}|PROMPT:${result.prompt_used}`, false);
        // Follow-up tips
        showTyping();
        const tips = await callChat(
          `You just generated ${urls.length} image(s) for: "${text}". Give 2 short tips to recreate this style.`
        );
        hideTyping();
        if (tips) addMessage(tips, false);
      }

    } else {
      showTyping();
      const reply = await callChat(text);
      hideTyping();
      addMessage(reply || "Something went wrong. Please try again.", false);
    }

  } catch (error) {
    hideTyping();
    hideProgressBar();
    addMessage(`❌ ${error.message || "Could not connect. Make sure app.py is running."}`, false);
  }

  sendBtn.disabled = false;
  userInput.focus();
  loadHistory();
}

// =============================================
// CLEAR / NEW CHAT
// =============================================

async function clearChat() {
  const res = await fetch("/clear", { method: "POST" });
  const data = await res.json();
  if (data.session_id) currentSessionId = data.session_id;
  chatStarted = false;
  lastGeneratedPrompt = "";
  messagesContainer.innerHTML = "";
  messagesContainer.classList.remove("visible");
  document.getElementById("input-area").classList.remove("visible");
  document.getElementById("chat-header").style.display = "none";
  document.getElementById("landing-screen").classList.remove("hidden");
  const li = document.getElementById("landing-input");
  if (li) { li.value = ""; li.style.height = "auto"; }
  document.querySelectorAll(".history-item").forEach(el => el.classList.remove("active"));
}

// =============================================
// CONVERSATION HISTORY
// =============================================

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function loadHistory() {
  const list = document.getElementById("history-list");
  if (!list) return;
  try {
    const res = await fetch("/get-conversations");
    const convos = await res.json();
    if (!convos.length) {
      list.innerHTML = `<p class="history-empty">No past conversations yet.</p>`;
      return;
    }
    list.innerHTML = convos.map(c => `
      <div class="history-item ${c.session_id === currentSessionId ? "active" : ""}"
           id="hist-${c.session_id}" onclick="loadConversation('${c.session_id}')">
        <div class="history-info">
          <div class="history-title">${escapeHtml(c.title)}</div>
          <div class="history-meta">${escapeHtml(c.created)} · ${c.message_count} msgs</div>
        </div>
        <button class="history-delete"
          onclick="event.stopPropagation(); deleteConversation('${c.session_id}')">×</button>
      </div>`).join("");
  } catch (e) {
    list.innerHTML = `<p class="history-empty">Could not load history.</p>`;
  }
}

async function loadConversation(sessionId) {
  try {
    const res = await fetch("/load-conversation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId })
    });
    const data = await res.json();
    if (data.error) return;

    currentSessionId = sessionId;
    messagesContainer.innerHTML = "";
    activateChat();

    data.messages.forEach(m => {
      if (m.content.startsWith("[Image generation]")) return;
      addMessage(m.content, m.role === "user");
    });

    document.querySelectorAll(".history-item").forEach(el => el.classList.remove("active"));
    const el = document.getElementById(`hist-${sessionId}`);
    if (el) el.classList.add("active");
    scrollToBottom();
  } catch (e) {
    addMessage("Could not load that conversation.", false);
  }
}

async function deleteConversation(sessionId) {
  await fetch("/delete-conversation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId })
  });
  if (sessionId === currentSessionId) clearChat();
  const el = document.getElementById(`hist-${sessionId}`);
  if (el) el.remove();
  const list = document.getElementById("history-list");
  if (list && !list.querySelector(".history-item"))
    list.innerHTML = `<p class="history-empty">No past conversations yet.</p>`;
}

// =============================================
// INIT
// =============================================

window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("chat-header").style.display = "none";
  loadHistory();
});