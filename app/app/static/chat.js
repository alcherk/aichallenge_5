const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const sendButtonEl = document.getElementById("send-button");
const settingsBtn = document.getElementById("settings-btn");
const systemPromptPanel = document.getElementById("system-prompt-panel");
const systemPromptInput = document.getElementById("system-prompt-input");
const saveSystemPromptBtn = document.getElementById("save-system-prompt-btn");
const resetSystemPromptBtn = document.getElementById("reset-system-prompt-btn");
const closeSystemPromptBtn = document.getElementById("close-system-prompt-btn");
const temperatureInput = document.getElementById("temperature-input");
const temperatureValue = document.getElementById("temperature-value");
const modelSelect = document.getElementById("model-select");
const compressionThresholdInput = document.getElementById("compression-threshold-input");
const compressionThresholdValue = document.getElementById("compression-threshold-value");
const metricsPanel = document.getElementById("metrics-panel");
const toggleMetricsBtn = document.getElementById("toggle-metrics-btn");
const showMetricsBtn = document.getElementById("show-metrics-btn");
const resetMetricsBtn = document.getElementById("reset-metrics-btn");

// Metrics elements
const metricModel = document.getElementById("metric-model");
const metricProvider = document.getElementById("metric-provider");
const metricInputTokens = document.getElementById("metric-input-tokens");
const metricOutputTokens = document.getElementById("metric-output-tokens");
const metricTotalTokens = document.getElementById("metric-total-tokens");
const metricCost = document.getElementById("metric-cost");
const metricResponseTime = document.getElementById("metric-response-time");
const metricTotalRequests = document.getElementById("metric-total-requests");
const metricTotalCost = document.getElementById("metric-total-cost");
const metricContextWindow = document.getElementById("metric-context-window");
const metricContextUsage = document.getElementById("metric-context-usage");
const metricContextUsagePercent = document.getElementById("metric-context-usage-percent");

// Default system prompt
const defaultSystemPrompt = `Ты помощник-прокси между пользователем и системой.

Твоя задача — сначала ПОНЯТЬ задачу, а потом решать.

Формат ответа: обычный текст или Markdown.

Если информации недостаточно, задай уточняющие вопросы.

Если информации достаточно и можно решить задачу, предоставь подробное решение.

Правила:
- Не придумывай ответ на задачу, если нет данных — сперва задавай вопросы.
- Когда считаешь, что вопросов достаточно, предоставь итоговый ответ.
- Используй Markdown для форматирования (заголовки, списки, код и т.д.).`;

// Load system prompt from localStorage or use default
function getSystemPrompt() {
  const saved = localStorage.getItem("systemPrompt");
  return saved || defaultSystemPrompt;
}

function setSystemPrompt(prompt) {
  localStorage.setItem("systemPrompt", prompt);
  updateConversationSystemMessage(prompt);
}

function updateConversationSystemMessage(prompt) {
  // Update or add system message in conversation
  const systemIndex = conversation.findIndex(msg => msg.role === "system");
  const systemMessage = { role: "system", content: prompt };
  
  if (systemIndex >= 0) {
    conversation[systemIndex] = systemMessage;
  } else {
    conversation.unshift(systemMessage);
  }
}

// Initialize conversation with system prompt
let conversation = [
  {
    role: "system",
    content: getSystemPrompt()
  }
];

// Message counter for compression (excludes system message)
let messageCount = 0;

// Temperature management
function getTemperature() {
  const saved = localStorage.getItem("temperature");
  return saved !== null ? parseFloat(saved) : 0.7;
}

function setTemperature(value) {
  localStorage.setItem("temperature", value.toString());
}

// Model management
function getModel() {
  const saved = localStorage.getItem("model");
  return saved || "gpt-4o-mini";
}

function setModel(value) {
  localStorage.setItem("model", value);
}

// Compression threshold management
function getCompressionThreshold() {
  const saved = localStorage.getItem("compressionThreshold");
  return saved !== null ? parseInt(saved) : 10;
}

function setCompressionThreshold(value) {
  localStorage.setItem("compressionThreshold", value.toString());
}

// Compress conversation history by summarizing old messages
async function compressConversation() {
  // Get messages to summarize (everything except system message)
  const messagesToSummarize = conversation.slice(1); // Skip system message
  
  if (messagesToSummarize.length === 0) {
    return; // Nothing to compress
  }
  
  // Create a summary prompt
  const summaryPrompt = `Please provide a concise summary of the following conversation history. The summary should capture:
- Key topics discussed
- Important decisions or conclusions reached
- Any context that would be needed to continue the conversation naturally

Conversation history:
${messagesToSummarize.map(msg => `${msg.role}: ${msg.content}`).join('\n\n')}

Provide a clear, concise summary that preserves essential context:`;

  try {
    // Call API to get summary
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messages: [
          { role: "system", content: "You are a helpful assistant that summarizes conversations concisely while preserving important context." },
          { role: "user", content: summaryPrompt }
        ],
        temperature: 0.3, // Lower temperature for more consistent summaries
        model: getModel(),
      }),
    });

    const responseData = await res.json();

    if (responseData.success && responseData.data && responseData.data.choices && responseData.data.choices[0]) {
      const summaryContent = responseData.data.choices[0].message.content;
      
      // Replace old messages with summary (keep system message)
      conversation = [
        conversation[0], // Keep system message
        {
          role: "assistant",
          content: `[Conversation Summary]\n\n${summaryContent}`
        }
      ];
      
      // Reset message count
      messageCount = 1; // The summary counts as 1 message
      
      // Show notification
      appendSystem("Conversation history compressed. Previous messages summarized.");
    } else {
      console.error("Failed to compress conversation:", responseData);
      appendSystem("Failed to compress conversation history. Continuing with full history.");
    }
  } catch (error) {
    console.error("Error compressing conversation:", error);
    appendSystem("Error compressing conversation history. Continuing with full history.");
  }
}

// Initialize system prompt input
systemPromptInput.value = getSystemPrompt();

// Initialize temperature
const currentTemperature = getTemperature();
temperatureInput.value = currentTemperature;
temperatureValue.textContent = currentTemperature.toFixed(1);

// Initialize model select
const currentModel = getModel();
modelSelect.value = currentModel;

// Initialize compression threshold
const currentCompressionThreshold = getCompressionThreshold();
compressionThresholdInput.value = currentCompressionThreshold;
compressionThresholdValue.textContent = currentCompressionThreshold;

// Update compression threshold display when slider changes
compressionThresholdInput.addEventListener("input", (e) => {
  const value = parseInt(e.target.value);
  compressionThresholdValue.textContent = value;
  setCompressionThreshold(value);
});

// Cost calculation based on OpenAI pricing (as of 2024)
function getModelPricing(model) {
  const pricing = {
    "gpt-4o": { input: 2.50, output: 10.00 }, // per 1M tokens
    "gpt-4-turbo": { input: 10.00, output: 30.00 },
    "gpt-4": { input: 30.00, output: 60.00 },
    "gpt-4o-mini": { input: 0.15, output: 0.60 },
    "gpt-3.5-turbo": { input: 0.50, output: 1.50 },
  };
  return pricing[model] || pricing["gpt-4o-mini"];
}

// Context window limits for OpenAI models
function getContextWindow(model) {
  const contextWindows = {
    "gpt-4o": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-4o-mini": 128000,
    "gpt-3.5-turbo": 16385,
  };
  return contextWindows[model] || contextWindows["gpt-4o-mini"];
}

// Calculate total tokens in conversation history
function calculateConversationTokens() {
  // Estimate tokens: roughly 4 characters per token for English text
  // This is a rough estimate - actual tokenization would require the API
  let totalTokens = 0;
  conversation.forEach(msg => {
    if (msg.content) {
      // Rough estimate: ~4 chars per token
      totalTokens += Math.ceil(msg.content.length / 4);
    }
  });
  return totalTokens;
}

function calculateCost(model, inputTokens, outputTokens) {
  const pricing = getModelPricing(model);
  const inputCost = (inputTokens / 1000000) * pricing.input;
  const outputCost = (outputTokens / 1000000) * pricing.output;
  return inputCost + outputCost;
}

// Metrics management
function getTotalMetrics() {
  const saved = localStorage.getItem("totalMetrics");
  return saved ? JSON.parse(saved) : { requests: 0, totalCost: 0 };
}

function setTotalMetrics(metrics) {
  localStorage.setItem("totalMetrics", JSON.stringify(metrics));
}

function updateMetrics(responseData) {
  if (!responseData.success || !responseData.metadata) return;
  
  const metadata = responseData.metadata;
  const tokenUsage = metadata.token_usage;
  const model = metadata.model || getModel();
  
  // Update current metrics
  if (metadata.model) {
    metricModel.textContent = model;
  }
  metricProvider.textContent = "OpenAI";
  
  // Update context window
  const contextWindow = getContextWindow(model);
  metricContextWindow.textContent = `${(contextWindow / 1000).toFixed(0)}k`;
  
  if (tokenUsage) {
    metricInputTokens.textContent = tokenUsage.prompt_tokens.toLocaleString();
    metricOutputTokens.textContent = tokenUsage.completion_tokens.toLocaleString();
    metricTotalTokens.textContent = tokenUsage.total_tokens.toLocaleString();
    
    // Calculate cost
    const cost = calculateCost(
      model,
      tokenUsage.prompt_tokens,
      tokenUsage.completion_tokens
    );
    metricCost.textContent = `$${cost.toFixed(6)}`;
    
    // Update context usage (use prompt_tokens as it represents the full context sent)
    const contextUsage = tokenUsage.prompt_tokens;
    metricContextUsage.textContent = contextUsage.toLocaleString();
    
    // Calculate context usage percentage
    const contextUsagePercent = (contextUsage / contextWindow) * 100;
    metricContextUsagePercent.textContent = `${contextUsagePercent.toFixed(2)}%`;
    
    // Update total metrics
    const totals = getTotalMetrics();
    totals.requests += 1;
    totals.totalCost += cost;
    setTotalMetrics(totals);
    
    metricTotalRequests.textContent = totals.requests.toLocaleString();
    metricTotalCost.textContent = `$${totals.totalCost.toFixed(6)}`;
  }
  
  if (metadata.processing_time_ms !== undefined) {
    metricResponseTime.textContent = `${metadata.processing_time_ms}ms`;
  }
}

// Initialize metrics panel
const totals = getTotalMetrics();
metricTotalRequests.textContent = totals.requests.toLocaleString();
metricTotalCost.textContent = `$${totals.totalCost.toFixed(6)}`;

// Initialize context window display
const initialModel = getModel();
const initialContextWindow = getContextWindow(initialModel);
metricContextWindow.textContent = `${(initialContextWindow / 1000).toFixed(0)}k`;

// Metrics panel toggle
toggleMetricsBtn.addEventListener("click", () => {
  metricsPanel.classList.add("hidden");
  showMetricsBtn.style.display = "block";
});

showMetricsBtn.addEventListener("click", () => {
  metricsPanel.classList.remove("hidden");
  showMetricsBtn.style.display = "none";
});

// Reset metrics
resetMetricsBtn.addEventListener("click", () => {
  if (confirm("Reset all metrics? This cannot be undone.")) {
    setTotalMetrics({ requests: 0, totalCost: 0 });
    metricTotalRequests.textContent = "0";
    metricTotalCost.textContent = "$0.000";
    metricModel.textContent = "-";
    metricInputTokens.textContent = "0";
    metricOutputTokens.textContent = "0";
    metricTotalTokens.textContent = "0";
    metricCost.textContent = "$0.000";
    metricResponseTime.textContent = "-";
    metricContextUsage.textContent = "0";
    metricContextUsagePercent.textContent = "0%";
  }
});

// Update temperature display when slider changes
temperatureInput.addEventListener("input", (e) => {
  const value = parseFloat(e.target.value);
  temperatureValue.textContent = value.toFixed(1);
  setTemperature(value);
});

// Update model when select changes
modelSelect.addEventListener("change", (e) => {
  setModel(e.target.value);
});

// Settings panel toggle
settingsBtn.addEventListener("click", () => {
  const isVisible = systemPromptPanel.style.display !== "none";
  systemPromptPanel.style.display = isVisible ? "none" : "block";
  if (!isVisible) {
    systemPromptInput.value = getSystemPrompt();
    temperatureInput.value = getTemperature();
    temperatureValue.textContent = getTemperature().toFixed(1);
    modelSelect.value = getModel();
    compressionThresholdInput.value = getCompressionThreshold();
    compressionThresholdValue.textContent = getCompressionThreshold();
  }
});

// Save system prompt
saveSystemPromptBtn.addEventListener("click", () => {
  const newPrompt = systemPromptInput.value.trim();
  if (newPrompt) {
    setSystemPrompt(newPrompt);
    systemPromptPanel.style.display = "none";
    appendSystem("System prompt updated successfully.");
  }
});

// Reset to default
resetSystemPromptBtn.addEventListener("click", () => {
  systemPromptInput.value = defaultSystemPrompt;
  setSystemPrompt(defaultSystemPrompt);
  temperatureInput.value = 0.7;
  temperatureValue.textContent = "0.7";
  setTemperature(0.7);
  modelSelect.value = "gpt-4o-mini";
  setModel("gpt-4o-mini");
  compressionThresholdInput.value = 10;
  compressionThresholdValue.textContent = "10";
  setCompressionThreshold(10);
  appendSystem("System prompt, temperature, model, and compression threshold reset to default.");
});

// Close panel
closeSystemPromptBtn.addEventListener("click", () => {
  systemPromptPanel.style.display = "none";
});

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

function formatMarkdown(text) {
  if (!text) return '';
  
  let html = text;
  
  // Code blocks first (before escaping)
  html = html.replace(/```([\s\S]*?)```/g, (match, code) => {
    const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return '<pre><code>' + escaped + '</code></pre>';
  });
  
  // Inline code
  html = html.replace(/`([^`\n]+)`/g, (match, code) => {
    const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return '<code>' + escaped + '</code>';
  });
  
  // Escape remaining HTML
  const parts = html.split(/(<pre><code>[\s\S]*?<\/code><\/pre>)/);
  html = parts.map(part => {
    if (part.startsWith('<pre><code>')) {
      return part; // Already processed
    }
    return part.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }).join('');
  
  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
  
  // Bold and italic (after escaping)
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  html = html.replace(/_(.*?)_/g, '<em>$1</em>');
  
  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  
  // Lists
  html = html.replace(/^\* (.*$)/gim, '<li>$1</li>');
  html = html.replace(/^- (.*$)/gim, '<li>$1</li>');
  html = html.replace(/^(\d+)\. (.*$)/gim, '<li>$2</li>');
  
  // Wrap consecutive list items in ul
  html = html.replace(/(<li>.*<\/li>(\n|$))+/gim, '<ul>$&</ul>');
  
  // Line breaks - double newline becomes paragraph break
  html = html.split(/\n\n+/).map(para => {
    if (para.trim().startsWith('<')) {
      return para; // Already has HTML tags
    }
    para = para.replace(/\n/g, '<br>');
    return para.trim() ? '<p>' + para + '</p>' : '';
  }).join('');
  
  return html;
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
  
  // Add statistics for assistant messages
  if (role === "assistant" && fullResponseData && fullResponseData.metadata) {
    const stats = document.createElement("div");
    stats.className = "message-stats";
    
    const metadata = fullResponseData.metadata;
    const statsItems = [];
    
    if (metadata.model) {
      statsItems.push(`Model: ${metadata.model}`);
    }
    
    if (metadata.processing_time_ms !== undefined) {
      statsItems.push(`Time: ${metadata.processing_time_ms}ms`);
    }
    
    if (metadata.token_usage) {
      const usage = metadata.token_usage;
      statsItems.push(`Tokens: ${usage.total_tokens} (${usage.prompt_tokens}+${usage.completion_tokens})`);
    }
    
    if (statsItems.length > 0) {
      stats.textContent = statsItems.join(" · ");
      meta.appendChild(stats);
    }
  }

  const contentEl = document.createElement("div");
  
  // Display assistant messages as markdown/plain text
  if (role === "assistant") {
    contentEl.className = "message-content";
    // Check if content is JSON and format it, otherwise display as markdown/text
    const extractedJSON = extractJSON(content);
    if (extractedJSON) {
      // If it's JSON, show it formatted
      contentEl.className = "json-content";
      const jsonLabel = document.createElement("div");
      jsonLabel.className = "json-label";
      jsonLabel.textContent = "📋 JSON Response";
      contentEl.appendChild(jsonLabel);
      
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      code.innerHTML = syntaxHighlightJSON(extractedJSON);
      pre.appendChild(code);
      contentEl.appendChild(pre);
    } else {
      // Display as markdown/plain text with basic formatting
      contentEl.className = "markdown-content";
      contentEl.innerHTML = formatMarkdown(content);
    }
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
  messageCount++;
  appendMessage("user", text);

  // Check if compression is needed before sending
  const threshold = getCompressionThreshold();
  if (messageCount >= threshold) {
    sendButtonEl.disabled = true;
    sendButtonEl.textContent = "Compressing...";
    await compressConversation();
  }

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
          temperature: getTemperature(),
          model: getModel(),
        }),
      });

      const responseData = await res.json();

      // Handle structured response format
      if (responseData.success && responseData.data) {
        const chatData = responseData.data;
        if (chatData.choices && chatData.choices[0] && chatData.choices[0].message) {
          const assistantMessage = chatData.choices[0].message;
          
          // Add assistant message to conversation history
          // Ensure we maintain the full conversation including system, user, and assistant messages
          conversation.push(assistantMessage);
          messageCount++; // Increment count for assistant message
          
          // Display the message content with full response data available
          appendMessage("assistant", assistantMessage.content, responseData);
          
          // Update metrics panel
          updateMetrics(responseData);
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
