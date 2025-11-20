<script>
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
  }
  
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
    if (selectedCedula && selectedPerfilId && dataUnemi[selectedCedula]) {
      const personaData = dataUnemi[selectedCedula];
      const perfilSelected = personaData.perfiles.find(p => p.id.toString() === selectedPerfilId);
      
      if (perfilSelected) {
        const sessionData = {
          [selectedCedula]: {
            perfiles: [perfilSelected]
          }
        };
        localStorage.setItem('user_session_data', JSON.stringify(sessionData));
        window.dispatchEvent(new CustomEvent('sessionDataUpdated', { detail: sessionData }));
      }
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
          <option value={perfil.id}>
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
