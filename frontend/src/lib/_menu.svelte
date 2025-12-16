<script>
  import { createEventDispatcher } from "svelte";
  import { slide } from "svelte/transition";

  // Recibimos la lista de categorías procesada por tu backend
  export let eCategorias = [];

  const dispatch = createEventDispatcher();
  let activeIndex = null; // Controla qué categoría está abierta

  // Función para abrir/cerrar categorías (Acordeón nativo Svelte)
  function toggleAccordion(index) {
    if (activeIndex === index) {
      activeIndex = null; // Cerrar si ya está abierta
    } else {
      activeIndex = index; // Abrir la nueva
    }
  }

  // Función al hacer clic en un trámite específico
  function selectProcess(proceso) {
    // Despachamos el evento al padre (Chatbot.svelte)
    dispatch("actionRun", {
      action: "selectProceso",
      data: { item: proceso }, // Pasamos el objeto proceso completo (nombre, id, tiempo, etc)
    });
  }
</script>

<div class="menu-container">
  <h5 class="menu-title">Trámites y Servicios</h5>

  <div class="accordion-list">
    {#each eCategorias as categoria, index}
      <div class="accordion-item">
        <button
          class="accordion-header"
          class:active={activeIndex === index}
          on:click={() => toggleAccordion(index)}
        >
          <span class="cat-name">{categoria.nombre}</span>
          <svg
            class="chevron"
            class:rotate={activeIndex === index}
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>

        {#if activeIndex === index}
          <div class="accordion-body" transition:slide={{ duration: 300 }}>
            <div class="process-list">
              {#each categoria.procesos as proceso}
                <button
                  class="process-item"
                  on:click={() => selectProcess(proceso)}
                >
                  <div class="proc-info">
                    <span class="proc-name">{proceso.nombre}</span>
                  </div>
                  {#if proceso.tiempo_estimado}
                    <span class="proc-time" title="Tiempo estimado">
                      ⏱ {proceso.tiempo_estimado}
                    </span>
                  {/if}
                </button>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .menu-container {
    height: 100%;
    display: flex;
    flex-direction: column;
    background-color: #ffffff;
    font-family: 'Segoe UI', system-ui, sans-serif;
  }

  .menu-title {
    padding: 15px;
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    color: #1e3a5f;
    border-bottom: 1px solid #e2e8f0;
    background-color: #f8fafc;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .accordion-list {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
  }

  /* --- ESTILOS DEL ACORDEÓN --- */
  .accordion-item {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-bottom: 8px;
    overflow: hidden;
    background: white;
    transition: box-shadow 0.2s;
  }

  .accordion-item:hover {
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  }

  .accordion-header {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 15px;
    background: #ffffff;
    border: none;
    cursor: pointer;
    text-align: left;
    color: #334155;
    font-weight: 600;
    font-size: 0.95rem;
    transition: background 0.2s, color 0.2s;
  }

  .accordion-header:hover {
    background-color: #f1f5f9;
    color: #1e3a5f;
  }

  .accordion-header.active {
    background-color: #eff6ff; /* Azul muy claro */
    color: #1e3a5f;
    border-bottom: 1px solid #e2e8f0;
  }

  .cat-name {
    flex: 1;
    padding-right: 10px;
  }

  /* Animación de la flecha */
  .chevron {
    transition: transform 0.3s ease;
    color: #94a3b8;
  }
  .accordion-header.active .chevron {
    color: #ff6b35; /* Naranja corporativo */
  }
  .chevron.rotate {
    transform: rotate(180deg);
  }

  /* --- ESTILOS DE LOS PROCESOS (HIJOS) --- */
  .accordion-body {
    background-color: #f8fafc;
  }

  .process-list {
    display: flex;
    flex-direction: column;
  }

  .process-item {
    display: flex;
    flex-direction: column; /* Cambiado a columna para mejor layout de tiempo */
    align-items: flex-start;
    padding: 10px 15px 10px 20px; /* Indentado un poco a la izquierda */
    border: none;
    background: transparent;
    border-bottom: 1px solid #f1f5f9;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s;
    width: 100%;
    position: relative;
  }

  .process-item:last-child {
    border-bottom: none;
  }

  .process-item:hover {
    background-color: #ffffff;
    padding-left: 25px; /* Efecto de movimiento sutil */
  }

  .process-item:hover .proc-name {
    color: #ff6b35;
  }

  .proc-info {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }

  .proc-name {
    font-size: 0.9rem;
    color: #475569;
    font-weight: 500;
  }


  .proc-time {
    font-size: 0.75rem;
    color: #94a3b8;
    display: flex;
    align-items: center;
    gap: 4px;
  }

</style>