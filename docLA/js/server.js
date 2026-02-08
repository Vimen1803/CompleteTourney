let currentGuildId = null;
let guildCategories = [];
let guildRoles = [];
let currentServerDataCache = null;
let isLoggedIn = false;
let currentUser = null;

async function init() {
const params = new URLSearchParams(window.location.search);
currentGuildId = params.get("id");

if (!currentGuildId) {
    document.getElementById("content").innerHTML =
    '<h1 style="text-align:center; margin-top:50px;">Error: No se especificó un servidor</h1>';
    return;
}

// Check if user is logged in
    // Auth handled by layout.js
    // Check login state for local banner logic via API response or global check
    try {
        const userRes = await fetch("/api/user");
        if (userRes.ok) {
            currentUser = await userRes.json();
            isLoggedIn = true;
        }
    } catch (e) {}

await loadServerDetail();

// Auto-refresh every 5 seconds
setInterval(async () => {
    // Only refresh if not in settings tab to avoid overwriting form inputs
    if (!document.getElementById('tab-settings') || !document.getElementById('tab-settings').classList.contains('active')) {
        await loadServerDetail();
    }
}, 5000);
}

async function loadServerDetail() {
try {
    const res = await fetch(`/api/guild/${currentGuildId}/public`);
    if (!res.ok) throw new Error("Guild not found");
    const data = await res.json();
    
    // Check if data has changed to avoid unnecessary re-renders
    if (currentServerDataCache && JSON.stringify(data) === JSON.stringify(currentServerDataCache)) {
        return;
    }
    currentServerDataCache = data;

    const guild = data.guild;
    const config = data.config || {};
    const canManage = data.can_manage || false;
    const roleLabel = data.role_label || "Miembro";

    guildChannels = data.channels || [];
    guildCategories = data.categories || [];
    guildRoles = data.roles || [];

    let loginBanner = "";
    if (!isLoggedIn) {
    loginBanner = `
                <div class="login-banner">
                    <p><i class="fas fa-info-circle"></i> Inicia sesión con Discord para ver más detalles y gestionar el servidor</p>
                    <a href="/login?redirect=/server?id=${currentGuildId}" class="login-btn">
                        <i class="fab fa-discord"></i> Iniciar Sesión
                    </a>
                </div>
            `;
    }

    // Build header
    let headerHtml = `
            <div class="dashboard-header">
                <div style="display:flex; align-items:center; gap:15px;">
                    <a href="/dashboard" class="back-btn" style="margin-bottom: 0; text-decoration: none;"><i class="fas fa-arrow-left"></i> Volver al Dashboard</a>
                    <img src="${guild.icon || "https://cdn.discordapp.com/embed/avatars/0.png"}" style="width:48px; height:48px; border-radius:50%;">
                    <h1>${guild.name}</h1>
                    ${isLoggedIn ? `<span class="badge ${roleLabel === "Admin" ? "admin" : roleLabel === "Organizador" ? "mod" : "member"}">${roleLabel}</span>` : ""}
                </div>
            </div>
        `;

    // Build tabs
    const activeTab = sessionStorage.getItem('server_active_tab') || 'overview';
    
    let tabsHtml = `
            <div class="tabs">
                <button class="tab-btn ${activeTab === 'overview' ? 'active' : ''}" onclick="switchTab('overview')">Resumen</button>
                <button class="tab-btn ${activeTab === 'tournaments' ? 'active' : ''}" onclick="switchTab('tournaments')">Torneos</button>
                ${canManage ? `<button class="tab-btn ${activeTab === 'settings' ? 'active' : ''}" onclick="switchTab('settings')">Configuración</button>` : ""}
            </div>
        `;

    // Overview Tab Content
    let overviewHTML = buildOverviewContent(data, canManage);

    // Tournaments Tab Content
    let tournamentsHTML = buildTournamentsContent(data, canManage);

    // Settings Tab Content (only if can manage)
    let settingsHTML = "";
    if (canManage) {
    settingsHTML = buildSettingsContent(data, roleLabel);
    }

    document.getElementById("content").innerHTML = `
            ${loginBanner}
            ${headerHtml}
            ${tabsHtml}
            <div id="tab-overview" class="tab-content ${activeTab === 'overview' ? 'active' : ''}">${overviewHTML}</div>
            <div id="tab-tournaments" class="tab-content ${activeTab === 'tournaments' ? 'active' : ''}">${tournamentsHTML}</div>
            ${canManage ? `<div id="tab-settings" class="tab-content ${activeTab === 'settings' ? 'active' : ''}">${settingsHTML}</div>` : ""}
        `;

    // Fill selects if logged in and can manage
    if (canManage) {
    fillSelect("cfg-category", guildCategories, config.category_id);
    fillSelect("cfg-bracket", guildChannels, config.bracket_channel_id);
    fillSelect("cfg-lobby", guildChannels, config.lobby_channel_id);
    fillSelect(
        "cfg-bot-admin",
        guildChannels,
        config.bot_admin_channel_id,
    );
    fillSelect(
        "cfg-logs",
        guildChannels,
        config.tourney_log_channel_id,
    );

    document.getElementById("cfg-prefix").value = config.prefix || ",";
    document.getElementById("cfg-logs-enabled").checked =
        !!config.tourney_logs_enabled;

    // Display admin roles with names
    displayAdminRoles(config.admin_roles || [], roleLabel === "Admin");
    }
} catch (e) {
    console.error(e);
    document.getElementById("content").innerHTML =
    '<h1 style="text-align:center; margin-top:50px;">Error: No se pudo cargar el servidor</h1><p style="text-align:center;">El bot puede no estar en este servidor.</p>';
}
}

function buildOverviewContent(data, canManage) {
let html = `
        <div class="dashboard-card" style="margin-bottom: 24px;">
            <h2>Estadísticas Rápidas</h2>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-top:15px;">
                <div style="background:var(--bg-tertiary); padding:15px; border-radius:4px;">
                    <div style="font-size:0.9em; color:var(--text-muted)">Miembros</div>
                    <div style="font-size:1.5em; font-weight:bold;">${data.guild.member_count || "-"}</div>
                </div>
                <div style="background:var(--bg-tertiary); padding:15px; border-radius:4px;">
                    <div style="font-size:0.9em; color:var(--text-muted)">Total Torneos</div>
                    <div style="font-size:1.5em; font-weight:bold;">${(data.history || []).length}</div>
                </div>
            </div>
        </div>
    `;

let heroTourney = data.active_tournament;
let isHistory = false;

if (!heroTourney && data.history && data.history.length > 0) {
    heroTourney = data.history[0];
    isHistory = true;
}

if (heroTourney) {
    html += buildTourneyHero(heroTourney, isHistory, canManage, data.guild.icon);
} else if (canManage) {
    html += `
            <div class="dashboard-card" style="text-align:center; padding:60px 20px; border-style:dashed; margin-top:20px;">
                <i class="fas fa-trophy" style="font-size:4rem; color:var(--text-muted); margin-bottom:24px; opacity:0.5;"></i>
                <h2 style="margin-bottom:12px;">No hay torneos activos</h2>
                <p style="margin-bottom:32px; color:var(--text-muted);">¡Crea uno ahora para empezar la competición!</p>
                <button onclick="openCreateModal()" class="btn-modern primary large" style="width:20%; justify-content:center; border-radius:20px; margin: 0 auto; display: block;"><i class="fas fa-plus"></i> Nuevo Torneo</button>
            </div>
        `;
} else {
    html += `<p style="text-align:center; color:var(--text-muted); padding:40px;">No hay torneos activos ni historial reciente.</p>`;
}

return html;
}

function buildTourneyHero(t, isHistory, canManage, serverIcon) {
const statusMap = {
    open: "Abierto",
    active: "En Curso",
    finished: "Finalizado",
    pending: "En Espera",
};
const st = statusMap[t.status] || t.status;


let bgStyle = `background-image: linear-gradient(to right, #5865f2, #ed4245);`;
if (
    t.image_url &&
    t.image_url !== "null" &&
    t.image_url !== "None" &&
    t.image_url !== "undefined" &&
    t.image_url.trim() !== ""
) {
    bgStyle = `background-image: url('${t.image_url}');`;
} else if (serverIcon) {
    // Use server icon as fallback
    bgStyle = `background-image: url('https://cdn.discordapp.com/icons/${currentServerDataCache.guild.id}/${serverIcon}.png');`;
}

let badgeColor = "var(--text-muted)";
if (t.status === "open" || t.status === "active")
    badgeColor = "var(--success)";
else if (t.status === "finished") badgeColor = "#ed4245";

const winnerHtml = t.winner_name
    ? `<div class="badge" style="background:#ffd700; color:black; font-size:1em; display:flex; align-items:center; gap:6px; box-shadow:0 2px 4px rgba(0,0,0,0.5);">
            <i class="fas fa-crown"></i> ${t.winner_name}
            </div>`
    : "";

let dateDisplay = `<i class="fas fa-calendar"></i> ${t.start_date || "N/A"}`;
if (t.date) {
    dateDisplay = `
            <div style="text-align:left; display:flex; flex-direction:column; gap:6px;">
                <div><i class="fas fa-calendar" style="width:20px; text-align:center;"></i> ${t.date}</div>
                <div style="font-size:0.9em; opacity:0.8"><i class="fas fa-clock" style="width:20px; text-align:center;"></i> Insc: ${t.registration_start_time} - ${t.registration_end_time}</div>
                <div style="font-size:0.9em; opacity:0.8"><i class="fas fa-flag" style="width:20px; text-align:center;"></i> Inicio: ${t.start_time}</div>
            </div>
        `;
}

return `
        <h3 style="margin-bottom:16px;">${isHistory ? "Último Torneo Jugado" : "Torneo Activo"}</h3>
        <div class="active-tourney-hero clickable" onclick="window.location.href='/tournament?guild=${currentGuildId}&tourney=${t.id}'">
            <div class="hero-bg" style="${bgStyle}"></div>
            <div class="hero-overlay">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                    <div style="display:flex; gap:16px; font-size:1em; color:rgba(255,255,255,0.9); font-weight:bold; text-shadow:0 1px 2px rgba(0,0,0,0.8);">
                        <span class="badge" style="background:${badgeColor}; font-size:0.9em;">${st}</span>
                        ${t.winner_name ? winnerHtml : ""}
                    </div>
                    <div style="font-size:0.8em; color:rgba(255,255,255,0.7);">
                        ${dateDisplay}
                    </div>
                </div>
                <h1 style="font-size:2.5rem; margin-bottom:12px; font-weight:800; text-shadow:0 2px 10px rgba(0,0,0,0.5); line-height:1.1;">${t.name}</h1>
                <p style="color:rgba(255,255,255,0.9); font-size:0.95em; max-width:100%; margin-bottom:16px; line-height:1.5; white-space:normal; overflow-wrap:break-word;">
                    ${t.description || "Sin descripción"}
                </p>
                <div class="hero-footer">
                    <div style="display:flex; gap:16px; font-size:1em; color:rgba(255,255,255,0.9); font-weight:bold; text-shadow:0 1px 2px rgba(0,0,0,0.8);">
                        <span><i class="fas fa-users"></i> ${t.max_teams} Equipos</span>
                        <span><i class="fas fa-user-friends"></i> ${t.max_members} vs ${t.max_members}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function buildTournamentsContent(data, canManage) {
let html = "";

if (canManage) {
    html += `
            <div style="margin-bottom:24px; display:flex; justify-content:flex-end;">
                <button onclick="openCreateModal()" class="btn-modern primary" style="border-radius: 20px;"><i class="fas fa-plus"></i> Nuevo Torneo</button>
            </div>
        `;
}

if (data.history && data.history.length > 0) {
    const cards = data.history
    .map((t) => {
        const statusMap = {
        open: "Abierto",
        active: "En Curso",
        finished: "Finalizado",
        pending: "En Espera",
        };
        const st = statusMap[t.status] || t.status;

        let bgStyle = `background-image: linear-gradient(to right, #5865f2, #ed4245);`;
        if (
        t.image_url &&
        t.image_url !== "null" &&
        t.image_url !== "None" &&
        t.image_url !== "undefined" &&
        t.image_url.trim() !== ""
        ) {
        bgStyle = `background-image: url('${t.image_url}');`;
        } else if (data.guild.icon) {
        bgStyle = `background-image: url('https://cdn.discordapp.com/icons/${data.guild.id}/${data.guild.icon}.png');`;
        }

        let badgeColor = "var(--text-muted)";
        if (t.status === "open" || t.status === "active")
        badgeColor = "var(--success)";
        else if (t.status === "finished") badgeColor = "#ed4245";

        const winnerHtml = t.winner_name
        ? `<div class="badge" style="background:#ffd700; color:black; font-size:1em; display:flex; align-items:center; gap:6px;">
                    <i class="fas fa-crown"></i> ${t.winner_name}
                    </div>`
        : "";

        let dateDisplayH = `<i class="fas fa-calendar"></i> ${t.start_date || "Fecha desconocida"}`;
        if (t.date) {
        dateDisplayH = `
                    <div style="text-align:left; display:flex; flex-direction:column; gap:6px;">
                        <div><i class="fas fa-calendar" style="width:20px; text-align:center;"></i> ${t.date}</div>
                        <div style="font-size:0.9em; opacity:0.8"><i class="fas fa-clock" style="width:20px; text-align:center;"></i> Insc: ${t.registration_start_time} - ${t.registration_end_time}</div>
                        <div style="font-size:0.9em; opacity:0.8"><i class="fas fa-flag" style="width:20px; text-align:center;"></i> Inicio: ${t.start_time}</div>
                    </div>
                `;
        }

        return `
                <div class="active-tourney-hero clickable" onclick="window.location.href='/tournament?guild=${currentGuildId}&tourney=${t.id}'" style="margin-bottom:0; box-shadow:0 4px 15px rgba(0,0,0,0.3);">
                    <div class="hero-bg" style="${bgStyle} background-size:cover; background-position:center;"></div>
                    <div class="hero-overlay">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                            <div style="display:flex; gap:16px; font-size:1em; color:rgba(255,255,255,0.9); font-weight:bold; text-shadow:0 1px 2px rgba(0,0,0,0.8);">
                                <span class="badge" style="background:${badgeColor}; font-size:0.9em;">${st}</span>
                                ${winnerHtml}
                            </div>
                            <div style="font-size:0.8em; color:rgba(255,255,255,0.7);">
                                ${dateDisplayH}
                            </div>
                        </div>
                        <h1 style="font-size:2.5rem; margin-bottom:12px; font-weight:800; text-shadow:0 2px 10px rgba(0,0,0,0.5); line-height:1.1;">${t.name}</h1>
                        <p style="color:rgba(255,255,255,0.9); font-size:0.95em; max-width:100%; margin-bottom:16px; line-height:1.5; white-space:normal; overflow-wrap:break-word;">
                            ${t.description || "Sin descripción"}
                        </p>
                        <div class="hero-footer">
                            <div style="display:flex; gap:16px; font-size:1em; color:rgba(255,255,255,0.9); font-weight:bold; text-shadow:0 1px 2px rgba(0,0,0,0.8);">
                                <span><i class="fas fa-users"></i> ${t.max_teams} Equipos</span>
                                <span><i class="fas fa-user-friends"></i> ${t.max_members} vs ${t.max_members}</span>
                            </div>
                            <div style="display:flex; flex-direction:row; align-items:flex-end; gap:4px;">
                                ${canManage ? `<button onclick="event.stopPropagation(); editTournament('${t.id}')" style="background:rgba(0,0,0,0.7); border:none; color:white; padding:10px; border-radius:50%; cursor:pointer; z-index:10;" title="Editar Torneo"><i class="fas fa-edit"></i></button>` : ""}
                                ${canManage ? `<button onclick="event.stopPropagation(); deleteTournament('${t.id}')" style="background:rgba(0,0,0,0.7); border:none; color:#f04747; padding:10px; border-radius:50%; cursor:pointer; z-index:10;" title="Eliminar Torneo"><i class="fas fa-trash"></i></button>` : ""}
                            </div>
                        </div>
                    </div>
                </div>
            `;
    })
    .join("");

    html += `
            <h3 style="margin-bottom:20px;">Historial de Torneos</h3>
            <div class="history-carousel">${cards}</div>
        `;
} else {
    html += `
            <div class="dashboard-card" style="text-align:center; padding:40px; color:var(--text-muted);">
                <p>No hay historial de torneos.</p>
            </div>
        `;
}

return html;
}

function buildSettingsContent(data, roleLabel) {
const config = data.config || {};
return `
        <div class="dashboard-card" style="padding: 0; overflow: hidden;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, var(--accent) 0%, #7289da 100%); padding: 24px 28px; border-bottom: 1px solid var(--border);">
                <h2 style="margin: 0; color: white; display: flex; align-items: center; gap: 12px; font-size: 1.4rem;">
                    <i class="fas fa-cog"></i> Configuración del Servidor
                </h2>
                <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.8); font-size: 0.9rem;">Personaliza el comportamiento del bot en tu servidor</p>
            </div>
            
            <form id="config-form" onsubmit="saveConfig(event)" style="padding: 28px;">
                <!-- Sección: Configuración Básica -->
                <div style="margin-bottom: 32px;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
                        <div style="width: 32px; height: 32px; background: rgba(88, 101, 242, 0.15); border-radius: 8px; display: flex; align-items: center; justify-content: center;">
                            <i class="fas fa-terminal" style="color: var(--accent); font-size: 14px;"></i>
                        </div>
                        <h3 style="margin: 0; font-size: 1.1rem; color: var(--text-header);">Configuración Básica</h3>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                        <div class="form-group" style="margin-bottom: 0;">
                            <label class="form-label" style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                                <i class="fas fa-hashtag" style="color: var(--text-muted); font-size: 12px;"></i> Prefijo del Bot
                            </label>
                            <input type="text" id="cfg-prefix" class="form-input" placeholder="," style="font-size: 1.1rem; text-align: center; max-width: 100px;">
                        </div>
                        <div class="form-group" style="margin-bottom: 0;">
                            <label class="form-label" style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                                <i class="fas fa-shield-alt" style="color: var(--text-muted); font-size: 12px;"></i> Canal Admin Bot
                            </label>
                            <select id="cfg-bot-admin" class="form-select"><option>Cargando...</option></select>
                        </div>
                    </div>
                </div>

                <!-- Sección: Canales de Torneos -->
                <div style="margin-bottom: 32px;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
                        <div style="width: 32px; height: 32px; background: rgba(67, 181, 129, 0.15); border-radius: 8px; display: flex; align-items: center; justify-content: center;">
                            <i class="fas fa-trophy" style="color: #43b581; font-size: 14px;"></i>
                        </div>
                        <h3 style="margin: 0; font-size: 1.1rem; color: var(--text-header);">Canales de Torneos</h3>
                    </div>
                    <div class="form-group" style="margin-bottom: 20px;">
                        <label class="form-label" style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                            <i class="fas fa-folder" style="color: var(--text-muted); font-size: 12px;"></i> Categoría de Torneos
                        </label>
                        <select id="cfg-category" class="form-select"><option>Cargando...</option></select>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                        <div class="form-group" style="margin-bottom: 0;">
                            <label class="form-label" style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                                <i class="fas fa-sitemap" style="color: var(--text-muted); font-size: 12px;"></i> Canal Brackets
                            </label>
                            <select id="cfg-bracket" class="form-select"><option>Cargando...</option></select>
                        </div>
                        <div class="form-group" style="margin-bottom: 0;">
                            <label class="form-label" style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                                <i class="fas fa-door-open" style="color: var(--text-muted); font-size: 12px;"></i> Canal Lobby
                            </label>
                            <select id="cfg-lobby" class="form-select"><option>Cargando...</option></select>
                        </div>
                    </div>
                </div>

                <!-- Sección: Logs -->
                <div style="margin-bottom: 32px;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
                        <div style="width: 32px; height: 32px; background: rgba(250, 166, 26, 0.15); border-radius: 8px; display: flex; align-items: center; justify-content: center;">
                            <i class="fas fa-clipboard-list" style="color: #faa61a; font-size: 14px;"></i>
                        </div>
                        <h3 style="margin: 0; font-size: 1.1rem; color: var(--text-header);">Sistema de Logs</h3>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr auto; gap: 20px; align-items: end;">
                        <div class="form-group" style="margin-bottom: 0;">
                            <label class="form-label" style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                                <i class="fas fa-scroll" style="color: var(--text-muted); font-size: 12px;"></i> Canal de Logs
                            </label>
                            <select id="cfg-logs" class="form-select"><option>Cargando...</option></select>
                        </div>
                        <label class="toggle-switch" style="margin-bottom: 8px;">
                            <input type="checkbox" id="cfg-logs-enabled">
                            <span class="toggle-slider"></span>
                            <span class="toggle-label">Activar Logs</span>
                        </label>
                    </div>
                </div>

                <!-- Sección: Roles Admin -->
                <div style="margin-bottom: 32px;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid var(--border);">
                        <div style="width: 32px; height: 32px; background: rgba(237, 66, 69, 0.15); border-radius: 8px; display: flex; align-items: center; justify-content: center;">
                            <i class="fas fa-user-shield" style="color: #ed4245; font-size: 14px;"></i>
                        </div>
                        <h3 style="margin: 0; font-size: 1.1rem; color: var(--text-header);">Roles de Administración</h3>
                    </div>
                    <div id="admin-roles-display" style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; min-height: 36px; align-items: center;"></div>
                    <div id="admin-roles-editor" style="display: none;">
                        <input type="text" id="cfg-roles" class="form-input" placeholder="IDs de roles separados por coma" style="margin-bottom: 8px;">
                        <small style="color: var(--text-muted); display: flex; align-items: center; gap: 6px;">
                            <i class="fas fa-info-circle"></i> Solo administradores del servidor pueden modificar esta configuración
                        </small>
                    </div>
                </div>

                <!-- Botón Guardar -->
                <button type="submit" class="btn-modern primary" style="width: 100%; justify-content: center; padding: 14px; font-size: 1rem; gap: 10px;">
                    <i class="fas fa-save"></i> Guardar Cambios
                </button>
            </form>
        </div>
    `;
}

function displayAdminRoles(roleIds, isAdmin) {
const container = document.getElementById("admin-roles-display");
const editor = document.getElementById("admin-roles-editor");
const input = document.getElementById("cfg-roles");

if (!container) return;

if (roleIds.length === 0) {
    container.innerHTML =
    '<span style="color:var(--text-muted);">No hay roles admin configurados</span>';
} else {
    const roleHtml = roleIds
    .map((roleId) => {
        const role = guildRoles.find(
        (r) => String(r.id) === String(roleId),
        );
        if (role) {
        const colorHex = role.color
            ? `#${role.color.toString(16).padStart(6, "0")}`
            : "#99aab5";
        return `
                    <span class="role-tag">
                        <span class="role-color" style="background-color: ${colorHex};"></span>
                        ${role.name}
                    </span>
                `;
        } else {
        return `<span class="role-tag" style="opacity:0.5;">ID: ${roleId}</span>`;
        }
    })
    .join("");
    container.innerHTML = roleHtml;
}

if (isAdmin) {
    editor.style.display = "block";
    input.value = roleIds.join(", ");
} else {
    editor.style.display = "none";
}
}

function fillSelect(id, items, selectedValue) {
const sel = document.getElementById(id);
if (!sel) return;
sel.innerHTML = '<option value="">-- Sin Definir --</option>';

// Convert selectedValue to string for comparison, handle null/undefined
const selectedStr = selectedValue ? String(selectedValue).trim() : "";

items.forEach((i) => {
    const opt = document.createElement("option");
    opt.value = i.id;
    opt.textContent = i.name;

    const itemIdStr = String(i.id).trim();
    
    if (selectedStr && itemIdStr === selectedStr) {
    opt.selected = true;
    }
    sel.appendChild(opt);
});
}

function switchTab(tabId) {
sessionStorage.setItem('server_active_tab', tabId);
document
    .querySelectorAll(".tab-content")
    .forEach((el) => el.classList.remove("active"));
document
    .querySelectorAll(".tab-btn")
    .forEach((el) => el.classList.remove("active"));
document.getElementById(`tab-${tabId}`).classList.add("active");

// Ensure the button gets active class even if triggered programmatically
if (event && event.currentTarget) {
        event.currentTarget.classList.add("active");
} else if (event && event.target) {
        event.target.classList.add("active");
}
}

function updatePreview(prefix) {
const nameInput = document.getElementById(prefix + '-t-name');
const descInput = document.getElementById(prefix + '-t-desc');
const teamsInput = document.getElementById(prefix + '-t-teams');
const minInput = document.getElementById(prefix + '-t-min');
const maxInput = document.getElementById(prefix + '-t-max');
const dateInput = document.getElementById(prefix + '-t-date');
const startInput = document.getElementById(prefix + '-t-start');
const regStartInput = document.getElementById(prefix + '-t-reg-start');
const regEndInput = document.getElementById(prefix + '-t-reg-end');
const imgInput = document.getElementById(prefix + '-t-img');

const name = nameInput ? nameInput.value : 'Nombre del Torneo';
const desc = descInput ? descInput.value : 'Descripción del torneo...';
const teams = teamsInput ? teamsInput.value : '16';
const minM = minInput ? minInput.value : '1';
const maxM = maxInput ? maxInput.value : '1';
const date = dateInput ? dateInput.value : 'YYYY-MM-DD';
const start = startInput ? startInput.value : '00:00';
const regStart = regStartInput ? regStartInput.value : '00:00';
const regEnd = regEndInput ? regEndInput.value : '00:00';
const imgUrl = imgInput ? imgInput.value : '';

// Update Name/Desc with Fallback
const nameText = name ? name : 'Nombre del Torneo';
const descText = desc ? desc : 'Descripción del torneo...';

const nameEl = document.getElementById(prefix + '-preview-name');
if(nameEl) nameEl.textContent = nameText;

const descEl = document.getElementById(prefix + '-preview-desc');
if(descEl) descEl.textContent = descText;

const teamsEl = document.getElementById(prefix + '-preview-teams');
if(teamsEl) teamsEl.innerHTML = `<i class="fas fa-users"></i> ${teams} Equipos`;

const membersEl = document.getElementById(prefix + '-preview-members');
if(membersEl) membersEl.innerHTML = `<i class="fas fa-user-friends"></i> ${maxM} vs ${maxM}`;

const dateEl = document.getElementById(prefix + '-preview-date');
if(dateEl) dateEl.textContent = date;

const startEl = document.getElementById(prefix + '-preview-start');
if(startEl) startEl.textContent = start;

const regEl = document.getElementById(prefix + '-preview-reg');
if(regEl) regEl.textContent = `${regStart} - ${regEnd}`;

// Status Update logic
let statusText = 'Abierto';
let statusColor = '#3ba55c'; // Green

// If editing, try to get real status
if (prefix === 'edit') {
    const statusSelect = document.getElementById('edit-t-status');
    const statusGroup = document.getElementById('edit-t-status-group');
    
    // If the status dropdown is visible, use its value (because user might be changing it)
    if (statusGroup && statusGroup.style.display !== 'none' && statusSelect) {
            const val = statusSelect.value;
            const map = { 'open': 'Abierto', 'pending': 'En Espera', 'active': 'En Curso', 'finished': 'Finalizado' };
            statusText = map[val] || val;
            if(val === 'open' || val === 'active') statusColor = '#3ba55c';
            else if(val === 'finished') statusColor = '#ed4245';
            else statusColor = '#6b7280';
    } else {
            // Fallback to DB if hidden
            const id = document.getElementById('edit-t-id').value;
            let t = null;
            if (currentServerDataCache && id) {
                if (currentServerDataCache.active_tournament && currentServerDataCache.active_tournament.id === id) t = currentServerDataCache.active_tournament;
                else if (currentServerDataCache.history) t = currentServerDataCache.history.find(x => x.id === id);
            }
            
            if (t) {
                const map = { 'open': 'Abierto', 'pending': 'En Espera', 'active': 'En Curso', 'finished': 'Finalizado' };
                statusText = map[t.status] || t.status;
                if(t.status === 'finished') statusColor = '#ed4245'; // Red
                else if(t.status === 'pending') statusColor = '#6b7280'; // Gray
                else if(t.status === 'open' || t.status === 'active') statusColor = '#3ba55c';
            }
    }
}

// Update badge
const previewContainer = document.getElementById(prefix + '-preview-bg').parentElement; // hero-bg parent is active-tourney-hero
const badge = previewContainer.querySelector('.badge');
if(badge) {
        badge.textContent = statusText;
        badge.style.background = statusColor;
}


const bgDiv = document.getElementById(prefix + '-preview-bg');
if (bgDiv) {
    // Helper to set fallback image
    const setFallback = () => {
            if (currentServerDataCache && currentServerDataCache.guild && currentServerDataCache.guild.icon) {
                // guild.icon is already a full URL from backend
                bgDiv.style.backgroundImage = `url('${currentServerDataCache.guild.icon}')`;
            } else {
                bgDiv.style.backgroundImage = 'linear-gradient(to right, #5865f2, #ed4245)';
            }
    };
    
    
    if (imgUrl && imgUrl.trim() && imgUrl !== "null" && imgUrl !== "None" && imgUrl !== "undefined") {
        // Validate if it is an image
        const img = new Image();
        img.onload = () => {
            bgDiv.style.backgroundImage = `url('${imgUrl}')`;
        };
        img.onerror = () => {
            setFallback();
        };
        img.src = imgUrl;
    } else {
        setFallback();
    }
}

checkFloatingButton(prefix);
}

let initialEditState = null;

function checkFloatingButton(prefix) {
    const btn = document.getElementById(prefix + '-floating-btn');
    if(!btn) return;

    // Check required fields
    const requiredIds = ['name', 'desc', 'date', 'start', 'reg-start', 'reg-end']; // ID suffixes
    let allFilled = true;
    
    for(const id of requiredIds) {
        const el = document.getElementById(prefix + '-t-' + id);
        if(!el || !el.value.trim()) {
            allFilled = false;
            break;
        }
    }
    
    let show = false;
    if (prefix === 'new') {
        show = allFilled;
    } else if (prefix === 'edit') {
        // Check changes
        if (allFilled && initialEditState) {
            // Compare current values with initial state
            const currentName = document.getElementById('edit-t-name').value;
            const currentDesc = document.getElementById('edit-t-desc').value;
            const currentTeams = document.getElementById('edit-t-teams').value;
            const currentMin = document.getElementById('edit-t-min').value;
            const currentMax = document.getElementById('edit-t-max').value;
            const currentDate = document.getElementById('edit-t-date').value;
            const currentStart = document.getElementById('edit-t-start').value;
            const currentRegStart = document.getElementById('edit-t-reg-start').value;
            const currentRegEnd = document.getElementById('edit-t-reg-end').value;
            const currentImg = document.getElementById('edit-t-img').value;
            const currentStatus = document.getElementById('edit-t-status').value;
            
            if (currentName !== initialEditState.name ||
                currentDesc !== initialEditState.desc ||
                currentTeams !== initialEditState.teams ||
                currentMin !== initialEditState.min ||
                currentMax !== initialEditState.max ||
                currentDate !== initialEditState.date ||
                currentStart !== initialEditState.start ||
                currentRegStart !== initialEditState.regStart ||
                currentRegEnd !== initialEditState.regEnd ||
                currentImg !== initialEditState.img ||
                currentStatus !== initialEditState.status) {
                show = true;
            }
        }
    }
    
    if(show) {
        btn.classList.add('visible');
    } else {
        btn.classList.remove('visible');
    }
}

// Modal Functions
function openCreateModal() {
if (!isLoggedIn) {
    window.location.href = `/login?redirect=/server?id=${currentGuildId}`;
    return;
}
const now = new Date();
const dateInput = document.getElementById("new-t-date");
if (dateInput) dateInput.value = now.toISOString().split("T")[0];

document.getElementById("new-t-reg-start").value = "10:00";
document.getElementById("new-t-reg-end").value = "18:00";
document.getElementById("new-t-start").value = "18:30";

// Reset other fields
document.getElementById("new-t-name").value = "";
document.getElementById("new-t-desc").value = "";
document.getElementById("new-t-teams").value = "16";
document.getElementById("new-t-min").value = "1";
document.getElementById("new-t-max").value = "1";
document.getElementById("new-t-img").value = "";

document.getElementById("modal-create").classList.add("active");
updatePreview('new');
}

function closeCreateModal() {
document.getElementById("modal-create").classList.remove("active");
}

function closeEditModal() {
document.getElementById("modal-edit").classList.remove("active");
}

async function processImageFile(fileInput) {
if (fileInput && fileInput.files && fileInput.files[0]) {
    const file = fileInput.files[0];
    if (file.size > 2 * 1024 * 1024)
    throw new Error("La imagen es muy grande (Max 2MB)");
    return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
    });
}
return null;
}

async function createTournament(e) {
e.preventDefault();
const name = document.getElementById("new-t-name").value;
const teams = document.getElementById("new-t-teams").value;
const desc = document.getElementById("new-t-desc").value;
const minM = document.getElementById("new-t-min").value;
const maxM = document.getElementById("new-t-max").value;

const date = document.getElementById("new-t-date").value;
const regStart = document.getElementById("new-t-reg-start").value;
const regEnd = document.getElementById("new-t-reg-end").value;
const startTime = document.getElementById("new-t-start").value;

let img = document.getElementById("new-t-img").value;
// const fileInput = document.getElementById("new-t-img-file");

/*
try {
    const fileImg = await processImageFile(fileInput);
    if (fileImg) img = fileImg;
} catch (err) {
    return alert(err.message);
}
*/

// If no image provided, use server icon as fallback
if (!img || !img.trim() || img === "null" || img === "None" || img === "undefined") {
    if (currentServerDataCache && currentServerDataCache.guild && currentServerDataCache.guild.icon) {
    img = currentServerDataCache.guild.icon;
    }
}

if (!name) return alert("Nombre requerido");

try {
    const res = await fetch(
    `/api/guild/${currentGuildId}/tournaments/create`,
    {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
        name,
        max_teams: teams,
        description: desc,
        min_members: minM,
        max_members: maxM,
        date,
        reg_start: regStart,
        reg_end: regEnd,
        start_time: startTime,
        image_url: img,
        }),
    },
    );
    const data = await res.json();

    if (res.ok) {
    closeCreateModal();
    loadServerDetail();
    alert("Torneo creado!");
    } else {
    alert("Error: " + data.error);
    }
} catch (e) {
    alert("Error de conexión");
}
}

function editTournament(id) {
if (!currentServerDataCache) return;

// Alias for openEditModal if needed, or just use this function 
// Logic to populate and open modal
let t = null;
if (
    currentServerDataCache.active_tournament &&
    currentServerDataCache.active_tournament.id === id
) {
    t = currentServerDataCache.active_tournament;
} else if (currentServerDataCache.history) {
    t = currentServerDataCache.history.find((x) => x.id === id);
}

if (!t) return alert("Error: Torneo no encontrado");

document.getElementById("edit-t-id").value = t.id;
document.getElementById("edit-t-name").value = t.name;
document.getElementById("edit-t-desc").value = t.description || "";
document.getElementById("edit-t-teams").value = t.max_teams;
document.getElementById("edit-t-min").value = t.min_members || 1;
document.getElementById("edit-t-max").value = t.max_members || 1;

document.getElementById("edit-t-date").value = t.date || "";
document.getElementById("edit-t-reg-start").value =
    t.registration_start_time || "";
document.getElementById("edit-t-reg-end").value =
    t.registration_end_time || "";
document.getElementById("edit-t-start").value = t.start_time || "";

document.getElementById("edit-t-img").value = t.image_url || "";

// Status Populating
const statusGroup = document.getElementById('edit-t-status-group');
const statusSelect = document.getElementById('edit-t-status');
if(statusGroup && statusSelect) {
    statusGroup.style.display = 'block';
    statusSelect.value = t.status;
}

// Store initial state
initialEditState = {
    name: t.name,
    desc: t.description || "",
    teams: String(t.max_teams),
    min: String(t.min_members || 1),
    max: String(t.max_members || 1),
    date: t.date || "",
    start: t.start_time || "",
    regStart: t.registration_start_time || "",
    regEnd: t.registration_end_time || "",
    img: t.image_url || "",
    status: t.status
};

document.getElementById("modal-edit").classList.add("active");
updatePreview('edit');
checkFloatingButton('edit');
}

async function submitEditTournament(e) {
e.preventDefault();
const id = document.getElementById("edit-t-id").value;
const name = document.getElementById("edit-t-name").value;
const desc = document.getElementById("edit-t-desc").value;
const teams = document.getElementById("edit-t-teams").value;
const minM = document.getElementById("edit-t-min").value;
const maxM = document.getElementById("edit-t-max").value;

const date = document.getElementById("edit-t-date").value;
const regStart = document.getElementById("edit-t-reg-start").value;
const regEnd = document.getElementById("edit-t-reg-end").value;
const startTime = document.getElementById("edit-t-start").value;

let img = document.getElementById("edit-t-img").value;
const fileInput = document.getElementById("edit-t-img-file");

const status = document.getElementById("edit-t-status").value;

try {
    const fileImg = await processImageFile(fileInput);
    if (fileImg) img = fileImg;
} catch (err) {
    return alert(err.message);
}

// If no image provided, use server icon as fallback
if (!img || !img.trim() || img === "null" || img === "None" || img === "undefined") {
    if (currentServerDataCache && currentServerDataCache.guild && currentServerDataCache.guild.icon) {
    img = currentServerDataCache.guild.icon;
    }
}

try {
    const res = await fetch(
    `/api/guild/${currentGuildId}/tournament/${id}/update`,
    {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
        name,
        description: desc,
        max_teams: teams,
        min_members: minM,
        max_members: maxM,
        date,
        reg_start: regStart,
        reg_end: regEnd,
        start_time: startTime,
        image_url: img,
        status: status,
        }),
    },
    );

    if (res.ok) {
    closeEditModal();
    loadServerDetail();
    alert("Torneo actualizado!");
    } else {
    const d = await res.json();
    alert("Error: " + d.error);
    }
} catch (e) {
    alert("Error de conexión");
}
}

async function deleteTournament(id) {
if (
    !confirm(
    "¿Estás seguro de eliminar este torneo? Esta acción es irreversible.",
    )
)
    return;

try {
    const res = await fetch(
    `/api/guild/${currentGuildId}/tournament/${id}/delete`,
    {
        method: "POST",
    },
    );
    if (res.ok) {
    loadServerDetail();
    } else {
    alert("Error al eliminar");
    }
} catch (e) {
    alert("Error de conexión");
}
}

async function saveConfig(e) {
e.preventDefault();

const rolesStr = document.getElementById("cfg-roles").value;
const roles = rolesStr
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s);

const payload = {
    prefix: document.getElementById("cfg-prefix").value,
    category_id: document.getElementById("cfg-category").value,
    bracket_channel_id: document.getElementById("cfg-bracket").value,
    lobby_channel_id: document.getElementById("cfg-lobby").value,
    bot_admin_channel_id: document.getElementById("cfg-bot-admin").value,
    tourney_log_channel_id: document.getElementById("cfg-logs").value,
    tourney_logs_enabled:
    document.getElementById("cfg-logs-enabled").checked,
    admin_roles: roles,
};

try {
    const res = await fetch(`/api/guild/${currentGuildId}/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    });
    if (res.ok) alert("Configuración guardada exitosamente");
    else alert("Error al guardar");
} catch (err) {
    alert("Error de conexión");
}
}

init();