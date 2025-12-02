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

function isJSON(str) {
  if (!str || typeof str !== 'string') return false;
  const trimmed = str.trim();
  // Check if it starts with { or [ and ends with } or ]
  if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || 
      (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    try {
      JSON.parse(trimmed);
      return true;
    } catch (e) {
      return false;
    }
  }
  return false;
}

function extractJSON(str) {
  if (!str || typeof str !== 'string') return null;
  const trimmed = str.trim();
  
  // Try direct JSON
  if (isJSON(trimmed)) {
    return trimmed;
  }
  
  // Try extracting from markdown code blocks
  const jsonMatch = trimmed.match(/```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```/);
  if (jsonMatch && isJSON(jsonMatch[1])) {
    return jsonMatch[1];
  }
  
  // Try finding JSON object/array in the text
  const jsonObjMatch = trimmed.match(/\{[\s\S]*\}/);
  if (jsonObjMatch && isJSON(jsonObjMatch[0])) {
    return jsonObjMatch[0];
  }
  
  const jsonArrayMatch = trimmed.match(/\[[\s\S]*\]/);
  if (jsonArrayMatch && isJSON(jsonArrayMatch[0])) {
    return jsonArrayMatch[0];
  }
  
  return null;
}

function formatJSON(jsonString) {
  try {
    const parsed = JSON.parse(jsonString);
    return JSON.stringify(parsed, null, 2);
  } catch (e) {
    return jsonString;
  }
}

function syntaxHighlightJSON(jsonString) {
  try {
    const parsed = JSON.parse(jsonString);
    const formatted = JSON.stringify(parsed, null, 2);
    
    // Simple syntax highlighting
    return formatted
      .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, (match) => {
        let cls = 'json-number';
        if (/^"/.test(match)) {
          if (/:$/.test(match)) {
            cls = 'json-key';
          } else {
            cls = 'json-string';
          }
        } else if (/true|false/.test(match)) {
          cls = 'json-boolean';
        } else if (/null/.test(match)) {
          cls = 'json-null';
        }
        return `<span class="${cls}">${match}</span>`;
      });
  } catch (e) {
    return jsonString;
  }
}

function appendMessage(role, content, fullResponseData = null) {
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
  
  // Always display assistant messages as JSON
  if (role === "assistant") {
    // Try to extract and display JSON
    const extractedJSON = extractJSON(content);
    const jsonToDisplay = extractedJSON || content;
    
    contentEl.className = "json-content";
    const jsonLabel = document.createElement("div");
    jsonLabel.className = "json-label";
    jsonLabel.textContent = "📋 JSON Response";
    contentEl.appendChild(jsonLabel);
    
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.innerHTML = syntaxHighlightJSON(jsonToDisplay);
    pre.appendChild(code);
    contentEl.appendChild(pre);
  } else {
    // User messages display as plain text
    contentEl.textContent = content;
  }

  // Add button to show full structured response if available
  if (fullResponseData && role === "assistant") {
    const showFullBtn = document.createElement("button");
    showFullBtn.className = "show-full-response-btn";
    showFullBtn.textContent = "Show Full Response";
    showFullBtn.onclick = () => {
      const fullResponseEl = document.createElement("div");
      fullResponseEl.className = "full-response-json";
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      code.innerHTML = syntaxHighlightJSON(JSON.stringify(fullResponseData, null, 2));
      pre.appendChild(code);
      fullResponseEl.appendChild(pre);
      
      // Toggle visibility
      const existing = bubble.querySelector(".full-response-json");
      if (existing) {
        existing.remove();
        showFullBtn.textContent = "Show Full Response";
      } else {
        bubble.appendChild(fullResponseEl);
        showFullBtn.textContent = "Hide Full Response";
      }
    };
    meta.appendChild(showFullBtn);
  }

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

      const responseData = await res.json();

      // Handle structured response format
      if (responseData.success && responseData.data) {
        const chatData = responseData.data;
        if (chatData.choices && chatData.choices[0] && chatData.choices[0].message) {
          const assistantMessage = chatData.choices[0].message;
          conversation.push(assistantMessage);
          
          // Display the message content with full response data available
          appendMessage("assistant", assistantMessage.content, responseData);
        } else {
          appendError("Unexpected data format in successful response.");
        }
      } else {
        // Handle error in structured response
        const errorMsg = responseData.error?.detail || responseData.message || `Request failed with status ${res.status}`;
        appendError(errorMsg);
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
