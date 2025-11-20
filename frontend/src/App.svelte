<script>
  import Chatbot from './lib/Chatbot.svelte'
</script>

<main>
  <div class="container">
    <h1>Chatbot con Ollama</h1>
    <Chatbot />
  </div>
</main>

<style>
  main {
    padding: 2rem;
    min-height: 100vh;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  }

  .container {
    max-width: 900px;
    margin: 0 auto;
  }

  h1 {
    color: white;
    text-align: center;
    margin-bottom: 2rem;
    font-size: 2rem;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  }
</style>
