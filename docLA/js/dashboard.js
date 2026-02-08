let currentGuildId = null;
let guildChannels = [];
let guildCategories = [];

async function init() {
// User data fetched by layout.js
    await refreshServers();
    updateBotStatusGlobal();
    setInterval(updateBotStatusGlobal, 60000);
}

const HOME_SERVER_ID = '1448450320639197211';

async function updateBotStatusGlobal() {
    const statusEls = document.querySelectorAll('.bot-status-indicator');
    if(statusEls.length === 0) return;

    try {
        const response = await fetch(`https://discord.com/api/guilds/${HOME_SERVER_ID}/widget.json`);
        if (!response.ok) throw new Error('Widget API Error');
        
        const data = await response.json();
        const botMember = data.members.find(member => member.username === 'LA TourneyBot');
        
        if (botMember) {
                statusEls.forEach(el => {
                el.textContent = "Online";
                el.style.color = "#4ade80";
                });
        } else {
                statusEls.forEach(el => {
                el.textContent = "Desconectado";
                el.style.color = "#ef4444";
                });
        }
    } catch(e) {
        console.error("Bot Status Error", e);
        statusEls.forEach(el => {
            el.textContent = "Desconectado";
            el.style.color = "#ef4444"; 
        });
    }
}

// fetchUserData is now handled by layout.js

async function refreshServers() {
    const container = document.getElementById('server-list-container');
    container.innerHTML = '<div class="loading-spinner"></div>';
    
    try {
        const res = await fetch('/api/guilds');
        const guilds = await res.json();
        
        container.innerHTML = '';
        if(guilds.length === 0) {
            container.innerHTML = '<p>No se encontraron servidores Prueba a actualizar la página.</p>';
            return;
        }

        guilds.forEach(g => {
            const card = document.createElement('div');
            card.className = 'dashboard-card clickable';
            
            const isBot = g.bot_in_guild;
            const inviteUrl = `https://discord.com/oauth2/authorize?client_id=1448450835213189191&permissions=8&scope=bot&guild_id=${g.id}`;
            
            if (isBot) {
                card.onclick = () => window.location.href = `/server?id=${g.id}`;
            } else {
                card.onclick = () => window.open(inviteUrl, '_blank');
            }

            const roleLabel = g.role_label || (g.can_manage ? 'Admin' : 'Miembro');
            const badgeClass = roleLabel === 'Admin' ? 'admin' : (roleLabel === 'Organizador' ? 'mod' : 'member');
            const imgStyle = isBot ? '' : 'filter: grayscale(100%); opacity: 0.7;';
            
            // Only show badge if bot is in guild
            const badgeHtml = isBot ? `<span class="badge ${badgeClass}">${roleLabel}</span>` : '';
            const inviteText = !isBot ? '<span style="font-size:0.7em; margin-top:4px; color:var(--accent);">Click para invitar Bot</span>' : '';
            
            card.innerHTML = `
                <div class="server-card-header">
                    <div style="display: flex; flex-direction: column; align-items: center;">
                        <img src="${g.icon || 'https://cdn.discordapp.com/embed/avatars/0.png'}" class="server-icon" style="${imgStyle}">
                        <h3 style="color:white; margin-bottom:4px;">${g.name}</h3>
                    </div>
                    <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
                        ${badgeHtml}
                        ${inviteText}
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    } catch(e) {
        container.innerHTML = '<p style="color:red">Error al cargar servidores.</p>';
    }
}

async function loadServerDetail(guildId) {
    currentGuildId = guildId;
    document.getElementById('view-server-list').style.display = 'none';
    document.getElementById('view-server-detail').style.display = 'block';
    
    // Reset contents
    document.getElementById('detail-server-name').textContent = "Cargando...";
    
    try {
        const res = await fetch(`/api/guild/${guildId}`);
        if(!res.ok) {
            const errText = await res.text();
            throw new Error(`Failed to load: ${res.status} - ${errText}`);
        }
        const data = await res.json();
        currentServerDataCache = data; // Cache data for Edit logic
        
        // Populate Data
        document.getElementById('detail-server-name').textContent = data.guild.name;
        document.getElementById('stat-members').textContent = data.guild.member_count;
        
        // Bot Status is handled globally now via widget api
        const canManage = data.guild.can_manage;
        
        // Badge Logic inside detail
        const roleLabel = data.guild.role_label;
        const headerBadge = document.getElementById('server-role-badge');
        if(headerBadge) {
            headerBadge.className = `badge ${roleLabel === 'Admin' ? 'admin' : (roleLabel === 'Organizador' ? 'mod' : 'member')}`;
            headerBadge.textContent = roleLabel;
        }

        // Handle Permissions UI
        if(!canManage) {
                document.querySelector('[onclick="switchTab(\'settings\')"]').style.display = 'none';
                if(document.getElementById('tab-settings').classList.contains('active')) switchTab('overview');
        } else {
                document.querySelector('[onclick="switchTab(\'settings\')"]').style.display = 'block';
        }

        // Store meta for forms
        guildChannels = data.channels || [];
        guildCategories = data.categories || [];
        
        fillSelect('cfg-category', guildCategories, data.config.category_id);
        fillSelect('cfg-bracket', guildChannels, data.config.bracket_channel_id);
        fillSelect('cfg-lobby', guildChannels, data.config.lobby_channel_id);
        fillSelect('cfg-bot-admin', guildChannels, data.config.bot_admin_channel_id);
        if(data.config.tourney_log_channel_id) fillSelect('cfg-logs', guildChannels, data.config.tourney_log_channel_id);
        else fillSelect('cfg-logs', guildChannels, null); 
        
        document.getElementById('cfg-prefix').value = data.config.prefix || ",";
        document.getElementById('cfg-logs-enabled').checked = !!data.config.tourney_logs_enabled;
        document.getElementById('cfg-roles').value = (data.config.admin_roles || []).join(', ');
        
        document.getElementById('cfg-roles').disabled = (roleLabel !== 'Admin');

        // --- OVERVIEW TAB: Active/Last Tournament or Create CTA ---
        let overviewHTML = '';
        
        let heroTourney = data.active_tournament;
        let isHistory = false;
        
        if (!heroTourney && data.history && data.history.length > 0) {
            heroTourney = data.history[0]; 
            isHistory = true;
        }
        
        if(heroTourney) {
            const t = heroTourney;
            const statusMap = { 'open': 'Abierto', 'active': 'En Curso', 'finished': 'Finalizado', 'pending': 'En Espera' };
            const st = statusMap[t.status] || t.status;
            
            // improved image logic
            let bgStyle = `background-image: linear-gradient(to right, #5865f2, #ed4245);`;
            if(t.image_url && t.image_url.trim() !== "" && t.image_url !== "None") {
                bgStyle = `background-image: url('${t.image_url}');`;
            } else if (g && g.icon) {
                bgStyle = `background-image: url('https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png');`;
            }

            let badgeColor = 'var(--text-muted)'; // Default Pending/Gray
            if (t.status === 'open' || t.status === 'active') badgeColor = 'var(--success)'; // Green
            else if (t.status === 'finished') badgeColor = '#ed4245'; // Red
            
            // Winner HTML - Only Crown + Name in a yellow badge
            const winnerHtml = t.winner_name ? 
                `<div class="badge" style="background:#ffd700; color:black; font-size:1em; display:flex; align-items:center; gap:6px; box-shadow:0 2px 4px rgba(0,0,0,0.5);">
                    <i class="fas fa-crown"></i> ${t.winner_name}
                    </div>` : '<div></div>'; // Empty div to keep flex spacing if no winner? Actually we can just render nothing

            let dateDisplay = `<i class="fas fa-calendar"></i> ${t.start_date || 'N/A'}`;
            if(t.date) {
                    dateDisplay = `
                    <div style="text-align:left; display:flex; flex-direction:column; gap:6px;">
                        <div><i class="fas fa-calendar" style="width:20px; text-align:center;"></i> ${t.date}</div>
                        <div style="font-size:0.9em; opacity:0.8"><i class="fas fa-clock" style="width:20px; text-align:center;"></i> Insc: ${t.registration_start_time} - ${t.registration_end_time}</div>
                        <div style="font-size:0.9em; opacity:0.8"><i class="fas fa-flag" style="width:20px; text-align:center;"></i> Inicio: ${t.start_time}</div>
                    </div>
                    `;
            }

            overviewHTML = `
                <h3 style="margin-bottom:16px;">${isHistory ? 'Último Torneo Jugado' : 'Torneo Activo'}</h3>
                <div class="active-tourney-hero clickable" onclick="window.location.href='/tournament?guild=${currentGuildId}&tourney=${t.id}'">
                    <div class="hero-bg" style="${bgStyle}"></div>
                    <div class="hero-overlay">
                        <!-- Top: Status + Meta -->
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                            <div style="display:flex; gap:16px; font-size:1em; color:rgba(255,255,255,0.9); font-weight:bold; text-shadow:0 1px 2px rgba(0,0,0,0.8);">
                                <span class="badge" style="background:${badgeColor}; font-size:0.9em;">${st}</span>
                                ${t.winner_name ? winnerHtml : ''}
                            </div>
                            
                            <div style="font-size:0.8em; color:rgba(255,255,255,0.7);">
                                ${dateDisplay}
                            </div>
                        </div>
                        
                        <!-- Content -->
                        <h1 style="font-size:2.5rem; margin-bottom:12px; font-weight:800; text-shadow:0 2px 10px rgba(0,0,0,0.5); line-height:1.1;">${t.name}</h1>
                        
                        <p style="color:rgba(255,255,255,0.9); font-size:0.95em; max-width:100%; margin-bottom:16px; line-height:1.5; white-space:normal; overflow-wrap:break-word;">
                            ${t.description || 'Sin descripción'}
                        </p>
                        
                        <!-- Footer: Winner Left, Details Right -->
                        <div class="hero-footer">
                            <div>
                                
                                <div style="display:flex; gap:16px; font-size:1em; color:rgba(255,255,255,0.9); font-weight:bold; text-shadow:0 1px 2px rgba(0,0,0,0.8);">
                                    <span><i class="fas fa-users"></i> ${t.max_teams} Equipos</span>
                                    <span><i class="fas fa-user-friends"></i> ${t.max_members} vs ${t.max_members}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else {
                // No active AND No history
                if(canManage) {
                overviewHTML = `
                    <div class="dashboard-card" style="text-align:center; padding:60px 20px; border-style:dashed; margin-top:20px;">
                        <i class="fas fa-trophy" style="font-size:4rem; color:var(--text-muted); margin-bottom:24px; opacity:0.5;"></i>
                        <h2 style="margin-bottom:12px;">No hay torneos activos</h2>
                        <p style="margin-bottom:32px; color:var(--text-muted);">¡Crea uno ahora para empezar la competición en tu servidor!</p>
                        <button onclick="openCreateModal()" class="action-btn primary large" style="width:20%; justify-content:center; border-radius:20px; margin: 0 auto; display: block;"><i class="fas fa-plus"></i> Nuevo Torneo</button>
                    </div>
                `;
                } else {
                    overviewHTML = `<p style="text-align:center; color:var(--text-muted); padding:40px;">No hay torneos activos ni historial reciente en este servidor.</p>`;
                }
        }
        
        // Inject into Overview
        const ovContainer = document.getElementById('overview-tourney-area');
        if(ovContainer) ovContainer.innerHTML = overviewHTML;


        // --- TOURNAMENTS TAB: Create Button + History Carousel ---
        const tourneysTabContent = document.getElementById('tab-tournaments');
        
        let createBtnArea = '';
        if(canManage) {
                createBtnArea = `
                <div style="margin-bottom:24px; display:flex; justify-content:flex-end;">
                    <button onclick="openCreateModal()" class="action-btn primary"><i class="fas fa-plus"></i> Nuevo Torneo</button>
                </div>
                `;
        }
        
        let historyHTML = '';
        if(data.history && data.history.length > 0) {
                const cards = data.history.map(t => {
                    const statusMap = { 'open': 'Abierto', 'active': 'En Curso', 'finished': 'Finalizado', 'pending': 'En Espera' };
                    const st = statusMap[t.status] || t.status;
                    // Improved image logic for history cards
                    let bgStyle = `background-image: linear-gradient(to right, #5865f2, #ed4245);`;
                    if(t.image_url && t.image_url.trim() !== "" && t.image_url !== "None") {
                        bgStyle = `background-image: url('${t.image_url}');`;
                    } else if (data.guild && data.guild.icon) { // Use data.guild for the current server's icon
                        bgStyle = `background-image: url('https://cdn.discordapp.com/icons/${data.guild.id}/${data.guild.icon}.png');`;
                    }

                    let badgeColor = 'var(--text-muted)'; // Default Pending/Gray
                    if (t.status === 'open' || t.status === 'active') badgeColor = 'var(--success)';
                    else if (t.status === 'finished') badgeColor = '#ed4245'; // Red
                    const date = t.start_date || 'Fecha desconocida';

                    const desc = t.description || 'Sin descripción';
                    
                    const winnerHtml = t.winner_name ? 
                        `<div class="badge" style="background:#ffd700; color:black; font-size:1em; display:flex; align-items:center; gap:6px; box-shadow:0 2px 4px rgba(0,0,0,0.5);">
                            <i class="fas fa-crown"></i> ${t.winner_name}
                        </div>` : '';

                    let dateDisplayH = `<i class="fas fa-calendar"></i> ${date}`;
                    if(t.date) {
                        dateDisplayH = `
                            <div style="text-align:left; display:flex; flex-direction:column; gap:6px;">
                                <div><i class="fas fa-calendar" style="width:20px; text-align:center;"></i> ${t.date}</div>
                                <div style="font-size:0.9em; opacity:0.8"><i class="fas fa-clock" style="width:20px; text-align:center;"></i> Insc: ${t.registration_start_time} - ${t.registration_end_time}</div>
                                <div style="font-size:0.9em; opacity:0.8"><i class="fas fa-flag" style="width:20px; text-align:center;"></i> Inicio: ${t.start_time}</div>
                            </div>
                        `;
                    }

                    return `
                        <div class="active-tourney-hero clickable" onclick="window.location.href='tournament.html?guild=${currentGuildId}&tourney=${t.id}'" style="margin-bottom:0; box-shadow:0 4px 15px rgba(0,0,0,0.3);">
                            <div class="hero-bg" style="${bgStyle} background-size:cover; background-position:center;"></div>
                            <div class="hero-overlay">
                                <!-- Top Row -->
                                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                                    <div style="display:flex; gap:16px; font-size:1em; color:rgba(255,255,255,0.9); font-weight:bold; text-shadow:0 1px 2px rgba(0,0,0,0.8);">
                                        <span class="badge" style="background:${badgeColor}; font-size:0.9em;">${st}</span>
                                        ${winnerHtml}
                                    </div>
                                    <div style="font-size:0.8em; color:rgba(255,255,255,0.7);">
                                        ${dateDisplayH}
                                    </div>
                                </div>
                                
                                <!-- Title & Desc -->
                                <h1 style="font-size:2.5rem; margin-bottom:12px; font-weight:800; text-shadow:0 2px 10px rgba(0,0,0,0.5); line-height:1.1;">${t.name}</h1>
                                <p style="color:rgba(255,255,255,0.9); font-size:0.95em; max-width:100%; margin-bottom:16px; line-height:1.5; white-space:normal; overflow-wrap:break-word;">
                                    ${desc}
                                </p>
                                <div class="hero-footer">
                                    <div>
                                        <div style="display:flex; gap:16px; font-size:1em; color:rgba(255,255,255,0.9); font-weight:bold; text-shadow:0 1px 2px rgba(0,0,0,0.8);">
                                            <span><i class="fas fa-users"></i> ${t.max_teams} Equipos</span>
                                            <span><i class="fas fa-user-friends"></i> ${t.max_members} vs ${t.max_members}</span>
                                        </div>
                                    </div>
                                    <div style="display:flex; flex-direction:row; align-items:flex-end; gap:4px;">
                                        ${canManage ? `<button onclick="event.stopPropagation(); editTournament('${t.id}')" style="background:rgba(0,0,0,0.7); border:none; color:white; padding:10px; border-radius:50%; cursor:pointer; z-index:10; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'" title="Editar Torneo"><i class="fas fa-edit"></i></button>` : ''}
                                        ${canManage ? `<button onclick="event.stopPropagation(); deleteTournament('${t.id}')" style="background:rgba(0,0,0,0.7); border:none; color:#f04747; padding:10px; border-radius:50%; cursor:pointer; z-index:10; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'" title="Eliminar Torneo"><i class="fas fa-trash"></i></button>` : ''}
                                </div>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
                
                historyHTML = `
                    <h3 style="margin-bottom:20px;">Historial de Torneos</h3>
                    <div class="carousel-container">
                        <div class="history-carousel" id="history-scroll">
                            ${cards}
                        </div>
                    </div>
                `;
        } else {
            historyHTML = `
                <div class="dashboard-card" style="text-align:center; padding:40px; color:var(--text-muted);">
                    <p>No hay historial de torneos.</p>
                </div>`;
        }
        
        tourneysTabContent.innerHTML = createBtnArea + historyHTML;


    } catch(e) {
        console.error(e);
        alert("Error al actualizar vista: " + e.message);
        document.getElementById('detail-server-name').textContent = "Error de Conexión";
        // Do not go back to server list, stay here so user doesn't lose context
    }
}

// --- Tournament Actions ---

function openCreateModal() {
    // Set Default Date/Time
    const now = new Date();
    const dateInput = document.getElementById('new-t-date');
    if(dateInput) dateInput.value = now.toISOString().split('T')[0];
    
    // Defaults
    document.getElementById('new-t-reg-start').value = "10:00";
    document.getElementById('new-t-reg-end').value = "18:00";
    document.getElementById('new-t-start').value = "18:30";
    
    document.getElementById('modal-create').classList.add('active');
}

function closeCreateModal() {
    document.getElementById('modal-create').classList.remove('active');
}

async function processImageFile(fileInput) {
    if(fileInput && fileInput.files && fileInput.files[0]) {
        const file = fileInput.files[0];
        if(file.size > 2 * 1024 * 1024) throw new Error("La imagen es muy grande (Max 2MB)");
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
    const name = document.getElementById('new-t-name').value;
    const teams = document.getElementById('new-t-teams').value;
    const desc = document.getElementById('new-t-desc').value;
    const minM = document.getElementById('new-t-min').value;
    const maxM = document.getElementById('new-t-max').value;
    
    const date = document.getElementById('new-t-date').value;
    const regStart = document.getElementById('new-t-reg-start').value;
    const regEnd = document.getElementById('new-t-reg-end').value;
    const startTime = document.getElementById('new-t-start').value;
    
    let img = document.getElementById('new-t-img').value; 
    const fileInput = document.getElementById('new-t-img-file');
    
    try {
        const fileImg = await processImageFile(fileInput);
        if(fileImg) img = fileImg;
    } catch(err) {
        return alert(err.message);
    }
    
    if(!name) return alert("Nombre requerido");
    
    try {
        const res = await fetch(`/api/guild/${currentGuildId}/tournaments/create`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                name: name, 
                max_teams: teams, 
                description: desc,
                min_members: minM,
                max_members: maxM,
                date: date,
                reg_start: regStart,
                reg_end: regEnd,
                start_time: startTime,
                image_url: img
            })
        });
        const data = await res.json();
        
        if(res.ok) {
            closeCreateModal();
            loadServerDetail(currentGuildId); // Reload
            alert("Torneo creado!");
        } else {
            alert("Error: " + data.error);
        }
    } catch(e) { alert("Error de conexión"); }
}

let currentServerDataCache = null; // To store loaded data for editing

function closeEditModal() {
        document.getElementById('modal-edit').classList.remove('active');
}

function editTournament(id) {
    // Find tourney in cache (active or history)
    // We need to access the data loaded in loadServerDetail. 
    // Currently it is not stored globally, let's fix that by attaching it to window or var
    // Wait, we can find it in `currentServerDataCache` if we define it in `loadServerDetail`
    // Let's rely on fetching details or iterating UI? Better fetching details again is cleaner but slower.
    // Let's modify `loadServerDetail` to store data in `currentServerDataCache`.
    
    if(!currentServerDataCache) return;

    let t = null;
    if (currentServerDataCache.active_tournament && currentServerDataCache.active_tournament.id === id) {
        t = currentServerDataCache.active_tournament;
    } else if (currentServerDataCache.history) {
        t = currentServerDataCache.history.find(x => x.id === id);
    }
    
    if(!t) return alert("Error: Torneo no encontrado en caché");

    document.getElementById('edit-t-id').value = t.id;
    document.getElementById('edit-t-name').value = t.name;
    document.getElementById('edit-t-desc').value = t.description || "";
    document.getElementById('edit-t-teams').value = t.max_teams;
    document.getElementById('edit-t-min').value = t.min_members || 1;
    document.getElementById('edit-t-max').value = t.max_members || 1;
    
    document.getElementById('edit-t-date').value = t.date || "";
    document.getElementById('edit-t-reg-start').value = t.registration_start_time || "";
    document.getElementById('edit-t-reg-end').value = t.registration_end_time || "";
    document.getElementById('edit-t-start').value = t.start_time || "";
    
    document.getElementById('edit-t-img').value = t.image_url || "";
    
    document.getElementById('modal-edit').classList.add('active');
}

async function submitEditTournament(e) {
    e.preventDefault();
    const id = document.getElementById('edit-t-id').value;
    const name = document.getElementById('edit-t-name').value;
    const desc = document.getElementById('edit-t-desc').value;
    const teams = document.getElementById('edit-t-teams').value;
    const minM = document.getElementById('edit-t-min').value;
    const maxM = document.getElementById('edit-t-max').value;
    
    const date = document.getElementById('edit-t-date').value;
    const regStart = document.getElementById('edit-t-reg-start').value;
    const regEnd = document.getElementById('edit-t-reg-end').value;
    const startTime = document.getElementById('edit-t-start').value;
    
    let img = document.getElementById('edit-t-img').value; 
    const fileInput = document.getElementById('edit-t-img-file');

    try {
        const fileImg = await processImageFile(fileInput);
        if(fileImg) img = fileImg;
    } catch(err) { return alert(err.message); }

        try {
        const res = await fetch(`/api/guild/${currentGuildId}/tournament/${id}/update`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                name: name, 
                description: desc,
                max_teams: teams, 
                min_members: minM,
                max_members: maxM,
                date: date,
                reg_start: regStart,
                reg_end: regEnd,
                start_time: startTime,
                image_url: img
            })
        });
        
        if(res.ok) {
            closeEditModal();
            loadServerDetail(currentGuildId); 
            alert("Torneo actualizado!");
        } else {
            const d = await res.json();
            alert("Error: " + d.error);
        }
    } catch(e) { alert("Error de conexión"); }
}

async function deleteTournament(id) {
    if(!confirm("¿Estás seguro de eliminar este torneo? Esta acción es irreversible.")) return;
    
    try {
            const res = await fetch(`/api/guild/${currentGuildId}/tournament/${id}/delete`, {
            method: 'POST'
        });
        if(res.ok) {
            loadServerDetail(currentGuildId);
        } else {
            alert("Error al eliminar");
        }
    } catch(e) { alert("Error de conexión"); }
}

function fillSelect(id, items, selectedValue) { // no funciona siempre sale seleccionar
    const sel = document.getElementById(id);
    if(!sel) return;
    sel.innerHTML = '<option value="">-- Seleccionar --</option>';
    // console.log(`Filling ${id} with ${items.length} items. Selected:`, selectedValue);
    items.forEach(i => {
        const opt = document.createElement('option');
        opt.value = i.id;
        opt.textContent = i.name;
        
        // Robust comparison
        const valA = String(i.id).trim();
        const valB = selectedValue ? String(selectedValue).trim() : "";
        
        if(valB && valA === valB) opt.selected = true;
        sel.appendChild(opt);
    });
}

async function saveConfig(e) {
    e.preventDefault();
    if(!currentGuildId) return;
    
    const rolesStr = document.getElementById('cfg-roles').value;
    const roles = rolesStr.split(',').map(s => s.trim()).filter(s => s);
    
    const payload = {
        prefix: document.getElementById('cfg-prefix').value,
        category_id: document.getElementById('cfg-category').value,
        bracket_channel_id: document.getElementById('cfg-bracket').value,
        lobby_channel_id: document.getElementById('cfg-lobby').value,
        bot_admin_channel_id: document.getElementById('cfg-bot-admin').value,
        tourney_log_channel_id: document.getElementById('cfg-logs').value,
        tourney_logs_enabled: document.getElementById('cfg-logs-enabled').checked,
        admin_roles: roles
    };
    
    try {
        const res = await fetch(`/api/guild/${currentGuildId}/config`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        if(res.ok) alert("Configuración guardada exitosamente");
        else alert("Error al guardar");
    } catch(err) {
        alert("Error de conexión");
    }
}

function showServerList() {
    document.getElementById('view-server-detail').style.display = 'none';
    document.getElementById('view-server-list').style.display = 'block';
    currentGuildId = null;
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById(`tab-${tabId}`).classList.add('active');
    event.target.classList.add('active');
}

// Sidebar toggle
// Sidebar toggle handled by layout.js

// Bug & Suggestion Logic handled by layout.js

init();