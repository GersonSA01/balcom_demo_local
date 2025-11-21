<script>
  import { Router, Route, Link } from "svelte-routing";
  import Chatbot from "./lib/Chatbot.svelte";
  import KnowledgeBase from "./lib/KnowledgeBase.svelte";

  export let url = "";
</script>

<Router {url}>
  <main>
    <div class="container">
      <div class="header">
        <div class="logo-section">
          <div class="logo">UNEMI</div>
          <div class="subtitle">Balcón de Servicios</div>
        </div>
        <h1>Asistente Virtual</h1>

        <!-- Navegación -->
        <nav class="nav-tabs">
          <Link to="/" class="nav-link">💬 Chatbot</Link>
          <Link to="/knowledge_base" class="nav-link"
            >📚 Base de Conocimiento</Link
          >
        </nav>
      </div>

      <!-- Rutas -->
      <Route path="/knowledge_base" component={KnowledgeBase} />
      <Route path="/" component={Chatbot} />
    </div>
  </main>
</Router>

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
    margin: 0 0 1.5rem 0;
    letter-spacing: -0.5px;
  }

  .nav-tabs {
    display: flex;
    justify-content: center;
    gap: 1rem;
    margin-top: 1.5rem;
  }

  :global(.nav-link) {
    padding: 0.75rem 1.5rem;
    background: #f5f5f5;
    color: #666;
    text-decoration: none;
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.3s ease;
    border: 2px solid transparent;
  }

  :global(.nav-link:hover) {
    background: #e8e8e8;
    color: #1e3a5f;
  }

  :global(.nav-link[aria-current="page"]) {
    background: #ff6b35;
    color: white;
    border-color: #ff6b35;
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

    .nav-tabs {
      flex-direction: column;
      gap: 0.5rem;
    }

    :global(.nav-link) {
      padding: 0.6rem 1rem;
      font-size: 0.9rem;
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
