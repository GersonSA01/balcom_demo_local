<script>
  import { onMount, tick } from "svelte";
  // Eliminadas importaciones de UserSelector y Menu

  // PROPS
  export let sessionData = {};
  
  // Estado interno para controlar si el chat está abierto
  let chatOpened = false;

  let messageInputEl;
  let chatContainer; // Referencia al div de mensajes
  let messages = [];
  let inputMessage = "";
  let isLoading = false;
  let error = null;
  let isConnected = false;

  // let sessionData es ahora Prop
  // let dataUnemi Eliminado (lo maneja App)

  // Eliminado estado de Menu y Servicios
  // Eliminada toda la lógica de upload y handoff

  const API_BASE_URL = "http://localhost:9090/api/chatbot";

  // Función para procesar markdown básico y formatear el texto
  function formatMessage(text) {
    if (!text) return "";
    
    // Escapar HTML para seguridad
    let formatted = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    
    // Procesar negritas **texto** -> <strong>texto</strong>
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    
    // Procesar saltos de línea
    formatted = formatted.replace(/\n/g, "<br>");
    
    return formatted;
  }

  // Función para abrir/cerrar el chat
  async function toggleChat() {
    chatOpened = !chatOpened;
    if (chatOpened) {
      await tick(); // esperar DOM
      messageInputEl?.focus(); // focus al input
    }
  }

  // Eliminado handleMenuAction
  // Eliminado handleSessionUpdate

  onMount(() => {
    checkConnection();
  });

  async function checkConnection() {
    try {
      const response = await fetch(`${API_BASE_URL}/health/`);
      const data = await response.json();

      isConnected = data.private_gpt_connected || false;
      if (!isConnected) {
        error =
          data.error ||
          "El asistente no pudo conectarse al servidor en este momento. Por favor intenta nuevamente.";
      }
    } catch (err) {
      isConnected = false;
      error =
        "No logré comunicarme con el servidor. Intenta otra vez en unos momentos.";
    }
  }

  let loadingText = "";
  async function sendMessage(isHidden = false) {
    if (isLoading || (!inputMessage.trim() && !isHidden))
      return;

    const userMessage = inputMessage.trim();
    inputMessage = "";
    error = null;

    if (!isHidden) {
      messages = [...messages, { role: "user", content: userMessage }];
    } else {
      // === NUEVO: MANEJO DE MENSAJES OCULTOS PARA RAG ===
      if (userMessage.startsWith("RAG_CONFIRMED||")) {
        // El usuario dijo SI, mostramos "Sí" visualmente, pero enviamos la query optimizada
        messages = [...messages, { role: "user", content: "Sí, es correcto." }];
      } else if (userMessage === "RAG_REJECTED") {
        messages = [...messages, { role: "user", content: "No, no es eso." }];
      } else if (userMessage === "HUMAN_HANDOFF") {
        messages = [
          ...messages,
          { role: "user", content: "Sí, por favor conéctame con un humano." },
        ];
      } else {
        messages = [...messages, { role: "user", content: userMessage }];
      }
    }

    isLoading = true;
    loadingText = "Pensando...";

    try {
      let sessionDataToSend = {};
      const storedData = localStorage.getItem("user_session_data");
      if (storedData) {
        try {
          sessionDataToSend = JSON.parse(storedData);
        } catch (e) {}
      }

      const history = messages.slice(0, -1).map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      // Construye el body
      const requestBody = {
        message: userMessage,
        history: history,
        session_data: sessionDataToSend,
        current_process: null, // Ya no dependemos de procesos
      };

      const response = await fetch(`${API_BASE_URL}/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) throw new Error("Error en el servidor");

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
          if (!line.trim()) continue;
          try {
            const update = JSON.parse(line);

            if (update.type === "status") {
              loadingText = update.text;
            } else if (update.type === "final") {
              const data = update.data;
              const isRagConfirm = data.action === "RAG_CONFIRMATION";

              // Solo guardamos el mensaje, sin lógica de upload o handoff
              messages = [
                ...messages,
                {
                  role: "assistant",
                  content: data.response,
                  sources: data.sources,
                  isFunction: data.is_function,
                  offerHandoff: data.offer_human_handoff,
                  isRagConfirmation: isRagConfirm,
                  reformulatedQuery: data.payload
                    ? data.payload.reformulated_query
                    : null,
                  confirmationResolved: false,
                },
              ];
            } else if (update.type === "error") {
              messages = [
                ...messages,
                { role: "assistant", content: update.text },
              ];
            }
          } catch (e) {
            console.error("Error leyendo línea:", line);
          }
        }
      }
    } catch (err) {
      console.error(err);
      messages = [
        ...messages,
        { role: "assistant", content: "Lo siento, no puedo obtener una respuesta en este momento. Por favor intenta realiza la solicitud mediante el balcón de servicios." },
      ];
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

  function confirmRag(index, reformulatedQuery) {
    messages[index].confirmationResolved = true;
    messages[index].selectedOption = "yes";
    messages = [...messages]; // Forzar reactividad

    // Enviamos el comando especial con la query optimizada
    inputMessage = "RAG_CONFIRMED||" + reformulatedQuery;
    sendMessage(true);
  }

  function rejectRag(index) {
    messages[index].confirmationResolved = true;
    messages[index].selectedOption = "no";
    messages = [...messages];

    inputMessage = "RAG_REJECTED";
    sendMessage(true);
  }

  // Función eliminada: pushSelectedProcessWelcome - ya no dependemos de procesos

  // Función centralizada y mejorada
  async function scrollToBottom() {
    await tick(); // Espera a que el DOM se actualice con el nuevo mensaje
    if (chatContainer) {
      chatContainer.scrollTo({
        top: chatContainer.scrollHeight,
        behavior: "smooth", // Scroll suave
      });
    }
  }

  // ESTA ES LA CLAVE: Reactividad automática
  // Cada vez que 'messages' cambie (longitud o contenido), se ejecuta el scroll.
  $: if (messages) {
    scrollToBottom();
  }

  // Lógica de apertura automática eliminada - el chat se abre manualmente

  $: lastMessage = messages[messages.length - 1];
  $: isHandoffPending =
    lastMessage && lastMessage.offerHandoff && !lastMessage.handoffResolved;

  // Función simplificada: solo muestra el mensaje cuando se confirma handoff
  async function confirmHandoff(index) {
    // Bloqueo visual
    messages[index].handoffResolved = true;
    messages[index].selectedOption = "yes";
    messages = [...messages];

    // Solo enviamos el comando, el backend responderá con el mensaje
    inputMessage = "HUMAN_HANDOFF";
    await sendMessage(true);
  }

  function cancelHandoff(index) {
    // 1. Bloqueamos los botones visualmente
    messages[index].handoffResolved = true;
    messages[index].selectedOption = "no";
    messages = [...messages];

    // 2. Agregamos el mensaje del usuario
    messages = [
      ...messages,
      { role: "user", content: "No, gracias. Seguiré conversando." },
    ];

    // 3. Simulamos "pensando" y respondemos tras 0.5 segundos
    isLoading = true; 
    
    setTimeout(() => {
      isLoading = false;
      messages = [
        ...messages,
        { 
          role: "assistant", 
          content: "Perfecto. ¿En qué más te puedo ayudar 😊?" 
        },
      ];
    }, 500); // 500ms = 0.5 segundos
  }
</script>

<!-- CHATBOT FLOTANTE -->
<div class="chatbot-floating-wrapper">
  <!-- Botón flotante para abrir/cerrar -->
  {#if !chatOpened}
    <button class="chatbot-toggle-btn" on:click={toggleChat} title="Abrir asistente virtual">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
      </svg>
      <span class="notification-badge" class:connected={isConnected}></span>
    </button>
  {:else}
    <div class="chatbot-container">
      <div class="chatbot-header">
        <div class="header-left">
          <h3>Asistente Virtual UNEMI</h3>
        </div>
        <div class="header-right">
          <div class="status-indicator">
            <span class="status-dot" class:connected={isConnected}></span>
            <span class="status-text"
              >{isConnected ? "Conectado" : "Desconectado"}</span
            >
          </div>
          <button class="close-btn" on:click={toggleChat} title="Cerrar chat">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>

      {#if error}
        <div class="error-message">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle
              cx="10"
              cy="10"
              r="9"
              stroke="currentColor"
              stroke-width="2"
            />
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

      <div class="messages-container" bind:this={chatContainer}>
        {#if messages.length === 0}
          <div class="empty-state">
            <div class="empty-icon">
              <svg
                width="64"
                height="64"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#cbd5e1"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
                ></path>
              </svg>
            </div>
            <h4>¡Hola! 👋 Soy tu asistente virtual UNEMI</h4>
            <p>
              Estoy aquí para ayudarte con información sobre trámites,
              servicios, reglamentos y más. Escríbeme tu consulta cuando
              quieras.
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
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                  </svg>
                {:else}
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path d="M12 8V4H8"></path>
                    <rect x="4" y="8" width="16" height="12" rx="2"></rect>
                    <path d="M2 14h2"></path>
                    <path d="M20 14h2"></path>
                    <path d="M15 13v2"></path>
                    <path d="M9 13v2"></path>
                  </svg>
                {/if}
              </div>

              <div class="message-content">
                {@html formatMessage(message.content)}

                {#if message.offerHandoff}
                  <div class="handoff-buttons">
                    <button
                      class="btn-yes"
                      class:selected={message.selectedOption === "yes"}
                      on:click={() => confirmHandoff(idx)}
                      disabled={message.handoffResolved}
                    >
                      🧑‍💻 Sí, contactar a un humano
                    </button>

                    <button
                      class="btn-no"
                      class:selected={message.selectedOption === "no"}
                      on:click={() => cancelHandoff(idx)}
                      disabled={message.handoffResolved}
                    >
                      Continuar conversando
                    </button>
                  </div>
                {/if}

                {#if message.isRagConfirmation}
                  <div class="handoff-buttons">
                    <button
                      class="btn-yes"
                      class:selected={message.selectedOption === "yes"}
                      on:click={() =>
                        confirmRag(idx, message.reformulatedQuery)}
                      disabled={message.confirmationResolved}
                    >
                      Sí, buscar
                    </button>

                    <button
                      class="btn-no"
                      class:selected={message.selectedOption === "no"}
                      on:click={() => rejectRag(idx)}
                      disabled={message.confirmationResolved}
                    >
                      No
                    </button>
                  </div>
                {/if}

                {#if message.sources && message.sources.length > 0}
                  <div class="sources-container">
                    <p class="sources-title">Fuentes:</p>
                    <div class="badges-wrapper">
                      {#each message.sources as source}
                        {#if source.url}
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            class="badge clickable"
                            title="Clic para ver documento original"
                          >
                            {source.title || "Documento"}
                            <svg
                              width="10"
                              height="10"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              stroke-width="3"
                              stroke-linecap="round"
                              stroke-linejoin="round"
                              style="margin-left:2px;"
                            >
                              <path
                                d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"
                              ></path>
                              <polyline points="15 3 21 3 21 9"></polyline>
                              <line x1="10" y1="14" x2="21" y2="3"></line>
                            </svg>
                          </a>
                        {:else}
                          <span class="badge" title="Fuente sin enlace">
                            {source.title || "Documento"}
                          </span>
                        {/if}
                      {/each}
                    </div>
                  </div>
                {/if}
              </div>
            </div>
          {/each}
        {/if}

        {#if isLoading}
          <div class="message assistant">
            <div class="message-avatar">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M12 8V4H8"></path>
                <rect x="4" y="8" width="16" height="12" rx="2"></rect>
                <path d="M2 14h2"></path>
                <path d="M20 14h2"></path>
                <path d="M15 13v2"></path>
                <path d="M9 13v2"></path>
              </svg>
            </div>
            <div class="message-content loading">
              {#if loadingText}
                <span class="loading-text">{loadingText}</span>
              {/if}
              <div class="typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        {/if}
      </div>

      <div class="input-container">
        <textarea
          bind:this={messageInputEl}
          bind:value={inputMessage}
          on:keypress={handleKeyPress}
          placeholder={isHandoffPending
            ? "Por favor selecciona una opción arriba 👆"
            : "Escribe aquí tu consulta 😊… "}
          disabled={isLoading || !isConnected || isHandoffPending}
          rows="1"
          style="flex: 1; min-height: 44px;"
        ></textarea>

        <button
          on:click={() => sendMessage(false)}
          class="send-btn"
          disabled={isLoading || !isConnected || !inputMessage.trim() || isHandoffPending}
          title="Enviar mensaje"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            style="transform: translateX(-1px) translateY(1px);"
          >
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  /* --- CHATBOT FLOTANTE --- */
  .chatbot-floating-wrapper {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 9999; /* Alto z-index para estar sobre todo */
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }

  /* Botón flotante para abrir el chat */
  .chatbot-toggle-btn {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, #1e3a5f 0%, #2c4a6b 100%);
    border: none;
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 20px rgba(30, 58, 95, 0.4);
    transition: all 0.3s ease;
    position: relative;
  }

  .chatbot-toggle-btn:hover {
    transform: scale(1.1);
    box-shadow: 0 6px 25px rgba(30, 58, 95, 0.5);
  }

  .chatbot-toggle-btn:active {
    transform: scale(0.95);
  }

  .notification-badge {
    position: absolute;
    top: 4px;
    right: 4px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #999;
    border: 2px solid white;
    box-shadow: 0 0 4px rgba(0, 0, 0, 0.2);
  }

  .notification-badge.connected {
    background: #4ade80;
    box-shadow: 0 0 6px rgba(74, 222, 128, 0.6);
    animation: pulse 2s infinite;
  }

  /* Container del chat cuando está abierto */
  .chatbot-container {
    width: 470px;
    height: 600px;
    max-height: calc(100vh - 40px);
    display: flex;
    flex-direction: column;
    background-color: #ffffff;
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    overflow: hidden;
    animation: slideUp 0.3s ease-out;
  }

  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(20px) scale(0.95);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  /* Responsive: en móvil el chat ocupa más espacio */
  @media (max-width: 480px) {
    .chatbot-floating-wrapper {
      bottom: 10px;
      right: 10px;
      left: 10px;
    }

    .chatbot-container {
      width: 100%;
      height: calc(100vh - 20px);
      max-height: calc(100vh - 20px);
    }
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

  .close-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background: rgba(255, 255, 255, 0.15);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
    backdrop-filter: blur(10px);
    flex-shrink: 0;
  }
  .close-btn svg {
    flex-shrink: 0;
    display: block;
  }
  .close-btn:hover {
    background: rgba(255, 107, 53, 0.2);
    border-color: #ff6b35;
    transform: translateY(-1px);
  }
  .close-btn:hover svg {
    stroke: #ffffff;
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
    max-width: 100%;
    box-sizing: border-box;
  }
  
  /* Responsive: ajustar en pantallas pequeñas */
  @media (max-width: 768px) {
    .message-content {
      max-width: 85%;
    }
    
    .messages-container {
      padding: 12px;
    }
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
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    color: #ffffff;
  }

  .message.user .message-avatar {
    background: linear-gradient(135deg, #1e3a5f 0%, #2c4a6b 100%);
  }

  .message.assistant .message-avatar {
    background: linear-gradient(135deg, #ff6b35 0%, #ff8c5a 100%);
  }

  .message-content {
    max-width: 75%;
    min-width: 0; /* Permite que se ajuste correctamente */
    padding: 14px 18px;
    border-radius: 16px;
    word-wrap: break-word;
    overflow-wrap: break-word; /* Asegura que las palabras largas se corten */
    word-break: break-word; /* Permite cortar palabras muy largas */
    line-height: 1.6;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    hyphens: auto; /* Agrega guiones automáticos cuando sea necesario */
  }
  
  /* Estilos para texto dentro del mensaje */
  .message-content strong {
    font-weight: 600;
    color: inherit;
  }
  
  .message.assistant .message-content strong {
    color: #1e3a5f;
  }
  
  .message.user .message-content strong {
    color: #ffffff;
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
    align-items: center;
  }

  .input-container textarea {
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

  .loading-text {
    font-size: 14px;
    color: #64748b;
    margin: 0;
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

  .sources-container {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(0, 0, 0, 0.1);
  }
  .sources-title {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
    margin: 0 0 6px 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .badges-wrapper {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 6px 10px; /* Un poco más grande para facilitar el clic */
    background: rgba(255, 107, 53, 0.1);
    color: #c2410c;
    border: 1px solid rgba(255, 107, 53, 0.2);
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    transition: all 0.2s ease;
    text-decoration: none; /* Quitar subrayado por defecto de enlaces */
    max-width: 512px;
    text-wrap: auto;
    text-align: left;
  }

  /* Estilo específico cuando es un link */
  .badge.clickable:hover {
    background: rgba(255, 107, 53, 0.25);
    transform: translateY(-2px);
    cursor: pointer;
    box-shadow: 0 2px 5px rgba(255, 107, 53, 0.2);
    border-color: #ff6b35;
  }

  /* ESTILOS NUEVOS PARA LOS BOTONES DE DECISIÓN */
  .handoff-buttons {
    display: flex;
    gap: 10px;
    margin-top: 15px;
    flex-wrap: wrap;
  }
  .btn-yes {
    background-color: #1e3a5f;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    transition: background 0.2s;
  }

  .btn-no {
    background-color: transparent;
    border: 1px solid #cbd5e1;
    padding: 8px 16px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    color: #1e293b;
  }
  .btn-no:hover {
    background-color: #f1f5f9;
    color: #1e293b;
  }

  .handoff-buttons button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    pointer-events: none; /* Evita clics extra */
  }
  .btn-yes.selected {
    background-color: #2c4a6b !important; /* Un azul más oscuro */
    border-color: #2c4a6b;
  }

  .btn-no.selected {
    background-color: #e2e8f0 !important;
    color: #94a3b8;
  }

  /* --- NUEVOS ESTILOS DE LAYOUT Y START PANEL --- */

  .content-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    height: 100%;
    position: relative;
    background-color: #f1f5f9;
  }

  /* .layout-header, .content-wrapper REMOVED (logic moved to App.svelte) */

  .start-panel {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    text-align: center;
    color: #64748b;
    background: #f8fafc;
    border-radius: 12px;
    margin: 20px;
    border: 2px dashed #cbd5e1;
    padding: 40px;
  }

  .start-panel h4 {
    margin-top: 0;
    margin-bottom: 10px;
    color: #1e293b;
    font-size: 1.25rem;
  }

  .start-panel p {
    margin: 0;
    max-width: 300px;
    line-height: 1.5;
  }

</style>
