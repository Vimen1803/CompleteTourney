// Navbar scroll effect
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
});

// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Scroll animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, observerOptions);

document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));

// Animated particles
function createParticles() {
    const container = document.getElementById('particles');
    const particleCount = 30;
    
    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.animationDuration = (Math.random() * 20 + 10) + 's';
        particle.style.animationDelay = Math.random() * 5 + 's';
        container.appendChild(particle);
    }
}
createParticles();

// Fetch Stats
async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        if (data.guilds !== undefined) {
            animateCounter('server-count', data.guilds);
        }
        if (data.tournaments !== undefined) {
            animateCounter('match-count', data.tournaments);
        }
    } catch (error) {
        console.error('Error fetching stats:', error);
    }
}

// Animated counter
function animateCounter(id, target) {
    const element = document.getElementById(id);
    const duration = 1000;
    const start = 0;
    const increment = target / (duration / 16);
    let current = start;

    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target + '+';
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current) + '+';
        }
    }, 16);
}

// Initial fetch
fetchStats();
fetchUserStatus();

// Fetch user status
async function fetchUserStatus() {
    try {
        const response = await fetch('/api/user');
        if (response.ok) {
            const data = await response.json();
            if (data && data.id) {
                const navActions = document.getElementById('nav-actions');
                if (navActions) {
                    navActions.innerHTML = `
                        <a href="/dashboard" class="cta-btn" style="background-color: var(--card-bg); border: 1px solid var(--border); color: var(--text-header);">
                            <i class="fas fa-server" style="margin-right: 8px"></i>
                            Dashboard
                        </a>
                        <a href="/logout" class="cta-btn" style="background-color: #ed4245;">
                            <i class="fas fa-sign-out-alt" style="margin-right: 8px"></i>
                            Cerrar Sesión
                        </a>
                        <button class="mobile-menu-btn" id="mobileMenuBtn">
                          <i class="fas fa-bars"></i>
                        </button>
                    `;
                }
            }
        }
    } catch(e) {
        console.error("Error fetching user status", e);
    }
}

// Mobile menu (básico)
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
mobileMenuBtn?.addEventListener('click', () => {
    alert('Menú móvil - Implementa tu lógica aquí');
});