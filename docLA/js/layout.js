// Shared Layout Logic (Sidebar, User Profile)

document.addEventListener('DOMContentLoaded', () => {
    initLayout();
});

async function initLayout() {
    injectGlobalModals();
    setupSidebar();
    await fetchUserData();
}

function setupSidebar() {
    const toggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    if(toggle && sidebar) {
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
}

async function fetchUserData() {
    try {
        const res = await fetch('/api/user');
        
        // Handle User Not Logged In
        if (res.status === 401) {
            // Updated: Call showLoginUI globally regardless of path
            // to ensure sidebar items are hidden correctly on all pages.
            showLoginUI();
            return;
        }
        
        if(!res.ok) return;

        const user = await res.json();
        updateUserUI(user);

    } catch(e) { 
        console.error("User fetch error", e); 
    }
}

function updateUserUI(user) {
    const nameEl = document.getElementById('user-name');
    const idEl = document.getElementById('user-id');
    const avatarEl = document.getElementById('user-avatar');

    if(nameEl) nameEl.textContent = user.username;
    if(idEl) idEl.textContent = `ID: ${user.id}`;
    if(avatarEl && user.avatar) {
        avatarEl.innerHTML = `<img src="https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png" style="width:100%; height:100%;">`;
    }
}

function showLoginUI() {
    // 1. Update Top Bar
    const nameEl = document.getElementById('user-name');
    const idEl = document.getElementById('user-id');
    const avatarEl = document.getElementById('user-avatar');
    
    if(nameEl) nameEl.textContent = "Invitado";
    if(idEl) idEl.textContent = "No logueado";
    if(avatarEl) avatarEl.innerHTML = '<i class="fas fa-user-circle" style="font-size: 32px; color: var(--text-muted);"></i>';

    // 2. Hide Sidebar Elements (Bug, Suggestion, Logout, My Servers)
    const sidebar = document.getElementById('sidebar');
    if(sidebar) {
        const links = sidebar.querySelectorAll('.nav-links .category-item');
        links.forEach(link => {
            const href = link.getAttribute('href') || "";
            const onclick = link.getAttribute('onclick') || "";
            const text = link.textContent.trim().toLowerCase();

            // Logic to hide specific items
            // - Logout (href has logout)
            // - Bug (onclick has BugModal or text contains bug)
            // - Suggestion (onclick has SuggestionModal or text contains sugerencia)
            // - My Servers (href has dashboard OR onclick has showServerList)
            
            // Allow "Home" (/) and "Documentación" (/docs) to stay visible
            
            if (
                href.includes('/logout') || 
                onclick.includes('BugModal') || 
                onclick.includes('SuggestionModal') ||
                text.includes('reportar bug') ||
                text.includes('sugerencia') ||
                text.includes('cerrar sesión') // Fallback text matching
            ) {
                link.style.display = 'none';
            }
        });
        
        // Hide only "Soporte" header since its items are hidden
        const headers = sidebar.querySelectorAll('.nav-header');
        headers.forEach(h => {
            const t = h.textContent.trim().toLowerCase();
            if(t === 'soporte') h.style.display = 'none';
        });
    }

    // 3. Dashboard Warning Overlay
    // Only invoke this if we are literally on /dashboard, NOT /server or /tournament
    if(window.location.pathname === '/dashboard') {
        // Need to ensure we replace the RIGHT content. 
        // dashboard.html has <div class="content-wrapper"> ... </div>
        // We should target that specific container if possible, or #content if it exists
        // In dashboard.html: <main class="main-content"> ... <div class="content-wrapper">
        
        const contentWrapper = document.querySelector('.content-wrapper');
        if(contentWrapper) {
            contentWrapper.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center; padding-top: 60px;">
                    <div style="background: var(--card-bg); padding: 40px; border-radius: 12px; border: 1px solid var(--border); max-width: 500px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
                        <i class="fab fa-discord" style="font-size: 4rem; color: #5865f2; margin-bottom: 24px;"></i>
                        <h1 style="color: white; margin-bottom: 16px;">Iniciar Sesión Requerido</h1>
                        <p style="color: var(--text-muted); margin-bottom: 32px; line-height: 1.6;">
                            Necesitas iniciar sesión con tu cuenta de Discord para ver tus servidores y gestionar tus torneos.
                        </p>
                        <a href="/login?redirect=/dashboard" class="btn-modern primary" style="font-size: 1.1rem; padding: 12px 32px; text-decoration: none;">
                            <i class="fas fa-sign-in-alt"></i> Iniciar Sesión con Discord
                        </a>
                    </div>
                </div>
            `;
        }
    }
}

// --- Global Modals (Bug & Suggestion) ---

function injectGlobalModals() {
    if(document.getElementById('modal-bug')) return; // Already exists

    const modalHTML = `
      <!-- Bug Report Modal -->
      <div id="modal-bug" class="modal-overlay">
        <div class="modal-content">
            <button class="modal-close" onclick="closeBugModal()">&times;</button>
            <h2 class="modal-title" style="color: #faa61a;"><i class="fas fa-bug"></i> Reportar Bug</h2>
            <p style="color:var(--text-muted); margin-bottom:15px; font-size:0.9em;">Por favor describe el error con detalle. Si es posible, indica pasos para reproducirlo.</p>
            <form onsubmit="submitBug(event)">
                <div class="form-group">
                    <label class="form-label">Descripción del Error</label>
                    <textarea id="bug-desc" class="form-input" rows="5" placeholder="Ej: Al intentar crear un torneo con fecha pasada..." required></textarea>
                </div>
                <button type="submit" class="action-btn primary" style="width:100%; justify-content:center; background-color: #faa61a;">Enviar Reporte</button>
            </form>
        </div>
      </div>

      <!-- Suggestion Modal -->
      <div id="modal-suggestion" class="modal-overlay">
        <div class="modal-content">
            <button class="modal-close" onclick="closeSuggestionModal()">&times;</button>
            <h2 class="modal-title" style="color: #3ba55c;"><i class="fas fa-lightbulb"></i> Hacer Sugerencia</h2>
             <p style="color:var(--text-muted); margin-bottom:15px; font-size:0.9em;">¡Tus ideas nos ayudan a mejorar! Cuéntanos qué funcionalidad te gustaría ver.</p>
            <form onsubmit="submitSuggestion(event)">
                <div class="form-group">
                    <label class="form-label">Tu Sugerencia</label>
                    <textarea id="suggestion-desc" class="form-input" rows="5" placeholder="Ej: Me gustaría que los torneos..." required></textarea>
                </div>
                <button type="submit" class="action-btn primary" style="width:100%; justify-content:center; background-color: #3ba55c;">Enviar Sugerencia</button>
            </form>
        </div>
      </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
}

// Global Functions attached to window
window.openBugModal = function() {
    document.getElementById('modal-bug').classList.add('active');
}
window.closeBugModal = function() {
    document.getElementById('modal-bug').classList.remove('active');
    const el = document.getElementById('bug-desc');
    if(el) el.value = "";
}

window.submitBug = async function(e) {
    e.preventDefault();
    const desc = document.getElementById('bug-desc').value;
    if(!desc) return;
    
    let sId = null;
    let sName = null;
    
    // Try to grab context if available
    if(window.currentGuildId) sId = window.currentGuildId; // Defined in dashboard.js or others
    
    try {
        const res = await fetch('/api/report/bug', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                description: desc,
                server_id: sId,
                server_name: sName
            })
        });
        if(res.ok) {
            alert("¡Reporte enviado! Gracias por ayudarnos.");
            window.closeBugModal();
        } else {
            alert("Error al enviar reporte.");
        }
    } catch(e) { alert("Error de conexión"); }
}

window.openSuggestionModal = function() {
    document.getElementById('modal-suggestion').classList.add('active');
}
window.closeSuggestionModal = function() {
    document.getElementById('modal-suggestion').classList.remove('active');
    const el = document.getElementById('suggestion-desc');
    if(el) el.value = "";
}

window.submitSuggestion = async function(e) {
    e.preventDefault();
    const desc = document.getElementById('suggestion-desc').value;
    if(!desc) return;
    
    let sId = null;
    let sName = null;
    if(window.currentGuildId) sId = window.currentGuildId;

    try {
        const res = await fetch('/api/report/suggestion', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                description: desc,
                server_id: sId,
                server_name: sName
            })
        });
        if(res.ok) {
            alert("¡Sugerencia enviada! Gracias por tu aporte.");
            window.closeSuggestionModal();
        } else {
            alert("Error al enviar sugerencia.");
        }
    } catch(e) { alert("Error de conexión"); }
}
