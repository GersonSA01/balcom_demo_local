<script>
  import Chatbot from './lib/Chatbot.svelte'
</script>

<main>
  <div class="container">
    <div class="header">
      <div class="logo-section">
        <div class="logo">UNEMI</div>
        <div class="subtitle">Balcón de Servicios</div>
      </div>
      <h1>Asistente Virtual</h1>
    </div>
    <Chatbot />
  </div>
</main>

<style>
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  main {
    min-height: 100vh;
    background: #ffffff;
    padding: 2rem 1rem;
    position: relative;
  }

  .container {
    max-width: 1100px;
    margin: 0 auto;
    position: relative;
  }

  .header {
    text-align: center;
    margin-bottom: 2rem;
    padding: 2rem 1rem;
  }

  .logo-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    margin-bottom: 1rem;
  }

  .logo {
    font-size: 3rem;
    font-weight: 800;
    color: #1e3a5f;
    letter-spacing: -1px;
  }

  .subtitle {
    font-size: 1rem;
    font-weight: 500;
    color: #ff6b35;
    text-transform: uppercase;
    letter-spacing: 2px;
  }

  h1 {
    color: #1e3a5f;
    font-size: 2rem;
    font-weight: 600;
    margin: 0;
    letter-spacing: -0.5px;
  }

  @media (max-width: 768px) {
    main {
      padding: 1rem 0.5rem;
    }

    .header {
      padding: 1.5rem 1rem;
      margin-bottom: 1.5rem;
    }

    .logo {
      font-size: 2.5rem;
    }

    .subtitle {
      font-size: 0.875rem;
      letter-spacing: 1px;
    }

    h1 {
      font-size: 1.5rem;
    }
  }

  @media (max-width: 480px) {
    .header {
      padding: 1rem;
      margin-bottom: 1rem;
    }

    .logo {
      font-size: 2rem;
    }

    h1 {
      font-size: 1.25rem;
    }
  }
</style>
