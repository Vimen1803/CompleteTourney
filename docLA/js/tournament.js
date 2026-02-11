let tourneyData = null;
let guildDataGlobal = null;
let activeTab = 'general';
let lastDataHash = '';

// Tab Switching Logic
window.switchTournamentTab = function(tabName) {
    activeTab = tabName;
    const generalTab = document.getElementById('tab-general');
    const matchupsTab = document.getElementById('tab-matchups');
    const btnGeneral = document.getElementById('btn-general');
    const btnMatchups = document.getElementById('btn-matchups');
    
    if (tabName === 'general') {
        if(generalTab) generalTab.style.display = 'block';
        if(matchupsTab) matchupsTab.style.display = 'none';
        
        if(btnGeneral) btnGeneral.classList.add('active');
        if(btnMatchups) btnMatchups.classList.remove('active');
    } else {
        if(generalTab) generalTab.style.display = 'none';
        if(matchupsTab) matchupsTab.style.display = 'flex'; // Flex for centering
        
        if(btnGeneral) btnGeneral.classList.remove('active');
        if(btnMatchups) btnMatchups.classList.add('active');
    }
};

// Delete Team Function (Available globally)
window.deleteTeam = async function(guildId, teamId) {
    if(!confirm("¿Estás seguro de que quieres eliminar este equipo?")) return;
    try {
        const res = await fetch(`/api/guild/${guildId}/team/${teamId}/delete`, { method: 'POST' });
        if(res.ok) {
            loadTournament(true); // Force Reload
        } else {
            alert("Error al eliminar equipo. Verifica permisos.");
        }
    } catch(e) {
            alert("Error de conexión");
    }
}

async function loadTournament(force = false) {
    const params = new URLSearchParams(window.location.search);
    const guildId = params.get('guild');
    const tourneyId = params.get('tourney');
    
    if(!guildId || !tourneyId) {
        document.getElementById('content').innerHTML = "<h1>Error: Falta ID de torneo o servidor</h1>";
        return;
    }

    // Check if user is logged in
    // Check if user is logged in (Data is already in data.is_logged_in from tournament fetch)
    // Legacy user-section update removed as it's handled by layout.js

    try {
        const res = await fetch(`/api/guild/${guildId}/tournament/${tourneyId}`);
        if(!res.ok) throw new Error("Not Found");
        const data = await res.json();
        
        // Fetch guild info for icon fallback and store globally
        const guildRes = await fetch(`/api/guild/${guildId}/public`);
        const guildData = guildRes.ok ? await guildRes.json() : null;
        guildDataGlobal = guildData; // Store for preview

        // Simple Change Detection
        const currentHash = JSON.stringify({
            t: data.tournament,
            teams: data.teams,
            can: data.can_manage
        });
        
        if (!force && currentHash === lastDataHash) {
            return; // No changes
        }
        lastDataHash = currentHash;

        const t = data.tournament;
        tourneyData = t; // Store global for Edit

        const teams = data.teams;
        
        const canManage = data.can_manage;
        const isLoggedIn = data.is_logged_in;
        
        const roleLabel = data.role_label;
        const inviteUrl = data.invite_url || "";
        const hasInvite = inviteUrl && inviteUrl.trim() !== "" && inviteUrl !== "None";

        // Login Banner for guests or Externo with Invite
        let loginBannerHtml = '';
        if (!isLoggedIn) {
            loginBannerHtml = `
                <div style="background: linear-gradient(135deg, #5865f2 0%, #7289da 100%); padding: 20px; border-radius: 8px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center;">
                    <p style="color: white; margin: 0; font-weight: 500;"><i class="fas fa-info-circle"></i> Inicia sesión con Discord para gestionar el torneo y participar</p>
                    <a href="/login?redirect=/tournament?guild=${guildId}%26tourney=${tourneyId}" style="background: white; color: #5865f2; padding: 10px 20px; border-radius: 6px; font-weight: bold; display: flex; align-items: center; gap: 8px; text-decoration: none;">
                        <i class="fab fa-discord"></i> Iniciar Sesión
                    </a>
                </div>
            `;
        } else if (roleLabel === "Externo") {
             loginBannerHtml = `
                <div style="background: linear-gradient(135deg, #5865f2 0%, #7289da 100%); padding: 20px; border-radius: 8px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center;">
                    <p style="color: white; margin: 0; font-weight: 500;"><i class="fas fa-info-circle"></i> ¡Únete al servidor para participar en los torneos!</p>
                    ${hasInvite ? `<a href="${inviteUrl}" target="_blank" style="background: white; color: #5865f2; padding: 10px 20px; border-radius: 6px; font-weight: bold; display: flex; align-items: center; gap: 8px; text-decoration: none;"> <i class="fab fa-discord"></i> Unirse al Servidor </a>` : ''}
                </div>
            `;
        }
        
        let badgeClass = "member";
        if (roleLabel === "Admin") badgeClass = "admin";
        else if (roleLabel === "Organizador") badgeClass = "mod";
        else if (roleLabel === "Externo") badgeClass = "external";
        
        // CSS for badge (inline or separate file? Assuming server.css covers some, but we need external style if not present)
        // tournament.css doesn't seem to have specific badge styles, relying on global or inline.
        // We will use inline styles for the badge color if needed or rely on server.css classes if imported (layout usually imports specific css).
        // Check if server.css is imported in tournament page? tournament.html usually imports tournament.css.
        // I'll add inline style mapping for simplicity or assume styles exist.
        // Server.css introduced .badge.external. Tournament.css has .badge.
        
        let badgeStyle = "background: #5865f2;";
        if (roleLabel === "Admin") badgeStyle = "background: #ed4245;";
        else if (roleLabel === "Organizador") badgeStyle = "background: #e67e22;";
        else if (roleLabel === "Externo") badgeStyle = "background: #747f8d;"; // Gray for external
        
        // Banner Logic
        let bannerStyle = `background-image: linear-gradient(to right, #5865f2, #ed4245);`;
        if(t.image_url && t.image_url.trim() !== "" && t.image_url !== "None") {
            bannerStyle = `background-image: url('${t.image_url}');`;
        } else if (guildData && guildData.guild && guildData.guild.icon) {
            bannerStyle = `background-image: url('https://cdn.discordapp.com/icons/${guildId}/${guildData.guild.icon}.png?size=1024');`;
        }
        
        const statusMap = { 'open': 'Abierto', 'active': 'En Curso', 'finished': 'Finalizado', 'pending': 'En Espera' };
        const st = statusMap[t.status] || t.status;
        
        // Status color logic
        let statusColor = '#6b7280'; // Default Pending/Gray
        if(t.status === 'open' || t.status === 'active') statusColor = '#3ba55c'; // Green
        else if(t.status === 'finished') statusColor = '#ed4245'; // Red
        
        const bracketStyle = t.last_bracket_url 
            ? `background-image: url('${t.last_bracket_url}'); background-repeat: no-repeat; background-position: center; background-size: contain;` 
            : `background-image: url('https://tourneydoc.victormenjon.es/data/image.png'); background-repeat: repeat; background-position: center; background-size: 100px;`;

        const winnerHtml = t.winner_name ? 
            `<div style="padding: 4px 10px; border-radius: 4px; font-size: 0.8em; font-weight: bold; text-transform: uppercase; background:#ffd700; color:black; display:flex; align-items:center; gap:6px; box-shadow:0 2px 4px rgba(0,0,0,0.5);">
                <i class="fas fa-crown"></i> ${t.winner_name}
                </div>` : '';

        // Determine Tab Visibility
        const generalDisplay = activeTab === 'general' ? 'block' : 'none';
        const matchupsDisplay = activeTab === 'matchups' ? 'flex' : 'none';
        const generalClass = activeTab === 'general' ? 'tab-link active' : 'tab-link';
        const matchupsClass = activeTab === 'matchups' ? 'tab-link active' : 'tab-link';

        document.getElementById('content').innerHTML = `
            ${loginBannerHtml}
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <div style="display:flex; align-items:center; gap:15px;">
                    <a href="/server?id=${guildId}" class="back-btn" style="text-decoration: none; margin-bottom: 0;"><i class="fas fa-arrow-left"></i> Volver a Servidor</a>
                </div>
                
                <div style="display: flex; gap: 20px;">
                    <span onclick="switchTournamentTab('general')" id="btn-general" class="${generalClass}">General</span>
                    <span onclick="switchTournamentTab('matchups')" id="btn-matchups" class="${matchupsClass}">Enfrentamientos</span>
                </div>
            </div>

            <div id="tab-general" style="display: ${generalDisplay};">
                <div class="hero-section">
                    <div class="hero-bg" style="${bannerStyle}"></div>
                    <div class="hero-overlay">
                        <div class="hero-header">
                            <div style="display:flex; gap:16px; font-size:1em; color:rgba(255,255,255,0.9); font-weight:bold; text-shadow:0 1px 2px rgba(0,0,0,0.8);">
                                <span class="hero-status" style="background: ${statusColor}; color: white;">${st}</span>
                                ${winnerHtml}
                            </div>
                            <div style="font-size:0.8em; color:rgba(255,255,255,0.7);">
                                ${t.date ? 
                                    `<div style="text-align:left; display:flex; flex-direction:column; gap:6px;">
                                        <div><i class="fas fa-calendar" style="width:20px; text-align:center;"></i> ${t.date}</div>
                                        <div style="font-size:0.9em; opacity:0.8"><i class="fas fa-clock" style="width:20px; text-align:center;"></i> Insc: ${t.registration_start_time} - ${t.registration_end_time}</div>
                                        <div style="font-size:0.9em; opacity:0.8"><i class="fas fa-flag" style="width:20px; text-align:center;"></i> Inicio: ${t.start_time}</div>
                                    </div>` 
                                    : `<i class="fas fa-calendar"></i> ${t.start_date || 'N/A'}`}
                            </div>
                        </div>

                        <div class="hero-title">${t.name}</div>
                        <div class="hero-description">${t.description || 'Sin descripción'}</div>

                        <div class="hero-footer">
                            <div style="display:flex; gap:20px; color:rgba(255,255,255,0.8); font-weight:500;">
                                <span><i class="fas fa-users"></i> ${t.max_teams} Equipos</span>
                                <span><i class="fas fa-user-friends"></i> ${t.min_members}-${t.max_members} Miembros/Equipo</span>
                            </div>
                            <div style="display:flex; gap:8px;">
                                ${data.can_manage ? `
                                    <button onclick="editTournament()" style="background:rgba(255,255,255,0.1); border:none; color:white; padding:8px 12px; border-radius:50%; cursor:pointer;"><i class="fas fa-edit"></i></button>
                                    <button onclick="deleteTournament()" style="background:rgba(240,71,71,0.2); border:none; color:#f04747; padding:8px 12px; border-radius:50%; cursor:pointer;"><i class="fas fa-trash"></i></button>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="grid-layout">
                    <div class="main-column">
                        <div class="section-card" style="height: auto; min-width:205%;">
                            <h2><i class="fas fa-users"></i> Equipos Registrados (${teams.length}/${t.max_teams})</h2>
                            <div class="team-list" style="margin-top:16px; overflow-y: visible; max-height: none;">
                                ${!isLoggedIn || roleLabel === "Externo" ? `<p style="color:var(--text-muted); margin:0; font-size:0.9em;">Debes unirte al servidor para ver los equipos.</p>` 
                                : teams.length === 0 ? '<p style="color:var(--text-muted); margin:0; font-size:0.9em;">Aún no hay equipos registrados.</p>' 
                                : teams.map(tm => {
                                    const membersHtml = (tm.resolved_members || []).map(m => `
                                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                                            ${m.is_leader ? '<i class="fas fa-crown" style="color:#ffd700; font-size:0.8em;"></i>' : '<div style="width:14px;"></div>'} 
                                            <img src="${m.avatar}" style="width: 24px; height: 24px; border-radius: 50%; object-fit: cover; background:var(--bg-tertiary);" alt="Avatar">
                                            <span style="font-size: 0.9em; ${m.is_leader ? 'font-weight:bold; color:white;' : 'color:var(--text-normal);'}">${m.name}</span>
                                        </div>
                                    `).join('');

                                    // Delete Button
                                    const canDelete = canManage && (t.status === 'open' || t.status === 'pending');
                                    const deleteBtn = canDelete ? `
                                        <div onclick="deleteTeam('${guildId}', '${tm.id}')" style="position: absolute; bottom: 10px; right: 10px; cursor: pointer; color: #ed4245; opacity: 0.7; transition: opacity 0.2s;" title="Eliminar Equipo">
                                            <i class="fas fa-trash"></i>
                                        </div>
                                    ` : '';
                                    
                                    // Dynamic height + relative positioning for delete button
                                    return `
                                    <div class="team-item" style="height: calc(30 + ${t.max_members * 50}px); position: relative;">
                                        <div class="team-name" style="padding-bottom:5px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center;">
                                            <span>${tm.name}</span>
                                            <span style="font-size:0.75em; background:var(--bg-secondary); padding:2px 8px; border-radius:12px;">${tm.resolved_members.length}</span>
                                        </div>
                                        <div style="display:flex; flex-direction:column; gap:10px;">
                                            ${membersHtml}
                                        </div>
                                        ${deleteBtn}
                                    </div>
                                `}).join('')}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div id="tab-matchups" style="display: ${matchupsDisplay}; min-height: calc(100vh - 200px); width: 100%; align-items: center; justify-content: center; border-radius: 12px; ${bracketStyle}"></div>
        `;
    } catch(e) {
        if (!tourneyData) {
            document.getElementById('content').innerHTML = "<h1>Error cargando torneo</h1><p>Es posible que no exista o no tengas permisos.</p>";
        }
    }
}

loadTournament();
setInterval(() => loadTournament(), 5000); // Auto-Refresh

// --- Edit/Delete Logic (Global) ---
function closeEditModal() {
        document.getElementById('modal-edit').classList.remove('active');
}

async function processImageFile(fileInput) {
    return null; // No file input anymore
}

let initialEditState = null;

function checkFloatingButton(prefix) {
    const btn = document.getElementById(prefix + '-floating-btn');
    if(!btn) return;

    const requiredIds = ['name', 'desc', 'date', 'start', 'reg-start', 'reg-end'];
    let allFilled = true;
    for(const id of requiredIds) {
        const el = document.getElementById(prefix + '-t-' + id);
        if(!el || !el.value.trim()) {
            allFilled = false;
            break;
        }
    }
    
    let show = false;
    // Only 'edit' supported effectively here as create is not in this file
    if (prefix === 'edit') {
        if (allFilled && initialEditState) {
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
    
    if(show) btn.classList.add('visible');
    else btn.classList.remove('visible');
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
    const maxM = maxInput ? maxInput.value : '1';
    const date = dateInput ? dateInput.value : 'YYYY-MM-DD';
    const start = startInput ? startInput.value : '00:00';
    const regStart = regStartInput ? regStartInput.value : '00:00';
    const regEnd = regEndInput ? regEndInput.value : '00:00';
    const imgUrl = imgInput ? imgInput.value : '';

    // Fallbacks for display
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
    
    // Status update
    let statusText = 'Abierto';
    let statusColor = '#3ba55c';
    
    // Use Editing Status if visible
    const statusGroup = document.getElementById('edit-t-status-group');
    const statusSelect = document.getElementById('edit-t-status');
        
    if (prefix === 'edit' && statusGroup && statusGroup.style.display !== 'none' && statusSelect) {
            const val = statusSelect.value;
            const map = { 'open': 'Abierto', 'pending': 'En Espera', 'active': 'En Curso', 'finished': 'Finalizado' };
            statusText = map[val] || val;
            if(val === 'open' || val === 'active') statusColor = '#3ba55c';
            else if(val === 'finished') statusColor = '#ed4245';
            else statusColor = '#6b7280';
    } else if (tourneyData) {
            const map = { 'open': 'Abierto', 'pending': 'En Espera', 'active': 'En Curso', 'finished': 'Finalizado' };
            statusText = map[tourneyData.status] || tourneyData.status;
            if(tourneyData.status === 'finished') statusColor = '#ed4245';
            else if(tourneyData.status === 'pending') statusColor = '#6b7280';
            else if(tourneyData.status === 'open' || tourneyData.status === 'active') statusColor = '#3ba55c'; // green
    }

    const previewContainer = document.getElementById(prefix + '-preview-bg').parentElement;
    const badge = previewContainer.querySelector('.badge');
    if(badge) {
        badge.textContent = statusText;
        badge.style.background = statusColor;
    }

    const bgDiv = document.getElementById(prefix + '-preview-bg');
    if (bgDiv) {
            const setFallback = () => {
                if (guildDataGlobal && guildDataGlobal.guild && guildDataGlobal.guild.icon) {
                    // guild.icon is already a full URL from backend
                    bgDiv.style.backgroundImage = `url('${guildDataGlobal.guild.icon}')`;
                } else {
                    bgDiv.style.backgroundImage = 'linear-gradient(to right, #5865f2, #ed4245)';
                }
            };

        if (imgUrl && imgUrl.trim() && imgUrl !== "null" && imgUrl !== "None" && imgUrl !== "undefined") {
            const img = new Image();
            img.onload = () => { bgDiv.style.backgroundImage = `url('${imgUrl}')`; };
            img.onerror = setFallback;
            img.src = imgUrl;
        } else {
            setFallback();
        }
    }
    
    checkFloatingButton(prefix);
    }

window.editTournament = function() {
        const t = tourneyData; // Global
        if(!t) return;
        
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
    
    // Status Logic
    const statusGroup = document.getElementById('edit-t-status-group');
    const statusSelect = document.getElementById('edit-t-status');
    
    // Always show status group in Edit Mode for flexibility, or keep dependent logic?
    // User requested adding label/dropdown. In server.html I made it always visible if logic allows.
    // Here currently existing logic was: if open/pending show it.
    // I'll update it to always show unless maybe finished?
    // "en el form de editar tienes que añadir un label para el estado".
    // I'll make it visible regardless of current status so user can change it (e.g. from Open to Active).
    if(statusGroup) {
        statusGroup.style.display = 'block';
        if(statusSelect) statusSelect.value = t.status;
    }
    
    // Store Initial State
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
    
    document.getElementById('modal-edit').classList.add('active');
    updatePreview('edit');
    checkFloatingButton('edit');
}

window.submitEditTournament = async function(e) {
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
    // const fileInput = document.getElementById('edit-t-img-file');

    /*
    try {
        const fileImg = await processImageFile(fileInput);
        if(fileImg) img = fileImg;
    } catch(err) { return alert(err.message); }
    */

    // If no image provided, use server icon as fallback
    if (!img || !img.trim() || img === "null" || img === "None" || img === "undefined") {
        if (guildDataGlobal && guildDataGlobal.guild && guildDataGlobal.guild.icon) {
        img = guildDataGlobal.guild.icon;
        }
    }
    
        try {
        const params = new URLSearchParams(window.location.search);
        const guildId = params.get('guild');

        // Read Status if visible
        let statusVal = null;
        const statusGroup = document.getElementById('edit-t-status-group');
        if (statusGroup.style.display !== 'none') {
            statusVal = document.getElementById('edit-t-status').value;
        }

        const payload = { 
            name: name, description: desc, max_teams: teams, 
            min_members: minM, max_members: maxM,
            date: date, reg_start: regStart, reg_end: regEnd, start_time: startTime,
            image_url: img
        };
        if(statusVal) payload.status = statusVal;

        const res = await fetch(`/api/guild/${guildId}/tournament/${id}/update`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        if(res.ok) {
            alert("Torneo actualizado!");
            loadTournament(true);
            closeEditModal();
        } else {
            const d = await res.json();
            alert("Error: " + d.error);
        }
    } catch(e) { alert("Error de conexión"); }
}

window.deleteTournament = async function() {
        if(!confirm("¿Eliminar torneo irreversiblemente?")) return;
        try {
            const params = new URLSearchParams(window.location.search);
            const guildId = params.get('guild');
            const tourneyId = params.get('tourney');
            
            const res = await fetch(`/api/guild/${guildId}/tournament/${tourneyId}/delete`, { method: 'POST' });
            if(res.ok) {
                window.location.href = `/server?id=${guildId}`;
            } else {
                alert("Error al eliminar");
            }
        } catch(e) { alert("Error de conexión"); }
}