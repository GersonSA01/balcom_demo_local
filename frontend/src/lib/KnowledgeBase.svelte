<script>
    import { onMount } from "svelte";

    let files = [];
    let isDragging = false;
    let uploading = false;
    let uploadProgress = 0;
    let uploadResults = null;
    let categoria = "general";

    // Estado del explorador de archivos
    let documentTree = {};
    let expandedFolders = {};
    let loadingTree = false;

    const CATEGORIAS = [
        { value: "general", label: "General" },
        { value: "estudiantes", label: "Estudiantes" },
        { value: "docentes", label: "Docentes" },
        { value: "administrativos", label: "Administrativos" },
        { value: "externos", label: "Externos" },
        { value: "aspirantes", label: "Aspirantes" },
        { value: "postulantes", label: "Postulantes" },
        { value: "empleo", label: "Empleo" },
        { value: "admision", label: "Admisión" },
    ];

    // Cargar árbol de documentos al montar
    onMount(() => {
        loadDocumentTree();
    });

    async function loadDocumentTree() {
        loadingTree = true;
        try {
            const response = await fetch(
                "http://localhost:8000/api/chatbot/upload-documents/",
            );
            const data = await response.json();
            documentTree = data.categories || {};

            // Expandir todas las carpetas por defecto
            Object.keys(documentTree).forEach((cat) => {
                expandedFolders[cat] = true;
            });
        } catch (error) {
            console.error("Error cargando árbol de documentos:", error);
        } finally {
            loadingTree = false;
        }
    }

    function toggleFolder(category) {
        expandedFolders[category] = !expandedFolders[category];
    }

    function getFileIcon(type) {
        const icons = {
            pdf: "📄",
            docx: "📝",
            txt: "📃",
            md: "📋",
        };
        return icons[type] || "📎";
    }

    function getCategoryIcon(category) {
        const icons = {
            general: "📁",
            estudiantes: "🎓",
            docentes: "👨‍🏫",
            administrativos: "💼",
            externos: "🌐",
            aspirantes: "🎯",
            postulantes: "📝",
            empleo: "💼",
            admision: "🎫",
        };
        return icons[category] || "📁";
    }

    function handleDragOver(e) {
        e.preventDefault();
        isDragging = true;
    }

    function handleDragLeave(e) {
        e.preventDefault();
        isDragging = false;
    }

    function handleDrop(e) {
        e.preventDefault();
        isDragging = false;

        const droppedFiles = Array.from(e.dataTransfer.files);
        addFiles(droppedFiles);
    }

    function handleFileSelect(e) {
        const selectedFiles = Array.from(e.target.files);
        addFiles(selectedFiles);
    }

    function addFiles(newFiles) {
        // Filtrar solo formatos soportados
        const supportedFormats = [".pdf", ".docx", ".txt", ".md"];
        const validFiles = newFiles.filter((file) => {
            const ext = "." + file.name.split(".").pop().toLowerCase();
            return supportedFormats.includes(ext);
        });

        files = [...files, ...validFiles];
    }

    function removeFile(index) {
        files = files.filter((_, i) => i !== index);
    }

    async function uploadDocuments() {
        if (files.length === 0) return;

        uploading = true;
        uploadProgress = 0;
        uploadResults = null;

        const formData = new FormData();
        files.forEach((file) => {
            formData.append("files", file);
        });
        formData.append("categoria", categoria);

        try {
            const response = await fetch(
                "http://localhost:8000/api/chatbot/upload-documents/",
                {
                    method: "POST",
                    body: formData,
                },
            );

            const data = await response.json();
            uploadResults = data;

            if (response.ok) {
                // Limpiar archivos después de éxito
                files = [];
                // Recargar árbol de documentos
                await loadDocumentTree();
            }
        } catch (error) {
            uploadResults = {
                error: "Error de conexión: " + error.message,
            };
        } finally {
            uploading = false;
            uploadProgress = 100;
        }
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return (
            Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i]
        );
    }
</script>

<div class="knowledge-base">
    <div class="header">
        <h1>📚 Base de Conocimiento</h1>
        <p class="subtitle">Gestión de documentos para el sistema RAG</p>
    </div>

    <!-- Explorador de Categorías -->
    <div class="file-explorer card">
        <div class="explorer-header">
            <h2>🗂️ Categorías</h2>
            <button
                class="refresh-btn"
                on:click={loadDocumentTree}
                disabled={loadingTree}
            >
                {#if loadingTree}
                    ⏳
                {:else}
                    🔄
                {/if}
            </button>
        </div>

        {#if loadingTree}
            <div class="loading">Cargando...</div>
        {:else if Object.keys(documentTree).length === 0}
            <div class="empty-state">
                <p>📂 No hay documentos cargados aún</p>
                <p class="hint">Sube algunos documentos abajo para empezar</p>
            </div>
        {:else}
            <div class="folder-tree">
                {#each Object.entries(documentTree) as [category, categoryFiles]}
                    <div class="folder-item">
                        <div
                            class="folder-header"
                            on:click={() => toggleFolder(category)}
                        >
                            <span class="folder-icon">
                                {getCategoryIcon(category)}
                            </span>
                            <span class="folder-name">{category}</span>
                            <span class="file-count"
                                >{categoryFiles.length} archivo{categoryFiles.length !==
                                1
                                    ? "s"
                                    : ""}</span
                            >
                            <span class="toggle-icon"
                                >{expandedFolders[category] ? "▼" : "▶"}</span
                            >
                        </div>

                        {#if expandedFolders[category]}
                            <div class="folder-content">
                                {#each categoryFiles as file}
                                    <div class="file-row">
                                        <span class="file-icon"
                                            >{getFileIcon(file.type)}</span
                                        >
                                        <span class="file-name"
                                            >{file.name}</span
                                        >
                                        <span class="file-size"
                                            >{file.size_mb} MB</span
                                        >
                                        <span class="file-type"
                                            >{file.type.toUpperCase()}</span
                                        >
                                    </div>
                                {/each}
                            </div>
                        {/if}
                    </div>
                {/each}
            </div>
        {/if}
    </div>

    <div class="upload-section">
        <div class="card">
            <h2>📤 Subir Documentos</h2>

            <!-- Selector de Categoría -->
            <div class="form-group">
                <label for="categoria">Categoría:</label>
                <select id="categoria" bind:value={categoria}>
                    {#each CATEGORIAS as cat}
                        <option value={cat.value}>{cat.label}</option>
                    {/each}
                </select>
            </div>

            <!-- Drag & Drop Area -->
            <div
                class="drag-drop-area"
                class:dragging={isDragging}
                on:dragover={handleDragOver}
                on:dragleave={handleDragLeave}
                on:drop={handleDrop}
                on:click={() => document.getElementById("fileInput").click()}
            >
                <div class="drag-drop-content">
                    <i class="icon">☁️</i>
                    <h3>Arrastra archivos aquí o haz clic para seleccionar</h3>
                    <p class="formats">
                        Formatos soportados: PDF, DOCX, TXT, MD
                    </p>
                    <p class="max-size">Tamaño máximo: 50 MB por archivo</p>
                </div>
                <input
                    type="file"
                    id="fileInput"
                    multiple
                    accept=".pdf,.docx,.txt,.md"
                    on:change={handleFileSelect}
                    style="display: none;"
                />
            </div>

            <!-- Lista de Archivos Seleccionados -->
            {#if files.length > 0}
                <div class="selected-files">
                    <h3>📄 Archivos Seleccionados ({files.length})</h3>
                    <ul class="file-list">
                        {#each files as file, index}
                            <li class="file-item">
                                <div class="file-info">
                                    <span class="file-name">{file.name}</span>
                                    <span class="file-size"
                                        >{formatFileSize(file.size)}</span
                                    >
                                </div>
                                <button
                                    class="remove-btn"
                                    on:click={() => removeFile(index)}
                                    disabled={uploading}
                                >
                                    ❌
                                </button>
                            </li>
                        {/each}
                    </ul>

                    <button
                        class="upload-btn"
                        on:click={uploadDocuments}
                        disabled={uploading || files.length === 0}
                    >
                        {#if uploading}
                            ⏳ Procesando...
                        {:else}
                            🚀 Procesar Documentos
                        {/if}
                    </button>
                </div>
            {/if}

            <!-- Barra de Progreso -->
            {#if uploading}
                <div class="progress-bar">
                    <div
                        class="progress-fill"
                        style="width: {uploadProgress}%"
                    ></div>
                </div>
            {/if}

            <!-- Resultados de la Carga -->
            {#if uploadResults}
                <div class="results">
                    {#if uploadResults.error}
                        <div class="alert alert-error">
                            <strong>❌ Error:</strong>
                            {uploadResults.error}
                        </div>
                    {:else}
                        <div class="alert alert-success">
                            <strong>✅ {uploadResults.message}</strong>
                        </div>

                        {#if uploadResults.details && uploadResults.details.length > 0}
                            <div class="file-details">
                                <h3>📊 Detalles de Procesamiento</h3>
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Archivo</th>
                                            <th>Tipo</th>
                                            <th>Tamaño</th>
                                            <th>Chunks</th>
                                            <th>Categoría</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {#each uploadResults.details as detail}
                                            <tr>
                                                <td>{detail.filename}</td>
                                                <td
                                                    >{detail.file_type.toUpperCase()}</td
                                                >
                                                <td>{detail.file_size_mb} MB</td
                                                >
                                                <td
                                                    ><strong
                                                        >{detail.chunks_created}</strong
                                                    ></td
                                                >
                                                <td
                                                    ><span class="badge"
                                                        >{detail.categoria}</span
                                                    ></td
                                                >
                                            </tr>
                                        {/each}
                                    </tbody>
                                </table>

                                <div class="summary">
                                    <div class="summary-card">
                                        <div class="summary-value">
                                            {uploadResults.total_chunks_added}
                                        </div>
                                        <div class="summary-label">
                                            Total de Chunks
                                        </div>
                                    </div>
                                    <div class="summary-card">
                                        <div class="summary-value">
                                            {uploadResults.files_processed
                                                .length}
                                        </div>
                                        <div class="summary-label">
                                            Archivos Procesados
                                        </div>
                                    </div>
                                </div>
                            </div>
                        {/if}

                        {#if uploadResults.errors && uploadResults.errors.length > 0}
                            <div class="errors-section">
                                <h3>⚠️ Errores</h3>
                                <ul>
                                    {#each uploadResults.errors as error}
                                        <li class="error-item">
                                            <strong>{error.file}:</strong>
                                            {error.error}
                                        </li>
                                    {/each}
                                </ul>
                            </div>
                        {/if}
                    {/if}
                </div>
            {/if}
        </div>
    </div>
</div>

<style>
    .knowledge-base {
        max-width: 1200px;
        margin: 0 auto;
        padding: 2rem;
    }

    .header {
        text-align: center;
        margin-bottom: 3rem;
    }

    .header h1 {
        font-size: 2.5rem;
        color: #1e3a5f;
        margin-bottom: 0.5rem;
    }

    .subtitle {
        color: #666;
        font-size: 1.1rem;
    }

    /* Explorador de Archivos */
    .file-explorer {
        margin-bottom: 2rem;
    }

    .explorer-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.5rem;
    }

    .refresh-btn {
        background: #f5f5f5;
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        cursor: pointer;
        font-size: 1.2rem;
        transition: all 0.3s;
    }

    .refresh-btn:hover:not(:disabled) {
        background: #e0e0e0;
    }

    .refresh-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .loading {
        text-align: center;
        padding: 2rem;
        color: #666;
    }

    .empty-state {
        text-align: center;
        padding: 3rem 2rem;
        background: #f9f9f9;
        border-radius: 8px;
    }

    .empty-state p {
        color: #666;
        margin: 0.5rem 0;
    }

    .hint {
        font-size: 0.9rem;
        font-style: italic;
    }

    .folder-tree {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        overflow: hidden;
    }

    .folder-item {
        border-bottom: 1px solid #e0e0e0;
    }

    .folder-item:last-child {
        border-bottom: none;
    }

    .folder-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 1rem;
        background: #f8f8f8;
        cursor: pointer;
        transition: background 0.2s;
    }

    .folder-header:hover {
        background: #f0f0f0;
    }

    .folder-icon {
        font-size: 1.2rem;
    }

    .toggle-icon {
        font-size: 0.8rem;
        color: #666;
        margin-left: 0.5rem;
    }

    .folder-name {
        flex: 1;
        font-weight: 600;
        color: #333;
        text-transform: capitalize;
    }

    .file-count {
        font-size: 0.85rem;
        color: #666;
        background: white;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
    }

    .folder-content {
        background: white;
    }

    .file-row {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 0.75rem 1rem 0.75rem 2.5rem;
        border-top: 1px solid #f0f0f0;
        transition: background 0.2s;
    }

    .file-row:hover {
        background: #f9f9f9;
    }

    .file-icon {
        font-size: 1.1rem;
    }

    .file-row .file-name {
        flex: 1;
        color: #555;
        font-size: 0.95rem;
    }

    .file-row .file-size {
        color: #888;
        font-size: 0.85rem;
        min-width: 60px;
    }

    .file-row .file-type {
        background: #1e3a5f;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        min-width: 50px;
        text-align: center;
    }

    .card {
        background: white;
        border-radius: 12px;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
        padding: 2rem;
    }

    .card h2 {
        color: #1e3a5f;
        margin-bottom: 1.5rem;
    }

    .form-group {
        margin-bottom: 1.5rem;
    }

    .form-group label {
        display: block;
        font-weight: 600;
        color: #333;
        margin-bottom: 0.5rem;
    }

    .form-group select {
        width: 100%;
        max-width: 300px;
        padding: 0.75rem;
        border: 2px solid #e0e0e0;
        border-radius: 8px;
        font-size: 1rem;
        background: white;
        cursor: pointer;
        transition: border-color 0.3s;
    }

    .form-group select:focus {
        outline: none;
        border-color: #ff6b35;
    }

    .drag-drop-area {
        border: 3px dashed #ddd;
        border-radius: 12px;
        padding: 3rem 2rem;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
        background: #f9f9f9;
    }

    .drag-drop-area:hover,
    .drag-drop-area.dragging {
        border-color: #ff6b35;
        background: #fff5f0;
    }

    .drag-drop-content .icon {
        font-size: 4rem;
        display: block;
        margin-bottom: 1rem;
    }

    .drag-drop-content h3 {
        color: #333;
        margin-bottom: 1rem;
    }

    .formats,
    .max-size {
        color: #666;
        font-size: 0.9rem;
        margin: 0.5rem 0;
    }

    .selected-files {
        margin-top: 2rem;
    }

    .selected-files h3 {
        color: #1e3a5f;
        margin-bottom: 1rem;
    }

    .file-list {
        list-style: none;
        padding: 0;
        margin-bottom: 1.5rem;
    }

    .file-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem;
        background: #f5f5f5;
        border-radius: 8px;
        margin-bottom: 0.5rem;
    }

    .file-info {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .file-info .file-name {
        font-weight: 600;
        color: #333;
    }

    .file-info .file-size {
        font-size: 0.85rem;
        color: #666;
    }

    .remove-btn {
        background: none;
        border: none;
        cursor: pointer;
        font-size: 1.2rem;
        opacity: 0.6;
        transition: opacity 0.2s;
    }

    .remove-btn:hover:not(:disabled) {
        opacity: 1;
    }

    .remove-btn:disabled {
        cursor: not-allowed;
        opacity: 0.3;
    }

    .upload-btn {
        width: 100%;
        padding: 1rem 2rem;
        background: linear-gradient(135deg, #ff6b35 0%, #ff8c5a 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 1.1rem;
        font-weight: 600;
        cursor: pointer;
        transition:
            transform 0.2s,
            box-shadow 0.2s;
    }

    .upload-btn:hover:not(:disabled) {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(255, 107, 53, 0.4);
    }

    .upload-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .progress-bar {
        width: 100%;
        height: 8px;
        background: #e0e0e0;
        border-radius: 4px;
        overflow: hidden;
        margin-top: 1rem;
    }

    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #ff6b35 0%, #ff8c5a 100%);
        transition: width 0.3s ease;
    }

    .results {
        margin-top: 2rem;
    }

    .alert {
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }

    .alert-success {
        background: #d4edda;
        color: #155724;
        border-left: 4px solid #28a745;
    }

    .alert-error {
        background: #f8d7da;
        color: #721c24;
        border-left: 4px solid #dc3545;
    }

    .file-details {
        margin-top: 1.5rem;
    }

    .file-details h3 {
        color: #1e3a5f;
        margin-bottom: 1rem;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 1.5rem;
    }

    table thead th {
        background: #f5f5f5;
        padding: 0.75rem;
        text-align: left;
        font-weight: 600;
        color: #333;
        border-bottom: 2px solid #ddd;
    }

    table tbody td {
        padding: 0.75rem;
        border-bottom: 1px solid #e0e0e0;
    }

    table tbody tr:hover {
        background: #f9f9f9;
    }

    .badge {
        padding: 0.25rem 0.75rem;
        background: #ff6b35;
        color: white;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .summary {
        display: flex;
        gap: 1rem;
        justify-content: center;
        margin-top: 1.5rem;
    }

    .summary-card {
        background: linear-gradient(135deg, #ff6b35 0%, #ff8c5a 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        min-width: 150px;
    }

    .summary-value {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }

    .summary-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }

    .errors-section {
        margin-top: 1.5rem;
        padding: 1rem;
        background: #fff3cd;
        border-radius: 8px;
        border-left: 4px solid #ffc107;
    }

    .errors-section h3 {
        color: #856404;
        margin-bottom: 1rem;
    }

    .errors-section ul {
        list-style: none;
        padding: 0;
    }

    .error-item {
        padding: 0.5rem 0;
        color: #856404;
    }
</style>
