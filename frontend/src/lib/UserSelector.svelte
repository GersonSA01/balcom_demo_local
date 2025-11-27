<script>
  import { onMount } from 'svelte';
  
  export let dataUnemi = {};
  
  let personasList = [];
  let selectedCedula = '';
  let selectedPerfilId = '';
  let perfilesDisponibles = [];
  
  $: if (dataUnemi && Object.keys(dataUnemi).length > 0) {
    personasList = Object.keys(dataUnemi).map(cedula => ({
      cedula,
      nombre: `${dataUnemi[cedula].persona?.nombres || ''} ${dataUnemi[cedula].persona?.apellido1 || ''} ${dataUnemi[cedula].persona?.apellido2 || ''}`.trim() || cedula
    }));
    
    // Cargar selección guardada cuando dataUnemi esté disponible
    loadSavedSelection();
  }
  
  function loadSavedSelection() {
    try {
      const stored = localStorage.getItem('user_session_data');
      if (stored && dataUnemi && Object.keys(dataUnemi).length > 0) {
        const sessionData = JSON.parse(stored);
        const cedula = Object.keys(sessionData)[0];
        
        if (cedula && dataUnemi[cedula]) {
          selectedCedula = cedula;
          handlePersonaChange(); // Esto carga los perfiles disponibles
          
          // Buscar el perfil seleccionado
          const perfiles = sessionData[cedula].perfiles;
          if (perfiles && perfiles.length > 0) {
            const perfilId = perfiles[0].id;
            // Asegurar que siempre sea string para consistencia
            selectedPerfilId = String(perfilId);
            
            // IMPORTANTE: Disparar el evento para actualizar el chatbot
            // Usar setTimeout para asegurar que el DOM se actualice primero
            setTimeout(() => {
              updateSessionData();
            }, 0);
          }
        }
      }
    } catch (e) {
      console.error('Error cargando selección guardada:', e);
    }
  }
  
  onMount(() => {
    loadSavedSelection();
  });
  
  function handlePersonaChange() {
    if (selectedCedula && dataUnemi[selectedCedula]) {
      perfilesDisponibles = dataUnemi[selectedCedula].perfiles.filter(p => p.status === true);
      selectedPerfilId = '';
    } else {
      perfilesDisponibles = [];
      selectedPerfilId = '';
    }
  }
  
  function handlePerfilChange() {
    updateSessionData();
  }
  
  function updateSessionData() {
    // Verificamos que existan datos
    if (selectedCedula && selectedPerfilId && dataUnemi[selectedCedula]) {
      const personaData = dataUnemi[selectedCedula];
      
      // ---------------------------------------------------------
      // 🔧 CORRECCIÓN: Usamos String() en ambos lados para evitar conflictos de tipo
      // ---------------------------------------------------------
      const perfilSelected = personaData.perfiles.find(p => 
        String(p.id) === String(selectedPerfilId)
      );
      
      if (perfilSelected) {
        const sessionData = {
          [selectedCedula]: {
            persona: personaData.persona, // Incluimos datos personales (nombres, etc)
            perfiles: [perfilSelected]    // Solo el perfil activo seleccionado
          }
        };
        
        // Guardar en localStorage
        const jsonString = JSON.stringify(sessionData);
        localStorage.setItem('user_session_data', jsonString);
        
        
        // Verificar que se guardó correctamente leyéndolo de vuelta
        const verify = localStorage.getItem('user_session_data');
        if (verify) {
          try {
            const parsed = JSON.parse(verify);
          } catch (e) {
            console.error("Error verificando datos guardados:", e);
          }
        }
        
        // Disparamos el evento para que el chat se actualice al instante
        window.dispatchEvent(new CustomEvent('sessionDataUpdated', { detail: sessionData }));
      } else {
        console.warn("Perfil no encontrado en el array. ID buscando:", selectedPerfilId, "(tipo:", typeof selectedPerfilId + ")");
      }
    } else {
      console.warn("UserSelector: No se puede actualizar sesión - faltan datos", {
        hasSelectedCedula: !!selectedCedula,
        hasSelectedPerfilId: !!selectedPerfilId,
        hasDataUnemi: !!dataUnemi[selectedCedula]
      });
    }
  }
</script>

<div class="user-selector">
  <div class="select-group">
    <label for="persona-select">Persona:</label>
    <select 
      id="persona-select" 
      bind:value={selectedCedula} 
      on:change={handlePersonaChange}
    >
      <option value="">Seleccione una persona</option>
      {#each personasList as persona}
        <option value={persona.cedula}>{persona.nombre} ({persona.cedula})</option>
      {/each}
    </select>
  </div>
  
  {#if selectedCedula && perfilesDisponibles.length > 0}
    <div class="select-group">
      <label for="perfil-select">Perfil:</label>
      <select 
        id="perfil-select" 
        bind:value={selectedPerfilId} 
        on:change={handlePerfilChange}
      >
        <option value="">Seleccione un perfil</option>
        {#each perfilesDisponibles as perfil}
          <option value={String(perfil.id)}>
            {perfil.tipo || 'Sin tipo'}
            {#if perfil.es_estudiante}(Estudiante){/if}
            {#if perfil.es_profesor}(Profesor){/if}
            {#if perfil.es_administrativo}(Administrativo){/if}
          </option>
        {/each}
      </select>
    </div>
  {/if}
</div>

<style>
  .user-selector {
    display: flex;
    flex-wrap: wrap; /* Permite que baje de línea en pantallas muy pequeñas */
    gap: 16px;
    padding: 14px 16px;
    background: linear-gradient(to right, #1e3a5f 0%, #2c4a6b 100%);
    border-bottom: 3px solid #ff6b35;
  }
  
  .select-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex: 1;
  }
  
  .select-group label {
    font-size: 13px;
    font-weight: 600;
    color: #ffffff;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  
  .select-group select {
    padding: 10px 12px;
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-radius: 6px;
    font-size: 14px;
    background: #ffffff;
    color: #1e3a5f;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.3s ease;
  }
  
  .select-group select:hover {
    border-color: #ff6b35;
    box-shadow: 0 2px 8px rgba(255, 107, 53, 0.2);
  }
  
  .select-group select:focus {
    outline: none;
    border-color: #ff6b35;
    box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.15);
  }
  
  .select-group select option {
    color: #1e3a5f;
    background: #ffffff;
    padding: 8px;
  }
  
  .select-group select option:disabled {
    color: #999;
  }
</style>
