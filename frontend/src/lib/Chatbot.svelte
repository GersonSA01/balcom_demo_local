<script>
  let messages = [];
  let inputMessage = '';
  let isLoading = false;
  let error = null;
  let isConnected = false;
  let configuredModel = 'phi3:mini';

  const API_BASE_URL = 'http://localhost:8000/api/chatbot';

  // Verificar conexión con Ollama al cargar
  async function checkConnection() {
    try {
      const response = await fetch(`${API_BASE_URL}/health/`);
      const data = await response.json();
      
      // Usar model_available en lugar de phi3_available
      isConnected = data.ollama_connected && data.model_available;
      
      if (data.model_configured) {
        configuredModel = data.model_configured;
      }
      
      if (!isConnected) {
        if (!data.ollama_connected) {
          error = data.error || 'Ollama no está disponible. Asegúrate de que Ollama esté ejecutándose.';
        } else if (!data.model_available) {
          error = `El modelo ${configuredModel} no está instalado. Ejecuta: ollama pull ${configuredModel}`;
        } else {
          error = data.error || `Ollama no está disponible o ${configuredModel} no está instalado`;
        }
      }
    } catch (err) {
      isConnected = false;
      error = 'No se pudo conectar con el servidor Django. Verifica que el servidor esté ejecutándose.';
    }
  }

  async function sendMessage() {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage.trim();
    inputMessage = '';
    error = null;

    // Agregar mensaje del usuario
    messages = [...messages, { role: 'user', content: userMessage }];
    isLoading = true;

    try {
      // Preparar historial de conversación
      const history = messages.slice(0, -1).map(msg => ({
        role: msg.role,
        content: msg.content
      }));

      const response = await fetch(`${API_BASE_URL}/chat/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          history: history
        })
      });

      const data = await response.json();

      if (response.ok) {
        // El backend retorna diferentes tipos según la intención:
        // 1. rag_response: Respuesta generada con RAG (consulta informativa)
        // 2. agent_handoff: Trámite operativo que requiere agente humano
        // 3. simple_text: Saludo u otros casos simples
        
        let responseText = '';
        
        if (data.type === 'rag_response') {
          // Respuesta del RAG (consulta informativa)
          responseText = data.text || 'No pude generar una respuesta.';
          
          // Agregar fuentes si están disponibles
          if (data.sources && data.sources.length > 0) {
            responseText += `\n\n📚 Fuentes: ${data.sources.join(', ')}`;
          }
        } else if (data.type === 'agent_handoff') {
          // Trámite operativo - mensaje de handoff
          responseText = data.text || 'Un agente se pondrá en contacto contigo.';
        } else if (data.type === 'simple_text') {
          // Saludo u otros casos simples
          responseText = data.text || 'No entendí tu consulta.';
        } else {
          // Fallback
          responseText = data.text || JSON.stringify(data, null, 2);
        }
        
        messages = [...messages, { role: 'assistant', content: responseText }];
      } else {
        error = data.error || 'Error al obtener respuesta';
        // Remover el último mensaje del usuario si hay error
        messages = messages.slice(0, -1);
      }
    } catch (err) {
      error = 'Error de conexión: ' + err.message;
      messages = messages.slice(0, -1);
    } finally {
      isLoading = false;
    }
  }

  function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  function clearChat() {
    messages = [];
    error = null;
  }

  // Verificar conexión al montar el componente
  checkConnection();
</script>

<div class="chatbot-container">
  <div class="chatbot-header">
    <h3>Chatbot - {configuredModel}</h3>
    <div class="status-indicator">
      <span class="status-dot" class:connected={isConnected}></span>
      <span class="status-text">{isConnected ? 'Conectado' : 'Desconectado'}</span>
    </div>
    {#if messages.length > 0}
      <button class="clear-btn" on:click={clearChat}>Limpiar</button>
    {/if}
  </div>

  {#if error}
    <div class="error-message">
      ⚠️ {error}
    </div>
  {/if}

  <div class="messages-container">
    {#if messages.length === 0}
      <div class="empty-state">
        <p>👋 ¡Hola! Soy tu asistente virtual. ¿En qué puedo ayudarte?</p>
        <p class="hint">Asegúrate de que Ollama esté ejecutándose y que tengas el modelo {configuredModel} instalado.</p>
      </div>
    {:else}
      {#each messages as message (message)}
        <div class="message" class:user={message.role === 'user'} class:assistant={message.role === 'assistant'}>
          <div class="message-content">
            {message.content}
          </div>
        </div>
      {/each}
    {/if}
    {#if isLoading}
      <div class="message assistant">
        <div class="message-content loading">
          <span class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </span>
        </div>
      </div>
    {/if}
  </div>

  <div class="input-container">
    <textarea
      bind:value={inputMessage}
      on:keypress={handleKeyPress}
      placeholder="Escribe tu mensaje aquí..."
      disabled={isLoading || !isConnected}
      rows="2"
    ></textarea>
    <button
      on:click={sendMessage}
      disabled={isLoading || !isConnected || !inputMessage.trim()}
      class="send-btn"
    >
      {#if isLoading}
        <span class="spinner"></span>
      {:else}
        ➤
      {/if}
    </button>
  </div>
</div>

<style>
  .chatbot-container {
    display: flex;
    flex-direction: column;
    height: 600px;
    max-width: 800px;
    margin: 0 auto;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    background: white;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .chatbot-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid #e0e0e0;
    background: #f5f5f5;
    border-radius: 8px 8px 0 0;
  }

  .chatbot-header h3 {
    margin: 0;
    font-size: 18px;
    color: #333;
  }

  .status-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #ccc;
    transition: background 0.3s;
  }

  .status-dot.connected {
    background: #4caf50;
  }

  .status-text {
    font-size: 12px;
    color: #666;
  }

  .clear-btn {
    padding: 6px 12px;
    background: #f44336;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    transition: background 0.2s;
  }

  .clear-btn:hover {
    background: #d32f2f;
  }

  .error-message {
    padding: 12px 16px;
    background: #ffebee;
    color: #c62828;
    border-bottom: 1px solid #ffcdd2;
    font-size: 14px;
  }

  .messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    text-align: center;
    color: #666;
  }

  .empty-state p {
    margin: 8px 0;
  }

  .hint {
    font-size: 12px;
    color: #999;
    font-style: italic;
  }

  .message {
    display: flex;
    margin-bottom: 8px;
  }

  .message.user {
    justify-content: flex-end;
  }

  .message.assistant {
    justify-content: flex-start;
  }

  .message-content {
    max-width: 70%;
    padding: 12px 16px;
    border-radius: 12px;
    word-wrap: break-word;
    white-space: pre-wrap;
  }

  .message.user .message-content {
    background: #2196f3;
    color: white;
    border-bottom-right-radius: 4px;
  }

  .message.assistant .message-content {
    background: #f1f1f1;
    color: #333;
    border-bottom-left-radius: 4px;
  }

  .message-content.loading {
    background: #f1f1f1;
    padding: 16px;
  }

  .typing-indicator {
    display: flex;
    gap: 4px;
  }

  .typing-indicator span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #999;
    animation: typing 1.4s infinite;
  }

  .typing-indicator span:nth-child(2) {
    animation-delay: 0.2s;
  }

  .typing-indicator span:nth-child(3) {
    animation-delay: 0.4s;
  }

  @keyframes typing {
    0%, 60%, 100% {
      transform: translateY(0);
      opacity: 0.7;
    }
    30% {
      transform: translateY(-10px);
      opacity: 1;
    }
  }

  .input-container {
    display: flex;
    padding: 12px;
    border-top: 1px solid #e0e0e0;
    gap: 8px;
    background: #fafafa;
    border-radius: 0 0 8px 8px;
  }

  .input-container textarea {
    flex: 1;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 6px;
    resize: none;
    font-family: inherit;
    font-size: 14px;
  }

  .input-container textarea:focus {
    outline: none;
    border-color: #2196f3;
  }

  .input-container textarea:disabled {
    background: #f5f5f5;
    cursor: not-allowed;
  }

  .send-btn {
    padding: 10px 20px;
    background: #2196f3;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 18px;
    transition: background 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 50px;
  }

  .send-btn:hover:not(:disabled) {
    background: #1976d2;
  }

  .send-btn:disabled {
    background: #ccc;
    cursor: not-allowed;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>

