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

fetchStats();

// Mobile menu
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
mobileMenuBtn?.addEventListener('click', () => {
    alert('Menú móvil - Implementa tu lógica aquí');
});