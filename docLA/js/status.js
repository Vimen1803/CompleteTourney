// !!! IMPORTANTE: REEMPLAZA ESTE ID POR EL DE TU SERVIDOR (Ajustes Servidor -> Widget -> ID del servidor)
const SERVER_ID = '1448450320639197211';

async function checkBotStatus() {
    const statusDots = document.querySelectorAll('.status-dot');
    const statusTexts = document.querySelectorAll('.status-text');
    
    if (statusDots.length === 0) return;

    try {
        // Fetch Discord Widget Data
        // IMPORTANT: The server must have "Server Widget" enabled in Server Settings > Widget
        const response = await fetch(`https://discord.com/api/guilds/${SERVER_ID}/widget.json`);
        
        if (!response.ok) {
            if (response.status === 403) {
                 console.warn('Widget disabled for this server. Enable it in Server Settings > Widget.');
            }
            throw new Error('Widget API Error');
        }
        
        const data = await response.json();
        console.log('Discord Widget Data:', data); // Debug log to see full response
        
        const botMember = data.members.find(member => member.username === 'LA TourneyBot');
        
        if (botMember) {
            console.log('Bot found:', botMember);
            
            statusDots.forEach(dot => {
                dot.style.backgroundColor = '#4ade80'; 
                dot.style.boxShadow = '0 0 8px rgba(74, 222, 128, 0.4)';
            });
            
            statusTexts.forEach(text => {
                text.textContent = 'Activo';
                text.parentElement.title = `Bot: ${botMember.username}\nEstado: ${botMember.status}\nServer: ${data.name}`;
            });

        } else {
             console.warn('Bot not found in widget members list. Members found:', data.members.length);
             
             statusDots.forEach(dot => {
                dot.style.backgroundColor = '#ef4444'; 
                dot.style.boxShadow = '0 0 8px rgba(239, 68, 68, 0.4)';
             });
             
             statusTexts.forEach(text => {
                text.textContent = 'Desconectado';
                text.parentElement.title = 'El bot no aparece en el Widget del servidor. Asegúrate de que el bot está ON y el Widget habilitado.';
             });
        }
    } catch (e) {
        console.error('Status check failed:', e);
        
        let errorMsg = 'Error Conexión';
        let errorTitle = 'Error conectando con la API de Discord.';
        
        if (e.message.includes('Widget API Error')) {
            errorMsg = 'Error Widget';
            errorTitle = 'El widget del servidor está deshabilitado o el ID es incorrecto.';
        }
        
        statusDots.forEach(dot => {
            dot.style.backgroundColor = '#ef4444'; 
            dot.style.boxShadow = 'none';
        });
        
        statusTexts.forEach(text => {
            text.textContent = errorMsg;
            text.style.color = 'var(--text-muted)';
            text.parentElement.title = `${errorTitle}\nDetalle: ${e.message}`;
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    checkBotStatus();
    // Check every 60 seconds
    setInterval(checkBotStatus, 60000);
});
