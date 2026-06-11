// Dashboard: lista de servidores del usuario.
// El detalle de cada servidor (torneos, configuración, blacklist) vive en la página /server.

let currentGuildId = null;

// Client ID público del bot (necesario para el enlace de invitación)
const BOT_CLIENT_ID = '1448450835213189191';

async function init() {
    await refreshServers();
    updateBotStatusGlobal();
    setInterval(updateBotStatusGlobal, 60000);
}

// Estado del bot en tiempo real vía heartbeat propio (sin depender del widget de Discord)
async function updateBotStatusGlobal() {
    const statusEls = document.querySelectorAll('.bot-status-indicator');
    if (statusEls.length === 0) return;

    try {
        const response = await fetch('/api/bot/live');
        if (!response.ok) throw new Error('Live status API error');
        const data = await response.json();
        const online = !!(data && data.online);

        statusEls.forEach(el => {
            el.textContent = online ? 'Online' : 'Desconectado';
            el.style.color = online ? '#4ade80' : '#ef4444';
        });
    } catch (e) {
        console.error('Bot Status Error', e);
        statusEls.forEach(el => {
            el.textContent = 'Desconectado';
            el.style.color = '#ef4444';
        });
    }
}

async function refreshServers() {
    const container = document.getElementById('server-list-container');
    if (!container) return;
    container.innerHTML = '<div class="loading-spinner"></div>';

    try {
        const res = await fetch('/api/guilds');
        const guilds = await res.json();

        container.innerHTML = '';
        if (!Array.isArray(guilds) || guilds.length === 0) {
            container.innerHTML = '<p>No se encontraron servidores. Prueba a actualizar la página.</p>';
            return;
        }

        guilds.forEach(g => {
            const card = document.createElement('div');
            card.className = 'dashboard-card clickable';

            const isBot = g.bot_in_guild;
            const inviteUrl = `https://discord.com/oauth2/authorize?client_id=${BOT_CLIENT_ID}&permissions=8&scope=bot&guild_id=${g.id}`;

            if (isBot) {
                card.onclick = () => window.location.href = `/server?id=${g.id}`;
            } else {
                card.onclick = () => window.open(inviteUrl, '_blank');
            }

            const roleLabel = g.role_label || (g.can_manage ? 'Admin' : 'Miembro');
            const badgeClass = roleLabel === 'Admin' ? 'admin' : (roleLabel === 'Organizador' ? 'mod' : 'member');
            const imgStyle = isBot ? '' : 'filter: grayscale(100%); opacity: 0.7;';

            const badgeHtml = isBot ? `<span class="badge ${badgeClass}">${escapeHtml(roleLabel)}</span>` : '';
            const inviteText = !isBot ? '<span style="font-size:0.7em; margin-top:4px; color:var(--accent);">Click para invitar Bot</span>' : '';

            card.innerHTML = `
                <div class="server-card-header">
                    <div style="display: flex; flex-direction: column; align-items: center;">
                        <img src="${encodeURI(g.icon || 'https://cdn.discordapp.com/embed/avatars/0.png')}" class="server-icon" style="${imgStyle}">
                        <h3 style="color:white; margin-bottom:4px;">${escapeHtml(g.name)}</h3>
                    </div>
                    <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
                        ${badgeHtml}
                        ${inviteText}
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (e) {
        container.innerHTML = '<p style="color:red">Error al cargar servidores.</p>';
    }
}

// El enlace "Mis Servidores" de la barra lateral invoca esta función.
function showServerList() {
    const listView = document.getElementById('view-server-list');
    if (listView) listView.style.display = 'block';
    currentGuildId = null;
}

init();
