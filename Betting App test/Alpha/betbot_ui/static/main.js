document.addEventListener('DOMContentLoaded', () => {
    console.log("Sistema BetBot Alpha iniciado...");

    const app = document.getElementById('app');
    
    // Simulación de carga de datos
    app.innerHTML = `
        <div class="loader">
            <p style="color: #00ff88;">> Cargando algoritmos de predicción...</p>
            <p style="color: #666;">Módulo Alpha v1.0 listo para operar.</p>
        </div>
    `;
});