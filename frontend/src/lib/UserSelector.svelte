<script>
  import { onMount } from 'svelte';
  
  // Ahora esperamos que dataUnemi sea un Array de objetos, no un diccionario gigante.
  export let dataUnemi = []; 
  
  let personasList = [];
  let selectedCedula = '';
  let selectedPerfilId = '';
  let perfilesDisponibles = [];
  
  // Reactividad: Si llega dataUnemi (Array), preparamos la lista para el <select>
  $: if (Array.isArray(dataUnemi) && dataUnemi.length > 0) {
    personasList = dataUnemi.map(u => ({
      cedula: u.cedula,
      // Asumiendo que el backend envía una estructura similar con 'persona' dentro
      nombre: `${u.persona?.nombres || ''} ${u.persona?.apellido1 || ''} ${u.persona?.apellido2 || ''}`.trim() || u.cedula
    }));
    
    loadSavedSelection();
  }
  
  function loadSavedSelection() {
    try {
      const stored = localStorage.getItem('user_session_data');
      if (stored && Array.isArray(dataUnemi) && dataUnemi.length > 0) {
        const sessionData = JSON.parse(stored);
        const cedula = Object.keys(sessionData)[0];
        
        // BUSCAR en el array (antes era directo dataUnemi[cedula])
        const usuarioEncontrado = dataUnemi.find(u => u.cedula === cedula);

        if (usuarioEncontrado) {
          selectedCedula = cedula;
          updatePerfiles(usuarioEncontrado); // Función auxiliar para no repetir código
          
          const perfilesGuardados = sessionData[cedula].perfiles;
          if (perfilesGuardados && perfilesGuardados.length > 0) {
            // Aseguramos que sea string para que coincida con el value del select
            selectedPerfilId = String(perfilesGuardados[0].id);
          }
        }
      }
    } catch (e) {
      console.error("Error loading selection:", e);
    }
  }
  
  function updatePerfiles(usuarioData) {
    if (usuarioData && usuarioData.perfiles) {
      perfilesDisponibles = usuarioData.perfiles;
      // Seleccionar el primero por defecto si no hay uno seleccionado
      if (perfilesDisponibles.length > 0 && !selectedPerfilId) {
        selectedPerfilId = String(perfilesDisponibles[0].id);
      }
    } else {
      perfilesDisponibles = [];
    }
  }

  function handlePersonaChange() {
    if (!selectedCedula) {
      perfilesDisponibles = [];
      selectedPerfilId = '';
      return;
    }
    
    // BUSCAR el usuario seleccionado en el array
    const usuarioData = dataUnemi.find(u => u.cedula === selectedCedula);
    
    updatePerfiles(usuarioData);
    
    // Al cambiar de persona, seleccionar automáticamente el primer perfil
    if (perfilesDisponibles.length > 0) {
      selectedPerfilId = String(perfilesDisponibles[0].id);
    } else {
      selectedPerfilId = '';
    }
    
    dispatchSelection();
  }

  function handlePerfilChange() {
    dispatchSelection();
  }

  function dispatchSelection() {
    if (!selectedCedula || !selectedPerfilId) return;

    // Buscar el objeto perfil completo basado en el ID seleccionado
    const perfilObj = perfilesDisponibles.find(p => String(p.id) === String(selectedPerfilId));
    
    if (perfilObj) {
      // Recrear la estructura de sesión que espera el Chatbot
      const sessionPayload = {
        [selectedCedula]: {
          perfiles: [perfilObj] // Enviamos el perfil seleccionado como una lista de 1
        }
      };
      
      // Guardar en localStorage
      localStorage.setItem('user_session_data', JSON.stringify(sessionPayload));
      
      // Emitir evento global para que Chatbot.svelte se entere
      const event = new CustomEvent('sessionDataUpdated', { detail: sessionPayload });
      window.dispatchEvent(event);
    }
  }
</script>

<div class="user-selector">
  <div class="select-group">
    <label for="persona-select">Usuario de Prueba</label>
    <select id="persona-select" bind:value={selectedCedula} on:change={handlePersonaChange}>
      <option value="">-- Seleccionar Usuario --</option>
      {#each personasList as p}
        <option value={p.cedula}>{p.nombre} ({p.cedula})</option>
      {/each}
    </select>
  </div>
  
  {#if perfilesDisponibles.length > 0}
    <div class="select-group">
      <label for="perfil-select">Perfil Activo</label>
      <select id="perfil-select" bind:value={selectedPerfilId} on:change={handlePerfilChange}>
        {#each perfilesDisponibles as perfil}
          <option value={String(perfil.id)}>
            ID: {perfil.id} - 
            {#if perfil.es_estudiante}Estudiante {/if}
            {#if perfil.es_profesor}Profesor {/if}
            {#if perfil.es_administrativo}Admin {/if}
            {#if !perfil.es_estudiante && !perfil.es_profesor && !perfil.es_administrativo}Otro{/if}
          </option>
        {/each}
      </select>
    </div>
  {/if}
</div>

<style>
  /* Tus estilos originales se mantienen igual */
  .user-selector {
    display: flex;
    flex-wrap: wrap;
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
    background: rgba(255, 255, 255, 0.9);
    color: #334155;
    outline: none;
    transition: all 0.2s;
  }

  .select-group select:focus {
    border-color: #ff6b35;
    background: #ffffff;
    box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.2);
  }
</style>