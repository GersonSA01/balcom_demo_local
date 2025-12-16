<script>
  import { onMount } from "svelte";
  import Chatbot from "./lib/Chatbot.svelte";
  import UserSelector from "./lib/UserSelector.svelte";
  import Menu from "./lib/_menu.svelte";
  import SolicitudesPanel from "./lib/_solicitudesinfo.svelte";

  export let url = "";

  // Estado Global
  let sessionData = {};
  let serviciosEstudianteData = [];
  let dataUnemi = {};
  let chatOpened = false;
  let showMenu = true;

  // Refs
  let chatbotComponent;

  const API_BASE_URL = "http://localhost:9090/api/chatbot";

  async function loadDataUnemi() {
    try {
      const response = await fetch(`${API_BASE_URL}/users/`);
      if (!response.ok) throw new Error("Error fetching users");
      dataUnemi = await response.json();
    } catch (e) {
      console.error("Error cargando usuarios desde API:", e);
    }
  }

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
        serviciosEstudianteData = data.categorias || [];
      } else {
        serviciosEstudianteData = [];
      }
    } catch (e) {
      serviciosEstudianteData = [];
    }
  }

  function handleSessionUpdate(event) {
    sessionData = event.detail;
    // Guardar en LC si es necesario, UserSelector ya lanza el evento
    // pero idealmente UserSelector ya maneja su persistencia, aquí solo reaccionamos.
    loadServiciosEstudiante();
  }

  function handleMenuAction(event) {
    const { action } = event.detail;
    if (action === "selectProceso") {
      chatOpened = true; // Abrir Chat
      // Podríamos llamar a un método del chatbot si fuera necesario
      // chatbotComponent.focusInput();
    }
  }

  onMount(() => {
    loadDataUnemi();
    // Recuperar sesión inicial si existe
    const stored = localStorage.getItem("user_session_data");
    if (stored) {
      try {
        sessionData = JSON.parse(stored);
        loadServiciosEstudiante();
      } catch (e) {}
    }
  });
</script>

<div class="app-layout">
  <!-- HEADER SUPERIOR -->
  <div class="layout-header">
    <div class="brand">
      <div class="subtitle">Balcón de Servicios</div>
    </div>
    <div class="user-controls">
      <UserSelector {dataUnemi} on:session-update={handleSessionUpdate} />
    </div>
  </div>

  <!-- CONTENIDO PRINCIPAL (Sidebar + Chat) -->
<div class="main-content">
  {#if serviciosEstudianteData.length > 0 && showMenu}
    <aside class="sidebar">
      <div class="sidebar-inner">
        <Menu eCategorias={serviciosEstudianteData} on:actionRun={handleMenuAction} />
      </div>
    </aside>
  {/if}

  <main class="chat-area">
    <Chatbot bind:this={chatbotComponent} bind:chatOpened {sessionData} />
  </main>

  <!-- PANEL DERECHO SIMULADO -->
  <aside class="right-panel">
    <div class="right-inner">
      <SolicitudesPanel />
    </div>
  </aside>
</div>

</div>

<style>

  body {
  background-color: #f1f5f9;
}

.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.layout-header {
  background: #ffffff;
  height: 70px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

/* ✅ AQUÍ está el cambio principal */
.main-content {
  flex: 1;
  display: flex;
  gap: 16px;          /* separación entre sidebar y chat */
  padding: 16px;      /* separación con bordes de la pantalla */
  background: #f1f5f9;
  overflow: hidden;   /* evita scroll doble, el scroll vive dentro */
  min-height: 0;
}

.sidebar {
  width: 300px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  overflow: hidden;   /* para que el radio recorte el contenido */
  flex-shrink: 0;
  min-height: 0;
}

.sidebar-inner {
  height: 100%;
  overflow-y: auto;   /* scroll aquí */
  padding: 12px;      /* aire interno del menú */
}

.chat-area {
  flex: 1;
  min-width: 0;       /* 🔥 importantísimo para que no se rompa en flex */
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Responsive opcional */
@media (max-width: 900px) {
  .main-content { padding: 12px; gap: 12px; }
  .sidebar { width: 260px; }
}
@media (max-width: 720px) {
  .main-content { flex-direction: column; }
  .sidebar { width: 100%; max-height: 45vh; }
}

.right-panel {
  width: 340px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  overflow: hidden;
  flex-shrink: 0;
  min-height: 0;
}

.right-inner {
  height: 100%;
  padding: 12px;
  overflow: hidden;
}

/* Responsive: en móvil lo bajas abajo */
@media (max-width: 1100px) {
  .right-panel { width: 300px; }
}
@media (max-width: 900px) {
  .main-content { flex-direction: column; }
  .right-panel { width: 100%; }
}


</style>
