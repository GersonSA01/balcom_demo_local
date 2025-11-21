<script>
  import { onMount } from "svelte";
  import UserSelector from "./UserSelector.svelte";

  let messages = [];
  let inputMessage = "";
  let isLoading = false;
  let error = null;
  let isConnected = false;
  let configuredModel = "phi3:mini";
  let sessionData = {};
  let dataUnemi = {};

  const API_BASE_URL = "http://localhost:8000/api/chatbot";

  async function loadDataUnemi() {
    try {
      const response = await fetch("/data_unemi.json");
      dataUnemi = await response.json();
    } catch (e) {
      console.error("Error cargando data_unemi.json:", e);
    }
  }

  function handleSessionUpdate(event) {
    sessionData = event.detail;
  }

  function loadSessionFromStorage() {
    try {
      const stored = localStorage.getItem("user_session_data");
      if (stored) {
        sessionData = JSON.parse(stored);
      }
    } catch (e) {
      console.error("Error cargando sesión desde localStorage:", e);
    }
  }

  onMount(() => {
    checkConnection();
    loadDataUnemi();
    loadSessionFromStorage(); // Cargar sesión guardada al iniciar
    window.addEventListener("sessionDataUpdated", handleSessionUpdate);

    return () => {
      window.removeEventListener("sessionDataUpdated", handleSessionUpdate);
    };
  });

  async function checkConnection() {
    try {
      const response = await fetch(`${API_BASE_URL}/health/`);
      const data = await response.json();

      isConnected = data.ollama_connected && data.model_available;

      if (data.model_configured) {
        configuredModel = data.model_configured;
      }

      if (!isConnected) {
        if (!data.ollama_connected) {
          error =
            data.error ||
            "Ollama no está disponible. Asegúrate de que Ollama esté ejecutándose.";
        } else if (!data.model_available) {
          error = `El modelo ${configuredModel} no está instalado. Ejecuta: ollama pull ${configuredModel}`;
        } else {
          error =
            data.error ||
            `Ollama no está disponible o ${configuredModel} no está instalado`;
        }
      }
    } catch (err) {
      isConnected = false;
      error =
        "No se pudo conectar con el servidor Django. Verifica que el servidor esté ejecutándose.";
    }
  }

  let loadingText = ""; // Nueva variable para el estado

  async function sendMessage() {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage.trim();
    inputMessage = "";
    error = null;

    messages = [...messages, { role: "user", content: userMessage }];
    isLoading = true;
    loadingText = "Iniciando..."; // Texto inicial

    try {
      // ---------------------------------------------------------
      // 🚨 CORRECCIÓN CRÍTICA: Leer datos frescos del localStorage
      // JUSTO ANTES de enviar, sin depender de variables reactivas
      // ---------------------------------------------------------
      let sessionDataToSend = {};
      const storedData = localStorage.getItem("user_session_data");

      if (storedData) {
        try {
          sessionDataToSend = JSON.parse(storedData);
          console.log("🟢 DATOS QUE SE ENVIARÁN AL PYTHON:", sessionDataToSend);
        } catch (e) {
          console.error(
            "❌ Error parseando datos de sesión desde localStorage:",
            e,
          );
        }
      }

      const history = messages.slice(0, -1).map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      const requestBody = {
        message: userMessage,
        history: history,
        session_data: sessionDataToSend,
      };

      const response = await fetch(`${API_BASE_URL}/chat/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      // ⚠️ AQUÍ EMPIEZA LA LECTURA DEL STREAM
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decodificar el chunk recibido
        buffer += decoder.decode(value, { stream: true });

        // Procesar líneas completas (NDJSON)
        const lines = buffer.split("\n");
        buffer = lines.pop(); // Guardar el fragmento incompleto para la siguiente vuelta

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const update = JSON.parse(line);

            // 1. SI ES ACTUALIZACIÓN DE ESTADO
            if (update.type === "status") {
              loadingText = update.text; // ¡Esto actualiza la UI en tiempo real!
            }

            // 2. SI ES LA RESPUESTA FINAL
            else if (update.type === "final") {
              const data = update.data;
              let responseText = "";

              if (data.type === "rag_response") {
                responseText = data.text || "No pude generar una respuesta.";
                if (data.sources && data.sources.length > 0) {
                  responseText += `\n\n📚 Fuentes: ${data.sources.join(", ")}`;
                }
              } else if (data.type === "agent_handoff") {
                responseText =
                  data.text || "Un agente se pondrá en contacto contigo.";
              } else if (data.type === "simple") {
                responseText = data.text || "Respuesta simple.";
              } else {
                responseText = data.text || JSON.stringify(data, null, 2);
              }

              messages = [
                ...messages,
                { role: "assistant", content: responseText },
              ];
            }

            // 3. SI ES ERROR
            else if (update.type === "error") {
              console.error("Backend error:", update.text);
              error = "Error del servidor: " + update.text;
            }
          } catch (e) {
            console.error("Error parseando JSON del stream:", e);
          }
        }
      }
    } catch (err) {
      error = "Error de conexión: " + err.message;
      messages = messages.slice(0, -1);
    } finally {
      isLoading = false;
      loadingText = "";
    }
  }

  function handleKeyPress(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  function clearChat() {
    messages = [];
    error = null;
  }
</script>

<div class="chatbot-container">
  <div class="chatbot-header">
    <div class="header-left">
      <div class="logo">SGA<span class="logo-plus">+</span></div>
      <h3>Asistente Virtual UNEMI</h3>
    </div>
    <div class="header-right">
      <div class="status-indicator">
        <span class="status-dot" class:connected={isConnected}></span>
        <span class="status-text"
          >{isConnected ? "Conectado" : "Desconectado"}</span
        >
      </div>
      {#if messages.length > 0}
        <button class="clear-btn" on:click={clearChat}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path
              d="M2 4h12M5 4V2a1 1 0 011-1h4a1 1 0 011 1v2m3 0v10a1 1 0 01-1 1H3a1 1 0 01-1-1V4h12z"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
            />
          </svg>
          Limpiar
        </button>
      {/if}
    </div>
  </div>

  <UserSelector {dataUnemi} />

  {#if error}
    <div class="error-message">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="2" />
        <path
          d="M10 6v4M10 14h.01"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
        />
      </svg>
      <span>{error}</span>
    </div>
  {/if}

  <div class="messages-container">
    {#if messages.length === 0}
      <div class="empty-state">
        <div class="empty-icon">💬</div>
        <h4>¡Hola! Soy tu asistente virtual</h4>
        <p>
          Puedo ayudarte con información sobre reglamentos, trámites y servicios
          de la UNEMI.
        </p>
        <p class="hint">
          Asegúrate de seleccionar tu perfil arriba para recibir respuestas
          personalizadas.
        </p>
      </div>
    {:else}
      {#each messages as message, idx (idx)}
        <div
          class="message"
          class:user={message.role === "user"}
          class:assistant={message.role === "assistant"}
        >
          <div class="message-avatar">
            {#if message.role === "user"}
              👤
            {:else}
              🤖
            {/if}
          </div>
          <div class="message-content">
            {@html message.content.replace(/\n/g, "<br>")}
          </div>
        </div>
      {/each}
    {/if}
    {#if isLoading}
      <div class="message assistant">
        <div class="message-avatar">🤖</div>
        <div class="message-content loading">
          {#if loadingText}
            <span class="loading-text">{loadingText}</span>
          {/if}
          <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    {/if}
  </div>

  <div class="input-container">
    <textarea
      bind:value={inputMessage}
      on:keypress={handleKeyPress}
      placeholder="Escribe tu pregunta aquí..."
      disabled={isLoading || !isConnected}
      rows="2"
    ></textarea>
    <button
      on:click={sendMessage}
      disabled={isLoading || !isConnected || !inputMessage.trim()}
      class="send-btn"
    >
      {#if isLoading}
        <svg class="spinner" width="20" height="20" viewBox="0 0 20 20">
          <circle
            cx="10"
            cy="10"
            r="8"
            stroke="currentColor"
            stroke-width="2"
            fill="none"
            stroke-dasharray="50"
            stroke-dashoffset="25"
          />
        </svg>
      {:else}
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path
            d="M18 2L9 11M18 2l-7 7M18 2H8M18 2v10"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      {/if}
    </button>
  </div>
</div>

<style>
  .chatbot-container {
    display: flex;
    flex-direction: column;
    height: 700px;
    max-width: 900px;
    margin: 0 auto;
    border: 1px solid #d0d5dd;
    border-radius: 12px;
    background: #ffffff;
    box-shadow: 0 4px 20px rgba(30, 58, 95, 0.15);
    overflow: hidden;
  }

  .chatbot-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    background: linear-gradient(135deg, #1e3a5f 0%, #2c4a6b 100%);
    border-bottom: 3px solid #ff6b35;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .logo {
    font-size: 24px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.5px;
  }

  .logo-plus {
    color: #ff6b35;
  }

  .chatbot-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: 0.3px;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .status-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    backdrop-filter: blur(10px);
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #999;
    box-shadow: 0 0 6px rgba(255, 255, 255, 0.5);
    transition: all 0.3s ease;
  }

  .status-dot.connected {
    background: #4ade80;
    box-shadow: 0 0 8px rgba(74, 222, 128, 0.6);
    animation: pulse 2s infinite;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.7;
    }
  }

  .status-text {
    font-size: 12px;
    font-weight: 500;
    color: #ffffff;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .clear-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    background: rgba(255, 255, 255, 0.15);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s ease;
    backdrop-filter: blur(10px);
  }

  .clear-btn:hover {
    background: rgba(255, 107, 53, 0.2);
    border-color: #ff6b35;
    transform: translateY(-1px);
  }

  .error-message {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 20px;
    background: #fff3e0;
    border-left: 4px solid #ff6b35;
    color: #e65100;
    font-size: 14px;
    font-weight: 500;
  }

  .messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    background: #f8fafc;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    text-align: center;
    color: #64748b;
    padding: 40px 20px;
  }

  .empty-icon {
    font-size: 64px;
    margin-bottom: 16px;
    filter: grayscale(0.2);
  }

  .empty-state h4 {
    margin: 0 0 12px 0;
    font-size: 20px;
    font-weight: 600;
    color: #1e3a5f;
  }

  .empty-state p {
    margin: 8px 0;
    font-size: 14px;
    line-height: 1.6;
    max-width: 400px;
  }

  .hint {
    font-size: 12px;
    color: #94a3b8;
    font-style: italic;
  }

  .message {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    animation: slideIn 0.3s ease-out;
  }

  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .message.user {
    flex-direction: row-reverse;
  }

  .message-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
    background: #ffffff;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .message.user .message-avatar {
    background: linear-gradient(135deg, #1e3a5f 0%, #2c4a6b 100%);
  }

  .message.assistant .message-avatar {
    background: linear-gradient(135deg, #ff6b35 0%, #ff8c5a 100%);
  }

  .message-content {
    max-width: 75%;
    padding: 14px 18px;
    border-radius: 16px;
    word-wrap: break-word;
    line-height: 1.5;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  .message.user .message-content {
    background: linear-gradient(135deg, #1e3a5f 0%, #2c4a6b 100%);
    color: #ffffff;
    border-bottom-right-radius: 4px;
    font-weight: 500;
  }

  .message.assistant .message-content {
    background: #ffffff;
    color: #1e293b;
    border: 1px solid #e2e8f0;
    border-bottom-left-radius: 4px;
  }

  .message-content.loading {
    background: #ffffff;
    padding: 16px;
    border: 1px solid #e2e8f0;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .typing-indicator {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  .typing-indicator span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #ff6b35;
    animation: typing 1.4s infinite;
  }

  .typing-indicator span:nth-child(2) {
    animation-delay: 0.2s;
  }

  .typing-indicator span:nth-child(3) {
    animation-delay: 0.4s;
  }

  @keyframes typing {
    0%,
    60%,
    100% {
      transform: translateY(0);
      opacity: 0.4;
    }
    30% {
      transform: translateY(-8px);
      opacity: 1;
    }
  }

  .input-container {
    display: flex;
    padding: 16px;
    border-top: 1px solid #e2e8f0;
    gap: 12px;
    background: #ffffff;
  }

  .input-container textarea {
    flex: 1;
    padding: 12px 16px;
    border: 2px solid #e2e8f0;
    border-radius: 10px;
    resize: none;
    font-family: inherit;
    font-size: 14px;
    color: #1e293b;
    background: #f8fafc;
    transition: all 0.3s ease;
  }

  .input-container textarea::placeholder {
    color: #94a3b8;
  }

  .input-container textarea:focus {
    outline: none;
    border-color: #ff6b35;
    background: #ffffff;
    box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.1);
  }

  .input-container textarea:disabled {
    background: #f1f5f9;
    cursor: not-allowed;
    opacity: 0.6;
  }

  .send-btn {
    padding: 12px 20px;
    background: linear-gradient(135deg, #ff6b35 0%, #ff8c5a 100%);
    color: white;
    border: none;
    border-radius: 10px;
    cursor: pointer;
    font-size: 18px;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 56px;
    box-shadow: 0 4px 12px rgba(255, 107, 53, 0.3);
  }

  .send-btn:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(255, 107, 53, 0.4);
  }

  .send-btn:active:not(:disabled) {
    transform: translateY(0);
  }

  .send-btn:disabled {
    background: #cbd5e1;
    cursor: not-allowed;
    box-shadow: none;
    opacity: 0.6;
  }

  .spinner {
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .loading-text {
    font-size: 14px;
    color: #64748b;
    margin: 0;
    font-style: normal;
    animation: fadeIn 0.3s ease-in;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
</style>
