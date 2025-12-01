const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const sendButtonEl = document.getElementById("send-button");

let conversation = [];

function appendSystem(text) {
  const banner = document.createElement("div");
  banner.className = "system-message";
  banner.textContent = text;
  messagesEl.appendChild(banner);
}

function appendError(text) {
  const banner = document.createElement("div");
  banner.className = "error-banner";
  banner.textContent = text;
  messagesEl.appendChild(banner);
}

function appendMessage(role, content) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = `message-bubble ${role}`;

  const meta = document.createElement("div");
  meta.className = "message-meta";

  const roleEl = document.createElement("span");
  roleEl.className = "message-role";
  roleEl.textContent = role === "user" ? "You" : "Assistant";

  meta.appendChild(roleEl);

  const contentEl = document.createElement("div");
  contentEl.textContent = content;

  bubble.appendChild(meta);
  bubble.appendChild(contentEl);
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function sendMessage(text) {
  const userMessage = { role: "user", content: text };
  conversation.push(userMessage);
  appendMessage("user", text);

  sendButtonEl.disabled = true;
  sendButtonEl.textContent = "Sending...";

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messages: conversation,
      }),
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      const msg = errorData.detail || `Request failed with status ${res.status}`;
      appendError(msg);
      return;
    }

    const data = await res.json();

    if (data && data.choices && data.choices[0] && data.choices[0].message) {
      const assistantMessage = data.choices[0].message;
      conversation.push(assistantMessage);
      appendMessage("assistant", assistantMessage.content);
    } else {
      appendError("Unexpected response format from server.");
    }
  } catch (err) {
    console.error(err);
    appendError("Network or server error while contacting the proxy.");
  } finally {
    sendButtonEl.disabled = false;
    sendButtonEl.textContent = "Send";
  }
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = inputEl.value.trim();
  if (!value) return;
  inputEl.value = "";
  sendMessage(value);
});

appendSystem("You are connected to the ChatGPT proxy. Messages are not persisted server-side.");
