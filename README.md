<div align="center">
  <div align="center">
    <img src="img/image.png" alt="Tourney Bot" width="80" style="vertical-align: middle; margin-right: 15px;"/>
    <h1 style="display: inline-block; vertical-align: middle; margin: 0;">Tourney Bot</h1>
  </div>

  <p align="center">
    <b>Bot de Discord avanzado para la gestión integral de torneos.</b><br>
    Sistema de brackets automáticos, gestión de equipos, canales privados por partida y dashboard web.
  </p>

  <p align="center">
    <img src="https://img.shields.io/badge/status-active-brightgreen?style=flat-square" alt="Status">
    <img src="https://img.shields.io/badge/made%20with-python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Made with Python">
    <img src="https://img.shields.io/badge/database-MongoDB-47A248?style=flat-square&logo=mongodb&logoColor=white" alt="MongoDB">
    <a href="http://tourneydoc.victormenjon.es"><img src="https://img.shields.io/badge/docs-tourneydoc.victormenjon.es-blue?style=flat-square&logo=read-the-docs&logoColor=white" alt="Documentation"></a>
  </p>
</div>

---

## ✨ Características Principales

<details>
<summary><b>🏆 Creación y Gestión de Torneos</b></summary>
<br>
Crea torneos totalmente personalizados definiendo nombre, descripción, fechas de inscripción y límites de participación. Gestiona el estado del torneo (apertura, cierre, inicio) con simples comandos.
<br><br>
<img src="img/torneoCreado.png" alt="Creación de Torneo" width="600"/>
</details>

<details>
<summary><b>👥 Sistema de Equipos y Liderazgo</b></summary>
<br>
Permite a los usuarios crear sus propios equipos, invitar a otros miembros y transferir el liderazgo. El bot valida automáticamente que los equipos cumplan con los requisitos de miembros mínimos y máximos.
<br><br>
<img src="img/teams.png" alt="Sistema de Equipos" width="600"/>
</details>

<details>
<summary><b>🖼️ Brackets Visuales Automáticos</b></summary>
<br>
Generación automática de imágenes de brackets que se actualizan ronda tras ronda. Visualiza el progreso del torneo de forma clara y atractiva directamente en Discord.
<br><br>
<img src="img/bracket.png" alt="Bracket Visual" width="600"/>
</details>

<details>
<summary><b>🔒 Canales de Partida Privados</b></summary>
<br>
Al iniciar un torneo, el bot crea automáticamente canales privados para cada enfrentamiento, otorgando permisos <b>exclusivamente</b> a los equipos involucrados y a los organizadores.
<br><br>
<img src="img/match.png" alt="Canales de Partida" width="600"/>
</details>

<details>
<summary><b>📜 Sistema de Logs Detallado</b></summary>
<br>
Mantén un control total con un canal de registros que notifica creación de equipos, uniones, eliminaciones, inicio de torneos y resultados de partidas.
<br><br>
<img src="img/logs.png" alt="Sistema de Logs" width="600"/>
</details>

<details>
<summary><b>🌐 Dashboard Web & API</b></summary>
<br>
Incluye un servidor web (FastAPI) para visualizar torneos activos, historial y documentación en una interfaz web moderna.
</details>

---

## 🛠️ Comandos de Usuario

Estos comandos están disponibles para todos los usuarios del servidor.

| Comando                                  | Descripción                                                                        |
| :--------------------------------------- | :--------------------------------------------------------------------------------- |
| `,tourney help`                          | Muestra la ayuda interactiva de comandos.                                          |
| `,tourney register <nombre> <@miembros>` | Crea un equipo y registra a los miembros mencionados (el líder se une auto).       |
| `,tourney invite <@usuario>`             | Invita a un usuario a unirse a tu equipo existente.                                |
| `,tourney leave`                         | Abandona tu equipo actual. Si eres líder, debes transferir el rol o ser el último. |
| `,tourney info [id_torneo]`              | Info detallada del torneo activo o de uno específico.                              |
| `,tourney teams [id_torneo]`             | Lista todos los equipos registrados en el torneo.                                  |
| `,tourney team <id_equipo>`              | Muestra detalles de un equipo (miembros, líder, estadísticas).                     |
| `,tourney historial`                     | Muestra una lista de los torneos finalizados anteriormente.                        |
| `,tourney link`                          | Proporciona el enlace de invitación para añadir el bot a otros servidores.         |
| `,tourney bug <descripción>`             | Reporta un error o problema directamente a los desarrolladores.                    |

---

## 👮 Comandos de Administración

Estos comandos requieren permisos de Administrador o un rol configurado como "Admin de Torneo".

### ⚙️ Gestión del Torneo

| Comando                          | Descripción                                                        |
| :------------------------------- | :----------------------------------------------------------------- |
| `,tourney create <args>`         | Crea un nuevo torneo (Ver formato abajo). Permite adjuntar imagen. |
| `,tourney open`                  | Abre las inscripciones (Estado: Pending ➜ Open).                   |
| `,tourney close`                 | Cierra las inscripciones (Estado: Open ➜ Pending).                 |
| `,tourney start [id_torneo]`     | Inicia el torneo, genera los enfrentamientos, brackets y canales.  |
| `,tourney delete <id_torneo>`    | Elimina un torneo de la base de datos permanentemente.             |
| `,tourney kick <equipo/user>`    | Expulsa a un equipo del torneo activo.                             |
| `,tourney set winner <@miembro>` | Define manualmente el ganador de un enfrentamiento actual.         |

**Formato de Creación:**

```
,tourney create Nombre | Descripción | Fecha (YYYY-MM-DD) | InicioInsc (HH:MM) | FinInsc (HH:MM) | InicioTorneo (HH:MM) | MaxEquipos | MinMiembros | MaxMiembros
```

### 🔧 Configuración del Servidor

| Comando                         | Descripción                                                  |
| :------------------------------ | :----------------------------------------------------------- |
| `,tourney settings`             | Muestra la configuración actual del servidor.                |
| `,tourney set category <id>`    | Define la categoría donde se crearán los canales de partida. |
| `,tourney set lobby <id>`       | Canal para avisos de registro y lobby.                       |
| `,tourney set bracket <id>`     | Canal donde se publicarán las imágenes de los brackets.      |
| `,tourney set logs [id]`        | Activa/Desactiva logs. Si se da ID, configura el canal.      |
| `,tourney set prefix <prefijo>` | Cambia el prefijo del bot para este servidor.                |
| `,tourney roles add <@rol>`     | Añade un rol permitido para administrar torneos.             |
| `,tourney roles remove <@rol>`  | Elimina un rol de la lista de permitidos.                    |

---

## 📝 Logs de Eventos

Color code para los logs del sistema (`tourney set logs`):

| Evento                 | Color      | Significado                                            |
| :--------------------- | :--------- | :----------------------------------------------------- |
| 🏆 Torneo Creado       | 🟢 Verde   | Se ha programado un nuevo torneo.                      |
| 🚀 Torneo Iniciado     | 🟢 Verde   | El torneo ha comenzado y los brackets están generados. |
| 🔓 Inscripción Abierta | 🟢 Verde   | Los usuarios pueden empezar a registrarse.             |
| 🔒 Inscripción Cerrada | 🟠 Naranja | Ya no se admiten nuevos equipos.                       |
| 🗑️ Eliminación         | 🟠 Naranja | Se ha eliminado un equipo o un torneo.                 |
| 📊 Resumen Ronda       | 🟣 Morado  | Resultado al finalizar una ronda.                      |

---

## 🚀 Instalación y Despliegue

### Requisitos Previos

- Python 3.10 o superior
- MongoDB (URI de conexión)
- Cuenta de Discord y Token de Bot

### Pasos

1. **Clonar el repositorio**

   ```bash
   git clone https://github.com/tu-usuario/tourney-bot.git
   cd tourney-bot
   ```

2. **Instalar dependencias**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar variables de entorno**
   Crea un archivo `.env` en la raíz del proyecto basándote en el siguiente ejemplo:

   ```env
   # Discord Credenciales
   DISCORD_BOT_TOKEN=tu_token_aqui
   BOT_PREFIX=,

   # Base de Datos (MongoDB)
   URL_BASE_1=mongodb+srv://usuario:password@cluster.mongodb.net/

   # IDs de Canales Globales (Opcional, para desarrollo)
   ERROR_CHANNEL_ID=123456789
   bug_channel_id=123456789

   # Web Server (Opcional)
   DOC_URL=http://localhost:8000
   ```

4. **Ejecutar el bot**
   ```bash
   python main.py
   ```

---

## 📂 Estructura del Proyecto

```
Tourney/
├── main.py           # Punto de entrada (Bot + Web Server)
├── server.py         # Servidor FastAPI y Dashboard
├── config.py         # Gestor de configuración y entorno
├── .env              # Variables de entorno (no subir al repo)
├── requirements.txt  # Dependencias del proyecto
├── cogs/             # Módulos del bot (Comandos)
│   └── tourney.py    # Lógica principal del torneo
├── utils/            # Utilidades
│   ├── db.py         # Conexión y métodos de base de datos
│   └── visual.py     # Motor de generación de imágenes (Brackets)
└── docLA/            # Frontend de documentación
```

---

<div align="center">
  
## 👨‍💻 Autor

**Victor Menjon**

[![Website](https://img.shields.io/badge/Website-victormenjon.es-blue?style=flat&logo=google-chrome)](https://victormenjon.es)
[![GitHub](https://img.shields.io/badge/GitHub-@Vimen1803-181717?style=flat&logo=github)](https://github.com/vimen1803)
[![Email](https://img.shields.io/badge/Email-victormnjfan@gmail.com-red?style=flat&logo=gmail)](mailto:victormnjfan@gmail.com)

---

Desarrollado con ❤️ para facilitar la gestión de torneos en comunidades de Discord.

_v1.5.0 | Febrero 2026_

</div>
