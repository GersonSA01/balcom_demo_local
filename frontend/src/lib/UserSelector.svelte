<script>
  import { onMount, createEventDispatcher } from "svelte";

  // Recibimos la data completa desde la vista de Django
  export let dataUnemi = [];

  // Dispatcher para eventos de Svelte
  const dispatch = createEventDispatcher();

  // Listas para los desplegables
  let personasList = [];
  let perfilesDisponibles = [];
  let periodosDisponibles = []; // <--- NUEVA LISTA PARA PERIODOS

  // Variables de selección (bindeables)
  let selectedCedula = "";
  let selectedPerfilId = "";
  let selectedPeriodoId = ""; // <--- NUEVA VARIABLE

  // 1. REACTIVIDAD INICIAL: Cuando llega la data desde el backend
  $: if (Array.isArray(dataUnemi) && dataUnemi.length > 0) {
    // Mapeamos solo lo necesario para el primer select
    personasList = dataUnemi.map((u) => ({
      cedula: String(u.cedula),
      nombre: u.nombre_completo || u.cedula,
    }));

    // Intentamos cargar lo guardado en localStorage
    loadSavedSelection();

    // Si no se cargó nada, seleccionamos el primero por defecto
    if (!selectedCedula && personasList.length > 0) {
      selectedCedula = personasList[0].cedula;
      handlePersonaChange();
    }
  }

  // 2. RECUPERAR SELECCIÓN GUARDADA
  function loadSavedSelection() {
    // Si ya tenemos una selección válida en memoria, no sobreescribir
    if (
      selectedCedula &&
      dataUnemi.find((u) => String(u.cedula) === String(selectedCedula))
    ) {
      return;
    }

    try {
      const stored = localStorage.getItem("user_session_data");
      if (stored) {
        const sessionData = JSON.parse(stored);
        // La estructura guardada es: { "CEDULA": { perfiles: [...], periodo_id: "..." } }
        const cedulaGuardada = Object.keys(sessionData)[0];
        const usuarioEncontrado = dataUnemi.find(
          (u) => String(u.cedula) === String(cedulaGuardada),
        );

        if (usuarioEncontrado) {
          selectedCedula = String(cedulaGuardada);

          // Actualizamos perfiles disponibles para este usuario
          perfilesDisponibles = usuarioEncontrado.perfiles || [];

          // Recuperamos el perfil ID guardado
          const datosGuardados = sessionData[cedulaGuardada];
          if (
            datosGuardados &&
            datosGuardados.perfiles &&
            datosGuardados.perfiles.length > 0
          ) {
            const perfilGuardado = datosGuardados.perfiles[0]; // Tomamos el objeto perfil guardado
            selectedPerfilId = String(perfilGuardado.id);

            // Lógica para recuperar Periodo
            updatePeriodosList(selectedPerfilId); // Llenamos la lista de periodos basada en el perfil

            if (datosGuardados.periodo_id) {
              // Verificamos si el periodo guardado aún existe en la lista permitida
              const existePeriodo = periodosDisponibles.some(
                (p) => String(p.id) === String(datosGuardados.periodo_id),
              );
              if (existePeriodo) {
                selectedPeriodoId = String(datosGuardados.periodo_id);
              }
            }
          }
        }
      }
    } catch (e) {
      console.error("Error cargando selección guardada:", e);
      localStorage.removeItem("user_session_data");
    }
  }

  // 3. HANDLERS (Manejadores de eventos)

  function handlePersonaChange() {
    // Al cambiar persona, reseteamos todo lo de abajo
    selectedPerfilId = "";
    selectedPeriodoId = "";
    perfilesDisponibles = [];
    periodosDisponibles = [];

    if (!selectedCedula) return;

    const usuarioData = dataUnemi.find(
      (u) => String(u.cedula) === String(selectedCedula),
    );
    if (usuarioData && usuarioData.perfiles) {
      perfilesDisponibles = usuarioData.perfiles;

      // Auto-seleccionar el primer perfil si existe
      if (perfilesDisponibles.length > 0) {
        selectedPerfilId = String(perfilesDisponibles[0].id);
        handlePerfilChange(); // Disparar cascada
      }
    }
    dispatchSelection();
  }

  function handlePerfilChange() {
    // Al cambiar perfil, actualizamos la lista de periodos
    updatePeriodosList(selectedPerfilId);
    dispatchSelection();
  }

  function handlePeriodoChange() {
    // Al cambiar periodo, solo guardamos/notificamos
    dispatchSelection();
  }

  // Helper para actualizar la lista de periodos
  function updatePeriodosList(perfilId) {
    selectedPeriodoId = ""; // Resetear selección actual
    periodosDisponibles = [];

    if (!perfilId) return;

    const perfilObj = perfilesDisponibles.find(
      (p) => String(p.id) === String(perfilId),
    );

    // Si el perfil tiene la lista 'periodos' (que viene del backend para estudiantes)
    if (perfilObj && perfilObj.periodos && perfilObj.periodos.length > 0) {
      periodosDisponibles = perfilObj.periodos;

      // Auto-seleccionar el primero (el más reciente según orden del backend)
      selectedPeriodoId = String(periodosDisponibles[0].id);
    }
  }

  // 4. GUARDAR Y EMITIR EVENTO
  function dispatchSelection() {
    if (!selectedCedula || !selectedPerfilId) return;

    const perfilObj = perfilesDisponibles.find(
      (p) => String(p.id) === String(selectedPerfilId),
    );
    if (!perfilObj) return;

    // Buscamos el objeto periodo completo si hay uno seleccionado
    let periodoObj = null;
    if (selectedPeriodoId) {
      periodoObj = periodosDisponibles.find(
        (p) => String(p.id) === String(selectedPeriodoId),
      );
    }

    // Estructura a guardar
    const sessionPayload = {
      [selectedCedula]: {
        perfiles: [perfilObj], // Mantenemos formato array por compatibilidad
        periodo_id: selectedPeriodoId || null, // Guardamos ID suelto
        periodo: periodoObj || null, // Guardamos objeto completo por si es útil
      },
    };

    // Guardar en localStorage
    localStorage.setItem("user_session_data", JSON.stringify(sessionPayload));

    // ✅ Emitir evento de Svelte (para App.svelte)
    dispatch("session-update", sessionPayload);

    // ✅ Emitir evento global para compatibilidad con otros componentes
    const event = new CustomEvent("sessionDataUpdated", {
      detail: sessionPayload,
    });
    window.dispatchEvent(event);
  }
</script>

<div class="user-selector">
  <div class="select-group">
    <label for="persona-select">Usuario</label>
    <select
      id="persona-select"
      bind:value={selectedCedula}
      on:change={handlePersonaChange}
    >
      {#each personasList as p}
        <option value={p.cedula}>{p.nombre}</option>
      {/each}
    </select>
  </div>

  {#if perfilesDisponibles.length > 0}
    <div class="select-group">
      <label for="perfil-select">Perfil</label>
      <select
        id="perfil-select"
        bind:value={selectedPerfilId}
        on:change={handlePerfilChange}
      >
        {#each perfilesDisponibles as perfil}
          <option value={String(perfil.id)}>
            {#if perfil.carrera_nombre}
              {perfil.carrera_nombre}
            {:else}
              {perfil.descripcion}
            {/if}
          </option>
        {/each}
      </select>
    </div>
  {/if}

  {#if periodosDisponibles.length > 0}
    <div class="select-group">
      <label for="periodo-select">Periodo Académico</label>
      <select
        id="periodo-select"
        bind:value={selectedPeriodoId}
        on:change={handlePeriodoChange}
      >
        {#each periodosDisponibles as per}
          <option value={String(per.id)}>
            {per.nombre}
            {#if per.activo}{/if}
          </option>
        {/each}
      </select>
    </div>
  {/if}
</div>

<style>
  .user-selector {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    padding: 0;
    background: transparent;
    border-bottom: none;
    color: #1e3a5f;
    box-shadow: none;
    align-items: center;
  }

  .select-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 150px;
  }

  .select-group label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    color: #64748b;
    letter-spacing: 0.5px;
  }

  select {
    width: 100%;
    padding: 6px 10px;
    font-size: 13px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background-color: #f8fafc;
    color: #1e293b;
    outline: none;
    transition: all 0.2s;
    cursor: pointer;
  }

  select:focus {
    border-color: #ff6b35;
    background-color: #fff;
    box-shadow: 0 0 0 2px rgba(255, 107, 53, 0.1);
  }

  select:hover {
    border-color: #cbd5e1;
  }

  option {
    background-color: white;
    color: #333;
    padding: 8px;
  }
</style>
