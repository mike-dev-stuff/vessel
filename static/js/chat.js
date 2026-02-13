const messagesDiv = document.getElementById("messages");
const input = document.getElementById("message-input");
const sendBtn = document.getElementById("send-button");
const settingsBtn = document.getElementById("settings-button");
const settingsPanel = document.getElementById("settings-panel");
const clearMemoryBtn = document.getElementById("clear-memory-btn");

// Settings panel toggle
settingsBtn.addEventListener("click", () => {
    settingsPanel.classList.toggle("hidden");
});

// Clear memory
clearMemoryBtn.addEventListener("click", async () => {
    if (!confirm("Erase all conversation history and long-term memory?")) return;

    clearMemoryBtn.disabled = true;
    clearMemoryBtn.textContent = "Clearing...";

    try {
        const resp = await fetch("/api/forget", { method: "POST" });
        if (resp.ok) {
            messagesDiv.innerHTML = "";
            settingsPanel.classList.add("hidden");
        }
    } catch (err) {
        alert("Failed to clear memory: " + err.message);
    }

    clearMemoryBtn.disabled = false;
    clearMemoryBtn.textContent = "Clear All Memory";
});

// Poll for proactive pings from the chatbot
setInterval(async () => {
    // Skip if we're mid-conversation (input disabled means streaming)
    if (input.disabled) return;
    try {
        const resp = await fetch("/api/pings");
        const data = await resp.json();
        if (data.message) {
            showTypingIndicator();
            const delay = Math.random() * 1000 + 500;
            setTimeout(() => {
                removeTypingIndicator();
                appendMessage("assistant", data.message);
            }, delay);
        }
    } catch {}
}, 30000);

// Send on Enter (Shift+Enter for newline)
input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

sendBtn.addEventListener("click", sendMessage);

// Auto-resize textarea
input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
});

function sendMessage() {
    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    input.style.height = "auto";
    appendMessage("user", message);

    if (message.startsWith("/imagine ")) {
        const imagePrompt = message.substring(9).trim();
        if (imagePrompt) {
            requestImage(imagePrompt);
        }
    } else {
        streamChat(message);
    }
}

function appendMessage(role, content) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = content;
    messagesDiv.appendChild(div);
    scrollToBottom();
    return div;
}

function scrollToBottom() {
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function setInputEnabled(enabled) {
    input.disabled = !enabled;
    sendBtn.disabled = !enabled;
    if (enabled) input.focus();
}

// Show the typing indicator (three animated dots)
function showTypingIndicator() {
    removeTypingIndicator();
    const indicator = document.createElement("div");
    indicator.className = "typing-indicator";
    indicator.id = "typing-indicator";
    indicator.innerHTML =
        '<div class="typing-dot"></div>' +
        '<div class="typing-dot"></div>' +
        '<div class="typing-dot"></div>';
    messagesDiv.appendChild(indicator);
    scrollToBottom();
}

function removeTypingIndicator() {
    const el = document.getElementById("typing-indicator");
    if (el) el.remove();
}

// Multi-message chat with typing indicators and realistic timing
async function streamChat(message) {
    setInputEnabled(false);
    showTypingIndicator();

    // Track the last assistant bubble for image attachment
    let lastBubble = null;

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
        });

        if (!response.ok) {
            removeTypingIndicator();
            const errBubble = appendMessage("assistant", `Error: ${response.statusText}`);
            errBubble.classList.add("error");
            setInputEnabled(true);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const jsonStr = line.substring(6);

                let data;
                try {
                    data = JSON.parse(jsonStr);
                } catch {
                    continue;
                }

                switch (data.type) {
                    case "typing":
                        // Server is simulating typing — show indicator
                        showTypingIndicator();
                        break;

                    case "message":
                        // A complete message bubble arrives
                        removeTypingIndicator();
                        lastBubble = appendMessage("assistant", data.content);
                        break;

                    case "image_generating":
                        removeTypingIndicator();
                        showLoader("Generating image...");
                        break;

                    case "image":
                        removeLoader();
                        const imgBubble = lastBubble || appendMessage("assistant", "");
                        const img = document.createElement("img");
                        img.src = data.url;
                        img.alt = "Generated image";
                        img.onload = scrollToBottom;
                        imgBubble.appendChild(img);
                        lastBubble = imgBubble;
                        break;

                    case "error":
                        removeTypingIndicator();
                        removeLoader();
                        const errDiv = appendMessage("assistant", data.message);
                        errDiv.classList.add("error");
                        break;

                    case "done":
                        removeTypingIndicator();
                        break;
                }
            }
        }
    } catch (err) {
        removeTypingIndicator();
        const errBubble = appendMessage("assistant", `Connection error: ${err.message}`);
        errBubble.classList.add("error");
    }

    setInputEnabled(true);
}

// Explicit /imagine command
async function requestImage(prompt) {
    setInputEnabled(false);
    showLoader("Generating image...");

    try {
        const response = await fetch("/api/imagine", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt }),
        });
        const data = await response.json();
        removeLoader();

        if (data.url) {
            const bubble = appendMessage("assistant", "");
            const img = document.createElement("img");
            img.src = data.url;
            img.alt = "Generated image";
            img.onload = scrollToBottom;
            bubble.appendChild(img);
        } else {
            const errDiv = appendMessage(
                "assistant",
                "Image generation failed: " + (data.error || "unknown error")
            );
            errDiv.classList.add("error");
        }
    } catch (err) {
        removeLoader();
        const errDiv = appendMessage(
            "assistant",
            "Image generation failed: " + err.message
        );
        errDiv.classList.add("error");
    }

    setInputEnabled(true);
}

function showLoader(text) {
    removeLoader();
    const loader = document.createElement("div");
    loader.className = "loading-indicator";
    loader.id = "loader";
    loader.innerHTML = `<div class="spinner"></div> ${text}`;
    messagesDiv.appendChild(loader);
    scrollToBottom();
}

function removeLoader() {
    const loader = document.getElementById("loader");
    if (loader) loader.remove();
}
