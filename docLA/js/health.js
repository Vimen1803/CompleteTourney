// --- Configuration ---
const API_URL = '/api/health'; // Keep existing endpoint

// --- Helper Functions ---
function getStatusClass(latency) {
    // Simple logic: > 0 means online for this demo
    if (latency > 0) return 'online';
    return 'offline';
}

function updateWaveChart(data, isOnline) {
    const chartContainer = document.getElementById('wave-chart');
    chartContainer.innerHTML = '';
    
    // Remove 'online' class first
    chartContainer.classList.remove('online');
    if (isOnline) chartContainer.classList.add('online');

    // Take last 15 points for the visual wave
    const entries = data.slice(0, 15).reverse();
    const maxVal = Math.max(...entries.map(e => e.latency), 200);

    entries.forEach(item => {
        const bar = document.createElement('div');
        bar.className = 'wave-bar';
        // Calculate height relative to max, min 10% height
        let hPercent = 10;
        if (item.latency > 0) {
            hPercent = (item.latency / maxVal) * 100;
            if (hPercent < 15) hPercent = 15;
            if (hPercent > 100) hPercent = 100;
        }
        
        bar.style.height = `${hPercent}%`;
        chartContainer.appendChild(bar);
    });
}

async function fetchHealth() {
    try {
        // Fetch data
        const response = await fetch(API_URL);
        const data = await response.json();

        if (data && data.length > 0) {
            const latest = data[0];
            const isOnline = latest.status === 'online' && latest.latency > 0;
            const latency = latest.latency;

            // 1. Update Glow & Pulse Colors
            const heroGlow = document.getElementById('hero-glow');
            const mainPulse = document.getElementById('main-pulse');
            
            if (isOnline) {
                heroGlow.className = 'hero-glow success';
                mainPulse.classList.add('online');
                document.getElementById('status-text').textContent = 'Sistema Operativo';
                document.getElementById('status-text').style.color = '#fff';
            } else {
                heroGlow.className = 'hero-glow danger';
                mainPulse.classList.remove('online');
                document.getElementById('status-text').textContent = 'Error de conexión';
                document.getElementById('status-text').style.color = '#ef4444';
            }

            // 2. Update Latency Text
            const latVal = document.getElementById('latency-value');
            latVal.textContent = isOnline ? latency : "0";

            // 3. Update Wave Chart
            updateWaveChart(data, isOnline);

            // 4. Update History List
            const historyContainer = document.getElementById('history-container');
            historyContainer.innerHTML = '';

            // Show up to 24 entries
            data.slice(0, 24).forEach(item => {
                const itemOnline = item.status === 'online' && item.latency > 0;
                const date = new Date(item.timestamp);
                const day = String(date.getDate()).padStart(2, '0');
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const year = date.getFullYear();
                const time = date.toLocaleTimeString('es-ES', { hour: '2-digit', minute:'2-digit' });
                const timeStr = `${day}/${month}/${year} ${time}`;
                
                const row = document.createElement('div');
                row.className = 'history-item';
                row.innerHTML = `
                    <div class="h-main">
                        <div class="h-dot ${itemOnline ? 'online' : ''}"></div>
                        <span class="h-latency ${itemOnline ? 'online' : ''}">
                            ${itemOnline ? item.latency + ' ms' : 'Offline'}
                        </span>
                    </div>
                    <div class="h-footer">
                        <span class="h-date">${time}</span>
                        <span class="h-time-small">${day}/${month}/${year}</span>
                    </div>
                `;
                historyContainer.appendChild(row);
            });

        } else {
            // No data state
            document.getElementById('status-text').textContent = 'Sin Datos';
        }

    } catch (error) {
        console.error("Fetch error:", error);
        document.getElementById('status-text').textContent = 'Error API';
    }
}

// Init
fetchHealth();
// Poll every 60s
setInterval(fetchHealth, 60000);