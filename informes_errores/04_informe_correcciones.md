# Informe de Correcciones Aplicadas

> Fecha: 2026-06-11
> Alcance: correcciones sobre los errores documentados en `01_errores_web.md`, `02_errores_bot.md` y `03_errores_ambos.md`.
> Verificación: `python -m py_compile` de todos los módulos → **OK**; `node --check` de todos los `.js` → **OK**.

Para cada error se indica: **ID**, archivos tocados, **qué se hizo** y **por qué**.

---

## BOT

### B-01 · `aiohttp` no importado → imágenes de bracket nunca cargaban · **CORREGIDO**
- **Archivo:** `cogs/tourney.py`
- **Cambio:** Añadido `import aiohttp` en la cabecera del módulo.
- **Por qué:** Las funciones `fetch_image` de `process_round` y `advance_round` usaban `aiohttp.ClientSession()`; al no estar importado, lanzaban `NameError` silenciado por un `except:` mudo, de modo que el icono del servidor y la imagen del torneo nunca se descargaban. Con el import, las imágenes ya se incrustan correctamente en el pie del bracket.

### B-02 · `init_bot_stats(1)` reseteaba servidores a 1 · **CORREGIDO**
- **Archivo:** `main.py`
- **Cambio:** `await DBManager.init_bot_stats(len(bot.guilds))` en lugar del literal `1`.
- **Por qué:** En cada arranque el contador `serversOn` se fijaba a 1 sin reflejar el número real de servidores. Ahora usa el conteo real de guilds del bot.

### B-03 · Estado final `"Terminado"` en vez de `"finished"` · **CORREGIDO**
- **Archivo:** `cogs/tourney.py` (`advance_round`, rama de final por BYE)
- **Cambio:** `update_tournament(..., {"status": "finished"})` en lugar de `"Terminado"`.
- **Por qué:** Unifica el valor de estado con el resto del sistema y con el `statusMap` del frontend, evitando que la web muestre un estado no reconocido.

### B-04 · Sin categoría → no se crean canales de partido (sin aviso) · **CORREGIDO**
- **Archivo:** `cogs/tourney.py` (`start_tourney`)
- **Cambio:** Antes de generar los partidos, si no hay `category_id` configurada se envía un **embed de aviso** indicando que no se crearán canales de enfrentamiento y cómo configurarla (`,tourney set category <id>`). No bloquea el inicio.
- **Por qué:** Antes el torneo arrancaba en un estado inutilizable (sin salas) sin ninguna explicación. Ahora el organizador es advertido.

### B-05 · `count_tournaments` duplicado · **CORREGIDO**
- **Archivo:** `utils/db.py`
- **Cambio:** Eliminada la segunda definición idéntica.
- **Por qué:** Código muerto que confundía y podía divergir.

### B-06 · Comprobación de `tzinfo` invertida/inútil · **CORREGIDO**
- **Archivos:** `cogs/tourney.py` (`ping`), `server.py` (`perform_health_check`)
- **Cambio:** `if last_seen.tzinfo is not None: last_seen = last_seen.replace(tzinfo=None)` (antes comparaba `is None`, que era un no-op).
- **Por qué:** Ahora normaliza correctamente timestamps *aware* a naïve-UTC antes de compararlos con `utcnow()`.

### B-09 · `config.py` reventaba el arranque con `.env` incompleto · **CORREGIDO**
- **Archivo:** `config.py`
- **Cambio:** Nueva función `_int_env(name, default=0)` que lee enteros de entorno tolerando ausencia/valor inválido y avisa por consola. Aplicada a `ERROR_CHANNEL`, `LOG_CHANNEL`, `BUG_CHANNEL`, `SERVER_LOG_CHANNEL`, `SUGGESTION_CHANNEL` y `OWNER`.
- **Por qué:** Antes `int(os.getenv(...))` lanzaba `TypeError` en import si faltaba una variable, sin indicar cuál. Ahora el arranque es robusto y el mensaje claro.

---

## WEB

### W-01 · Endpoints de API sin verificación de permisos · **CORREGIDO** (Crítico)
- **Archivo:** `server.py`
- **Cambio:** Nuevo helper reutilizable `async def user_can_manage(guild_id, request)` (admin OAuth o rol de organizador). Aplicado con respuesta `403` en:
  - `create_tournament`
  - `delete_tournament`
  - `get_blacklist_api`
  - `add_blacklist_api`
  - `remove_blacklist_api`
- **Por qué:** Estas rutas solo validaban sesión, permitiendo a cualquier usuario autenticado crear/borrar torneos y manipular la blacklist de servidores ajenos (Broken Access Control / IDOR). Ahora exigen permiso de gestión, igual que `update_config`/`update_tournament`.

### W-02 · Doble barra `//` en URLs SSR · **CORREGIDO**
- **Archivo:** `server.py`
- **Cambio:** Añadida constante `DOC_URL_BASE = (DOC_URL or "").rstrip("/")` y usada en las construcciones de URL SSR de `serve_server`/`serve_tournament`.
- **Por qué:** `DOC_URL` termina en `/`; concatenar `/server` producía `//server`. Ahora las URLs canónicas quedan bien formadas.

### W-03 · SSR de torneo no rellenaba metadatos (param `id`) · **CORREGIDO**
- **Archivo:** `server.py` (`serve_tournament`)
- **Cambio:** La ruta ahora acepta `tourney`, `guild` (y `id` como alternativa). Usa `tourney_id = tourney or id` para buscar el torneo y construye la URL canónica con `?guild=...&tourney=...`.
- **Por qué:** Los enlaces reales (bot y frontend) usan `?guild=&tourney=`, por lo que el SSR con `id` nunca se ejecutaba. `serve_server` también acepta ahora `?id=` (que es lo que usa el frontend).

### W-04 · Placeholders `${DOC_URL}` sin sustituir en HTML · **CORREGIDO**
- **Archivos:** `server.py`
- **Cambio:** Nuevo helper `render_html(path)` que lee el HTML y reemplaza `${DOC_URL}` por `DOC_URL_BASE`. Aplicado a `serve_home`, `serve_docs`, `serve_dashboard`, `status_page`, y a `serve_server`/`serve_tournament` (sustitución final de los `${DOC_URL}` restantes).
- **Por qué:** Las meta-tags Open Graph/Twitter contenían el literal `${DOC_URL}`, rompiendo previsualizaciones de enlace en redes/Discord. Ahora se sustituyen al servir.

### W-05 · Fechas de health en zona horaria incorrecta · **CORREGIDO**
- **Archivo:** `docLA/js/health.js`
- **Cambio:** Nueva función `parseUTC(ts)` que añade el sufijo `Z` si el timestamp ISO no trae zona, y se usa en lugar de `new Date(item.timestamp)`.
- **Por qué:** Los timestamps UTC sin `Z` se interpretaban como hora local, desplazando las horas del histórico el offset del visitante.

### W-06 · Código muerto + `ReferenceError` en `dashboard.js` · **CORREGIDO (parcial)**
- **Archivo:** `docLA/js/dashboard.js`
- **Cambio:** Sustituido el `g` indefinido por `data.guild` (eliminando el `ReferenceError`) y corregido el enlace relativo `tournament.html?...` → `/tournament?...`.
- **Por qué:** Evita errores latentes si esa vista se reactiva. **Nota:** la función `loadServerDetail` de `dashboard.js` sigue siendo código obsoleto (el flujo real usa la página `/server`); se recomienda eliminarla en el futuro (ver "Pendientes").

### W-07 · Fuga de configuración a miembros sin permiso · **CORREGIDO**
- **Archivo:** `server.py` (`get_guild_details`)
- **Cambio:** `config_safe` solo se construye/devuelve `if config and can_manage`.
- **Por qué:** Antes se exponían IDs de canales/roles/prefijo a cualquier miembro. Ahora se alinea con la ruta `/public` (config solo para gestores).

### W-08 · Posible `500` al actualizar torneo inexistente · **CORREGIDO**
- **Archivo:** `server.py` (`update_tournament`)
- **Cambio:** Si `get_tournament` devuelve `None`, se responde `404` en lugar de continuar (evita `AttributeError`).
- **Por qué:** Manejo limpio de IDs inválidos.

### W-09 · Línea muerta en `saveConfig` (server.js) · **CORREGIDO**
- **Archivo:** `docLA/js/server.js`
- **Cambio:** Eliminadas las líneas `const rolesStr = ...; const roles = rolesStr` sin uso.
- **Por qué:** Limpieza de deuda técnica (el `payload` ya calcula `admin_roles` inline).

---

## AMBOS

### A-01 · XSS almacenado (datos sin escapar) · **CORREGIDO** (Crítico)
- **Archivos:** `docLA/js/layout.js`, `server.js`, `tournament.js`, `dashboard.js`
- **Cambio:** Añadida función global `escapeHtml()` en `layout.js` (cargada en todas las páginas de panel). Aplicada a todos los campos controlados por usuario que se inyectan con `innerHTML`:
  - Nombres y descripciones de torneos, `winner_name`.
  - Nombres de equipos y de miembros.
  - Nombre del servidor, nombres de roles.
  - Blacklist: `user_name`, `user_id`, `reason`, `date`.
  - URLs de imagen de avatar/icono envueltas con `encodeURI()`.
- **Por qué:** Nombres/descripciones (introducidos desde el bot o la web) se renderizaban como HTML, permitiendo XSS almacenado (p. ej. `<img src=x onerror=...>`). Ahora se escapan antes de inyectarse.

### A-02 · Convención de barra final de `DOC_URL` incoherente · **CORREGIDO** (lado web)
- **Archivo:** `server.py`
- **Cambio:** Centralizada la normalización con `DOC_URL_BASE = DOC_URL.rstrip("/")`, y todas las URLs SSR se construyen sobre esa base.
- **Por qué:** El bot ya generaba URLs correctas asumiendo barra final; la web asumía lo contrario. Normalizando en la web, ambos lados son coherentes con el valor actual de `.env` y resistentes a que se añada/quite la barra. (El bot ya funcionaba; no requería cambio.)

### A-03 · Contador `tournamentsDone`/`serversOn` podía ser negativo · **CORREGIDO (mitigado)**
- **Archivo:** `utils/db.py` (`get_bot_stats`)
- **Cambio:** Al leer las estadísticas, los valores negativos se normalizan a `0`.
- **Por qué:** Los `$inc: -1` al borrar torneos/servidores podían dejar el contador por debajo de 0. Se evita mostrar negativos en la web. (La semántica de "total acumulado" vs "vivos" se deja como decisión de producto; ver "Pendientes".)

### A-04 · Campo `tourney_logs` vs `tourney_logs_enabled` · **CORREGIDO**
- **Archivo:** `utils/db.py` (dataclass `GuildConfig`)
- **Cambio:** El campo del modelo pasa a llamarse `tourney_logs_enabled` (con default `False`), alineado con lo que bot y web leen/escriben realmente. Las líneas de compatibilidad de `server.py` (`config.get('tourney_logs', False)`) se mantienen para no romper documentos antiguos.
- **Por qué:** El modelo declaraba un campo que nunca se usaba para lectura; las nuevas configuraciones ahora se crean con la clave correcta y los logs se activan de forma consistente.

### A-06 · Validaciones divergentes bot↔web al crear torneos · **CORREGIDO (parcial)**
- **Archivo:** `server.py` (`create_tournament`)
- **Cambio:** Añadida validación equivalente a la del bot: `max_teams` múltiplo de 2 y en rango 2-64; `min_members`/`max_members` enteros válidos con `min <= max`. Respuestas `400` con mensaje claro.
- **Por qué:** Antes la web aceptaba valores (p. ej. `max_teams` impar) que rompían el *seeding* de `start_tourney`. Ahora ambos canales aplican las mismas reglas mínimas. (La validación estricta de formato de fecha/hora se deja como mejora pendiente.)

---

## Segunda tanda de correcciones (a petición del usuario)

### W-10 · Dominios inconsistentes → unificado a Vercel · **CORREGIDO**
- **Archivos:** `docLA/sitemap.xml`, `docLA/robots.txt`
- **Cambio:** Todas las URLs pasan a `https://complete-tourney.vercel.app` (dominio definitivo indicado por el usuario), coherente con `DOC_URL`/`REDIRECT_URI`.
- **Por qué:** Evita sitemaps/canónicas apuntando a un dominio distinto del operativo.

### W-11 · Estado del bot en tiempo real (sin widget hardcodeado) · **CORREGIDO**
- **Archivos:** `server.py` (nuevo endpoint `GET /api/bot/live`), `docLA/js/dashboard.js`
- **Cambio:** Nuevo endpoint que calcula online/offline a partir del **heartbeat real** (latido cada 30s, margen 45s). `dashboard.js` consume `/api/bot/live` en vez del widget de Discord, eliminando `HOME_SERVER_ID` y el nombre `'LA TourneyBot'` hardcodeados.
- **Por qué:** El estado ya no depende de que el widget del servidor esté activado ni de un nombre fijo; refleja el estado real del proceso del bot.

### A-05 · Reportes instantáneos · **CORREGIDO**
- **Archivos:** `cogs/reports.py`, `cogs/tourney.py`, `config.py`
- **Cambio:**
  - El loop de entrega pasa de **60 min** a **15 s** (`@tasks.loop(seconds=15)`), para los reportes creados desde la **web**.
  - Los reportes creados desde el **bot** (`,tourney bug`/`,tourney suggest`) se entregan **al instante**: tras guardarlos, se invoca `Reports.deliver_reports()` directamente.
- **Por qué:** Antes un reporte podía tardar hasta una hora en aparecer en el canal de soporte. Ahora es inmediato (bot) o casi inmediato ≤15s (web). *(Web y bot son procesos separados que comparten MongoDB; por eso la web no puede entregar directamente y se apoya en el loop corto.)*

### A-07 · `datetime.utcnow()` deprecado → datetimes *aware* UTC · **CORREGIDO**
- **Archivos:** `utils/db.py`, `server.py`, `cogs/tourney.py`, `cogs/reports.py`
- **Cambio:**
  - Cliente Mongo con `tz_aware=True` (los datetimes leídos vuelven como *aware* UTC).
  - Helpers `utcnow()` (en `db.py` y `server.py`) que devuelven `datetime.now(timezone.utc)`; sustituidas todas las llamadas a `datetime.utcnow()`.
  - Normalización de `last_seen` actualizada para asegurar *aware*-UTC en las comparaciones (`ping`, health, `/api/bot/live`).
- **Por qué:** `utcnow()` está deprecado en Python 3.12+. Además, al serializar con `.isoformat()` ahora se incluye el offset `+00:00`, lo que **refuerza W-05** (el frontend interpreta las horas como UTC sin ambigüedad).

### B-07 · Registro de excepciones silenciosas · **CORREGIDO (puntos clave)**
- **Archivos:** `main.py`, `utils/api.py`, `cogs/admin.py`, `cogs/tourney.py`
- **Cambio:** Sustituidos los `except:` mudos que ocultaban fallos diagnósticos por `except Exception as e:` con `print` descriptivo en: listado de invitaciones (`main.py`), `get_bot_guilds` (`api.py`), creación de invitación (`admin.py`), descarga de imágenes de bracket (`fetch_image`) y envío de logs (`send_log`).
- **Por qué:** Estos `except` mudos eran los que enmascaraban errores como B-01. Ahora cualquier fallo deja traza en consola. *(Los `except` de "mejor esfuerzo" puramente esperados —p. ej. parseo de menciones o fuentes no instaladas— se mantienen por ser ruido innecesario.)*

### A-08 · Límites de longitud de entrada · **CORREGIDO**
- **Archivos:** `cogs/tourney.py` (constantes `MAX_TOURNEY_NAME_LEN=100`, `MAX_TOURNEY_DESC_LEN=1000`, `MAX_TEAM_NAME_LEN=50`), `server.py`, `docLA/server.html`, `docLA/tournament.html`
- **Cambio:** Validación de longitud de nombre/descripción de torneo y nombre de equipo, tanto en el **bot** (`create_tourney`, `register_team`) como en la **web** (`create_tournament`, `update_tournament`, importando las constantes del bot). Añadido `maxlength` en los formularios HTML para feedback inmediato.
- **Por qué:** Textos demasiado largos (introducidos desde la web) podían romper el renderizado de embeds en Discord. Ahora ambos canales comparten los mismos límites.

### dashboard.js · Vista `loadServerDetail` obsoleta eliminada · **CORREGIDO**
- **Archivos:** `docLA/js/dashboard.js`, `docLA/dashboard.html`
- **Cambio:** `dashboard.js` reescrito para gestionar **solo** la lista de servidores (la navegación va a `/server`). Eliminadas `loadServerDetail`, `editTournament`, `submitEditTournament`, `deleteTournament`, `createTournament`, `saveConfig`, `fillSelect`, `switchTab`, modales, etc. En `dashboard.html` se eliminó la vista de detalle y los modales de crear/editar (ahora exclusivos de la página `/server`).
- **Por qué:** Era código muerto y duplicado (con el bug del `g` indefinido) que ya estaba sustituido por la página `/server`. La página de dashboard queda limpia y mantenible.

---

## Pendientes restantes (bajo impacto)

| Ref | Motivo de no aplicarse |
|-----|------------------------|
| **B-08** Heartbeat puede registrar NaN al arrancar | Mitigado por `wait_until_ready`; riesgo muy bajo. No se ha tocado para no añadir complejidad innecesaria. |
| **B-07** (resto de `except` de "mejor esfuerzo") | Los `except` puramente esperados (parseo de IDs/menciones, carga de fuentes alternativas en `visual.py`) se mantienen silenciosos a propósito para no generar ruido en consola. |

---

## Verificación realizada
- `python -m py_compile main.py config.py server.py utils/db.py utils/api.py utils/visual.py cogs/*.py` → **sin errores** (tras ambas tandas).
- `python -c "import server"` → **importa correctamente**; `DOC_URL_BASE = https://complete-tourney.vercel.app` (sin barra final) y constantes de límite resueltas.
- `node --check` sobre `layout.js, server.js, tournament.js, dashboard.js, health.js, index.js, doc.js` → **sin errores de sintaxis**.
- Búsqueda de referencias colgantes a `tourney_logs` tras el renombrado → solo quedan las líneas de **compatibilidad intencionadas** en `server.py`.
- Búsqueda de `datetime.utcnow()` → ya no quedan usos (sustituidos por helpers *aware*).

> Nota: no se han ejecutado el bot ni el servidor contra Discord/MongoDB reales (requeriría credenciales y servicios en vivo). Las correcciones se han validado por compilación/importación/sintaxis y análisis estático.
