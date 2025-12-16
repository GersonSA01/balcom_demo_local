<script>
  import { onMount, tick } from "svelte";
  // Eliminadas importaciones de UserSelector y Menu

  // PROPS
  export let chatOpened = false;
  export let sessionData = {};

  let messageInputEl;
  let chatContainer; // Referencia al div de mensajes
  let messages = [];
  let inputMessage = "";
  let isLoading = false;
  let error = null;
  let isConnected = false;

  // let sessionData es ahora Prop
  // let dataUnemi Eliminado (lo maneja App)

  let handoffMode = false;
  let showUploadAction = false;
  let isUploadOptional = false;

  // Eliminado estado de Menu y Servicios

  // --- NUEVO: Estado para Subida Directa ---
  let fileInput; // Referencia al input file oculto
  let uploadedFile = null;
  let isUploading = false;

  const API_BASE_URL = "http://localhost:9090/api/chatbot";

  // Eliminado loadDataUnemi

  async function openChatOnly() {
    chatOpened = true; // 👈 abre el chat (actualiza prop via bind)
    await tick(); // esperar DOM
    messageInputEl?.focus(); // focus al input
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
    if (isLoading || (!inputMessage.trim() && !uploadedFile && !isHidden))
      return;

    if (uploadedFile) {
      await uploadAndSend();
      return;
    }

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

      // 1) Determina si esta request debe ir en modo handoff
      const willSendHandoffMode = handoffMode === true;

      // 2) Construye el body incluyendo el flag
      const requestBody = {
        message: userMessage,
        history: history,
        session_data: sessionDataToSend,
        handoff_mode: willSendHandoffMode, // NUEVO
      };

      // 3) Apaga el flag INMEDIATAMENTE (one-shot) si lo acabas de usar
      if (willSendHandoffMode) {
        handoffMode = false;
      }

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
              if (data.payload && data.payload.handoff_mode) {
                handoffMode = true; // Se activa el estado para indicar que estamos en modo Handoff
              }

              // LOGICA DE UPLOAD (Existente)
              if (data.payload && data.payload.need_documentation) {
                showUploadAction = true;
                isUploadOptional = data.payload.upload_optional || false;
              } else {
                showUploadAction = false;
                isUploadOptional = false;
              }

              const isRagConfirm = data.action === "RAG_CONFIRMATION";

              // AQUÍ GUARDAMOS LA BANDERA offerHandoff
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
        { role: "assistant", content: "Error de conexión." },
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

  function clearChat() {
    messages = [];
    error = null;
    showUploadAction = false;
  }

  function goToUpload() {
    // Simula clic en el input file oculto
    fileInput.click();
  }

  function handleFileSelect(e) {
    if (e.target.files.length > 0) {
      uploadedFile = e.target.files[0];
      // El usuario ya seleccionó archivo, desbloqueamos el input (visual)
    }
  }

  function removeFile() {
    uploadedFile = null;
    if (fileInput) fileInput.value = "";
  }

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

  async function uploadAndSend() {
    if (!uploadedFile) return; // Validación extra

    isUploading = true;
    const details = inputMessage.trim();

    // 1. Guardamos referencia local del archivo para enviarlo
    const fileToSend = uploadedFile;
    const detailsToSend = details;

    // 2. LIMPIEZA INMEDIATA (Optimistic UI)
    // Quitamos el archivo y texto de la vista del usuario AHORA MISMO
    uploadedFile = null;
    inputMessage = "";
    if (fileInput) fileInput.value = "";
    showUploadAction = false;

    // 3. Agregamos el mensaje del usuario al chat visualmente
    messages = [
      ...messages,
      {
        role: "user",
        content: `Archivo enviado: ${fileToSend.name}${detailsToSend ? `\nDetalles: ${detailsToSend}` : ""}`,
      },
    ];
    // scrollToBottom(); // Eliminado por reactividad

    try {
      const formData = new FormData();
      formData.append("file", fileToSend); // Usamos la referencia guardada
      formData.append("details", detailsToSend);

      // 4. Hacemos la petición (el usuario ya ve el chat limpio)
      const response = await fetch(`${API_BASE_URL}/documentacion/subir/`, {
        method: "POST",
        body: formData,
      });

      const result = await response.json();

      if (result.status === "success") {
        // Respuesta del Bot
        messages = [
          ...messages,
          {
            role: "assistant",
            content:
              result.ai_response ||
              "¡Perfecto! Tu documento fue recibido sin problemas.",
          },
        ];
        // scrollToBottom(); // Eliminado por reactividad
      } else {
        // Si falla, mostramos error
        messages = [
          ...messages,
          {
            role: "assistant",
            content: `Error al subir archivo: ${result.message || "Intenta de nuevo."}`,
          },
        ];
        // scrollToBottom();
      }
    } catch (e) {
      console.error("Error subiendo:", e);
      messages = [
        ...messages,
        {
          role: "assistant",
          content:
            "No pude subir tu documento por un problema de conexión. Por favor intenta nuevamente.",
        },
      ];
      // scrollToBottom();
    } finally {
      isUploading = false;
    }
  }

  $: lastMessage = messages[messages.length - 1];
  $: isHandoffPending =
    lastMessage && lastMessage.offerHandoff && !lastMessage.handoffResolved;

  // --- NUEVA FUNCIÓN: Manejar clic en "Sí, contactar humano" ---
  // Modificar en la sección

  async function confirmHandoff(index) {
  // 1) Bloqueo visual
  messages[index].handoffResolved = true;
  messages[index].selectedOption = "yes";
  messages = [...messages];

  // 2) Activar modo handoff (one-shot) + mandar comando (NO vacío)
  handoffMode = true;
  inputMessage = "HUMAN_HANDOFF";
  await sendMessage(true);
}


  function cancelHandoff(index) {
    messages[index].handoffResolved = true;
    messages[index].selectedOption = "no";
    messages = [...messages];

    // Simplemente agregamos el mensaje visual y seguimos normal
    messages = [
      ...messages,
      { role: "user", content: "No, gracias. Seguiré conversando." },
    ];
  }

  // --- LÓGICA DEL MENÚ ---
  async function loadServiciosEstudiante() {
    if (!sessionData) return;
    const cedula = Object.keys(sessionData)[0];
    if (!cedula) return;

    try {
      const resp = await fetch(
        `${API_BASE_URL}/api/servicios-estudiante/?cedula=${cedula}`,
      );
      if (resp.ok) {
        const data = await resp.json();
        // El backend devuelve { categorias: [...], ... }
        serviciosEstudianteData = data.categorias || [];
      } else {
        serviciosEstudianteData = [];
      }
    } catch (e) {
      console.error("Error cargando servicios:", e);
      serviciosEstudianteData = [];
    }
  }
</script>

<!-- EL LAYOUT SE MANEJA EN APP.SVELTE -->
<div class="chatbot-container-wrapper">
  {#if !chatOpened}
  <div class="start-box">
    <img class="start-img" src="/solicitud_balcon.jpg" alt="Seleccione un servicio para comenzar" />
  </div>
{:else}
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
                {@html message.content.replace(/\n/g, "<br>")}

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
        <input
          type="file"
          style="display: none;"
          bind:this={fileInput}
          on:change={handleFileSelect}
          accept=".pdf,.jpg,.jpeg,.png"
        />

        {#if showUploadAction}
          <button
            class="upload-icon-btn"
            on:click={goToUpload}
            title="Se requiere documentación. Clic para subir."
            disabled={isLoading || !isConnected}
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
            >
              <path
                d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"
              ></path>
            </svg>
            <span class="notification-dot"></span>
          </button>
        {/if}

        <div style="flex: 1; display: flex; flex-direction: column;">
          {#if uploadedFile}
            <div class="file-preview">
              <span style="display:flex; align-items:center; gap:5px;">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  ><path
                    d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"
                  ></path><polyline points="13 2 13 9 20 9"></polyline></svg
                >
                {uploadedFile.name}
              </span>
              <button
                class="remove-file-btn"
                on:click={removeFile}
                title="Quitar archivo">&times;</button
              >
            </div>
          {/if}

          <textarea
            bind:this={messageInputEl}
            bind:value={inputMessage}
            on:keypress={handleKeyPress}
            placeholder={showUploadAction && !uploadedFile && !isUploadOptional
              ? "Por favor sube el documento obligatoriamente..."
              : showUploadAction && isUploadOptional && !uploadedFile
                ? "Describe tu caso o sube una evidencia (opcional)..."
                : isHandoffPending
                  ? "Por favor selecciona una opción arriba 👆"
                  : "Escribe aquí tu consulta… estoy listo para ayudarte 😊"}
            disabled={isLoading ||
              !isConnected ||
              (showUploadAction && !uploadedFile && !isUploadOptional) ||
              isHandoffPending}
            rows="1"
            style="min-height: 44px;"
          ></textarea>
        </div>

        <button
          on:click={() => sendMessage(false)}
          class="send-btn"
          disabled={isLoading ||
            !isConnected ||
            (!inputMessage.trim() && !uploadedFile) ||
            (showUploadAction && !uploadedFile && !isUploadOptional) ||
            isHandoffPending}
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

<!-- Fin main-layout -->

<!-- Fin chatbot-wrapper y main-layout -->

<style>
  /* --- LAYOUT PRINCIPAL (Flexbox) --- */
  /* --- LAYOUT PRINCIPAL (Flexbox) --- */

  .chatbot-container-wrapper {
    flex: 1; /* El chat toma el resto */
    display: flex;
    justify-content: center; /* Centramos el chat si se desea, o full width */
    height: 100%;
    position: relative;
    overflow: hidden; /* Importante para que no crezca más de la cuenta */
  }

  /* Ajustes al container original del chatbot para que se comporte bien dentro del wrapper */
  .chatbot-container {
    width: 100%;
    max-width: 100%; /* Quitamos max-width fijo si queremos que llene, o lo mantenemos */
    height: 100%; /* Altura full del padre */
    display: flex;
    flex-direction: column;
    background-color: #ffffff;
    /* Eliminamos márgenes auto o sombras externas si queremos un look "panel completo" */
    box-shadow: none;
    border-radius: 0;
  }

  /* --- ESTILOS ANTIGUOS --- */
  .upload-icon-btn {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border: 2px solid #e2e8f0;
    background: #f8fafc;
    border-radius: 10px; /* Cuadrado redondeado */
    color: #64748b;
    cursor: pointer;
    transition: all 0.2s ease;
    flex-shrink: 0;
  }
  .upload-icon-btn svg {
    width: 20px; /* Forzamos el ancho */
    height: 20px; /* Forzamos el alto */
    stroke: #64748b; /* Aseguramos el color base */
    flex-shrink: 0; /* Evita que el flexbox lo aplaste */
  }

  .upload-icon-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: #f1f5f9;
  }

  .notification-dot {
    position: absolute;
    top: -2px;
    right: -2px;
    width: 10px;
    height: 10px;
    background-color: #ef4444; /* Rojo */
    border: 2px solid #ffffff;
    border-radius: 50%;
    animation: pulse-red 2s infinite;
  }

  @keyframes pulse-red {
    0% {
      transform: scale(0.95);
      box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
    }
    70% {
      transform: scale(1);
      box-shadow: 0 0 0 6px rgba(239, 68, 68, 0);
    }
    100% {
      transform: scale(0.95);
      box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
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
    align-items: center;
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

  /* NUEVOS ESTILOS PARA BOTÓN UPLOAD */
  .upload-btn {
    position: relative;
    padding: 12px;
    background: #f1f5f9;
    color: #64748b;
    border: 2px solid #e2e8f0;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .upload-btn:hover {
    background: #e2e8f0;
    color: #1e3a5f;
    border-color: #cbd5e1;
  }
  /* Indicador rojo de que se requiere acción */
  .upload-dot {
    position: absolute;
    top: -2px;
    right: -2px;
    width: 10px;
    height: 10px;
    background-color: #ef4444;
    border-radius: 50%;
    border: 2px solid white;
    animation: pulse-red 2s infinite;
  }
  @keyframes pulse-red {
    0% {
      transform: scale(0.95);
      box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
    }
    70% {
      transform: scale(1);
      box-shadow: 0 0 0 6px rgba(239, 68, 68, 0);
    }
    100% {
      transform: scale(0.95);
      box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
    }
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
  }

  /* Estilo específico cuando es un link */
  .badge.clickable:hover {
    background: rgba(255, 107, 53, 0.25);
    transform: translateY(-2px);
    cursor: pointer;
    box-shadow: 0 2px 5px rgba(255, 107, 53, 0.2);
    border-color: #ff6b35;
  }

  /* Estilos para el indicador de archivo seleccionado */
  .file-preview {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 8px;
    margin: 0 16px 8px 16px;
    color: #0369a1;
    font-size: 13px;
    animation: slideDown 0.2s ease-out;
  }
  @keyframes slideDown {
    from {
      opacity: 0;
      transform: translateY(-5px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .remove-file-btn {
    background: none;
    border: none;
    color: #0369a1;
    font-weight: bold;
    cursor: pointer;
    padding: 0 4px;
    font-size: 16px;
  }
  .remove-file-btn:hover {
    color: #0c4a6e;
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


  .start-box{
  height: 100%;
  display: grid;
  place-items: center;
}

.start-img{
  width: auto;
  max-width: 750px;
  max-height: 500px;
  object-fit: contain;
  background: #fff;
}

</style>
