// DOM Elements
const categoryList = document.getElementById('category-list');
const commandsContainer = document.getElementById('commands-container');
const searchInput = document.getElementById('search-input');
const menuToggle = document.getElementById('menu-toggle');
const sidebar = document.getElementById('sidebar');

// Modal Elements
const modalOverlay = document.getElementById('command-modal');
const modalCloseBtn = document.getElementById('modal-close');
const modalBody = document.getElementById('modal-body');

// State
let commandData = {};
let activeCategory = 'Todos';

async function init() {
    try {
        const response = await fetch('data/commands.json?t=' + Date.now());
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        commandData = await response.json();
        
        renderCategories();
        renderCommands('Todos'); // Render all by default or first category
        setupEventListeners();
    } catch (e) {
        console.error("Could not load commands.json", e);
        commandsContainer.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--danger);">Error cargando comandos. Si estás en local, usa un servidor local (VS Code Live Server) o deshabilita CORS.</div>';
    }
}

function renderCategories() {
    // Calculate total commands
    let totalCommands = 0;
    Object.values(commandData).forEach(cmds => totalCommands += cmds.length);

    // Add 'Todos' first
    const allItem = document.createElement('li');
    allItem.className = 'category-item active';
    allItem.dataset.category = 'Todos';
    allItem.innerHTML = `<span>Todos</span> <span class="count">${totalCommands}</span>`;
    categoryList.appendChild(allItem);

    // Add specific categories, preserving JSON order (which is sorted by python script)
    const categories = Object.keys(commandData);
    
    for (const category of categories) {
        const cmds = commandData[category];
        if (category === 'Otros' && cmds.length === 0) continue; 

        const li = document.createElement('li');
        li.className = 'category-item';
        li.dataset.category = category;
        li.innerHTML = `<span>${category}</span> <span class="count">${cmds.length}</span>`;
        categoryList.appendChild(li);
    }
}

function renderCommands(category, filterText = '') {
    commandsContainer.innerHTML = ''; // Clear current
    let cmdsToRender = [];

    if (category === 'Todos') {
        // Flatten all commands if 'Todos'
        for (const [cat, cmds] of Object.entries(commandData)) {
            cmds.forEach(cmd => {
                // Add category property for display
                cmd._category = cat; 
                cmdsToRender.push(cmd);
            });
        }
    } else {
        if (commandData[category]) {
             cmdsToRender = commandData[category].map(cmd => ({...cmd, _category: category}));
        }
    }

    // Filter by search text
    if (filterText) {
        const lowerFilter = filterText.toLowerCase();
        cmdsToRender = cmdsToRender.filter(cmd => 
            cmd.name.toLowerCase().includes(lowerFilter) || 
            (cmd.aliases && cmd.aliases.some(a => a.toLowerCase().includes(lowerFilter))) ||
            (cmd.desc && cmd.desc.toLowerCase().includes(lowerFilter))
        );
    }

    if (cmdsToRender.length === 0) {
        commandsContainer.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px;">No se encontraron comandos.</div>';
        return;
    }

    cmdsToRender.forEach(cmd => {
        const card = document.createElement('div');
        card.className = 'command-card';
        card.onclick = () => openModal(cmd);
        
        const aliasHtml = cmd.aliases && cmd.aliases.length > 0 
            ? `<span class="usage-example" style="font-size:0.7em; margin-left: 5px;">,${cmd.aliases[0]}</span>` 
            : '';

        card.innerHTML = `
            <div class="card-header">
                <div>
                    <span class="cmd-name">,${cmd.name}</span>
                    ${aliasHtml}
                </div>
                <span class="cmd-category-badge">${cmd._category}</span>
            </div>
            <div class="cmd-desc">${cmd.desc || 'Sin descripción'}</div>
            <div class="cmd-footer">
                <span class="usage-example">${cmd.usage || ',' + cmd.name}</span>
            </div>
        `;
        commandsContainer.appendChild(card);
    });
}

function openModal(cmd) {
    let subcommandsHtml = '';
    
    if (cmd.subcommands && cmd.subcommands.length > 0) {
        const subList = cmd.subcommands.map(sub => `
            <li class="subcommand-item">
                <div class="sub-name">,${cmd.name} ${sub.name}</div>
                <div class="sub-desc">${sub.desc || 'Sin descripción'}</div>
                <div style="margin-top:4px; font-size: 0.8em; color: var(--text-muted);">
                   Uso: <code style="background:rgba(0,0,0,0.3); padding:2px 4px; border-radius:3px;">${sub.usage || ',' + cmd.name + ' ' + sub.name}</code>
                </div>
            </li>
        `).join('');
        
        subcommandsHtml = `
            <div class="modal-section">
                <h3>Subcomandos</h3>
                <ul class="subcommand-list">
                    ${subList}
                </ul>
            </div>
        `;
    }

    const aliasesHtml = cmd.aliases && cmd.aliases.length > 0
        ? `<div style="margin-bottom: 16px; color: var(--text-muted); font-size: 0.9rem;">
             <strong>Aliases:</strong> ${cmd.aliases.map(a => `<code style="background:rgba(0,0,0,0.3); padding:2px 4px; border-radius:3px;">,${a}</code>`).join(', ')}
           </div>`
        : '';

    modalBody.innerHTML = `
        <div class="modal-title">,${cmd.name}</div>
        <div class="modal-subtitle">${cmd._category || 'Comando'}</div>
        
        ${aliasesHtml}

        <div class="modal-section">
            <h3>Descripción</h3>
            <p style="white-space: pre-wrap; line-height: 1.5;">${cmd.desc || 'Sin descripción disponible.'}</p>
        </div>

        <div class="modal-section">
            <h3>Uso</h3>
            <code style="display:block; background: var(--bg-tertiary); padding: 12px; border-radius: 4px; font-family: monospace; color: var(--success);">
                ${cmd.usage || ',' + cmd.name}
            </code>
        </div>

        ${subcommandsHtml}
    `;

    modalOverlay.classList.add('active');
    document.body.style.overflow = 'hidden'; // Prevent background scrolling
}

function closeModal() {
    modalOverlay.classList.remove('active');
    document.body.style.overflow = '';
}

function setupEventListeners() {
    // Category switching
    categoryList.addEventListener('click', (e) => {
        const item = e.target.closest('.category-item');
        if (!item) return;

        // Update UI
        document.querySelectorAll('.category-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        
        activeCategory = item.dataset.category;
        renderCommands(activeCategory, searchInput.value);

        // On mobile, close sidebar after selection
        if (window.innerWidth <= 768) {
            sidebar.classList.remove('open');
        }
    });

    // Search
    searchInput.addEventListener('input', (e) => {
        renderCommands(activeCategory, e.target.value);
    });

    // Mobile Menu
    menuToggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768 && 
            sidebar.classList.contains('open') && 
            !sidebar.contains(e.target) && 
            !menuToggle.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    });

    // Modal Events
    modalCloseBtn.addEventListener('click', closeModal);
    modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) {
            closeModal();
        }
    });
    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modalOverlay.classList.contains('active')) {
            closeModal();
        }
    });
}



// Start
init();
