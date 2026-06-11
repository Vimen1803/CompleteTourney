# Informe de Errores — WEB (soporte web / FastAPI + Frontend)

> Ámbito: `server.py`, `utils/api.py` (uso desde la web) y `docLA/` (HTML, CSS, JS).
> Fecha del informe: 2026-06-11
> Estado: **solo diagnóstico** (sin correcciones aplicadas en esta fase).

## Escala de gravedad
- **Crítica**: compromete seguridad/datos o rompe una funcionalidad central.
- **Alta**: comportamiento incorrecto visible o riesgo serio, con workaround difícil.
- **Media**: fallo funcional acotado o degradación notable.
- **Baja**: code smell, cosmética, deuda técnica o caso borde poco probable.

---

## W-01 · Endpoints de API sin verificación de permisos · **Crítica**
**Archivo:** `server.py`
**Rutas afectadas:**
- `POST /api/guild/{guild_id}/tournaments/create` (línea ~807)
- `POST /api/guild/{guild_id}/tournament/{tournament_id}/delete` (línea ~1075)
- `GET  /api/guild/{guild_id}/blacklist` (línea ~1129)
- `POST /api/guild/{guild_id}/blacklist/add` (línea ~1154)
- `POST /api/guild/{guild_id}/blacklist/remove` (línea ~1175)

**Descripción:** Estas rutas solo comprueban que exista sesión (`request.session.get("user")`), pero **no verifican `can_manage`** (admin del servidor o rol de organizador), a diferencia de `update_config`, `update_tournament` o `delete_team_api`, que sí lo hacen. El propio código lo admite con un comentario en `add_blacklist_api`: *"assuming user has permissions if they reach this"*.

**Impacto:** Cualquier usuario autenticado (aunque no pertenezca al servidor) puede, conociendo un `guild_id`:
- Crear torneos en servidores ajenos.
- Borrar torneos ajenos (acción irreversible que además ejecuta `decrement_tournaments` y borra equipos).
- Leer, añadir o eliminar entradas de la blacklist de cualquier servidor.

Es una vulnerabilidad de **control de acceso roto (IDOR / Broken Access Control)**.

---

## W-02 · Doble barra (`//`) en URLs generadas por SSR · **Alta**
**Archivo:** `server.py` (`serve_server` línea ~59-60, `serve_tournament` línea ~86-87)
**Descripción:** `DOC_URL` está configurado **con barra final** (`https://complete-tourney.vercel.app/`). El SSR construye URLs con una barra adicional:
```python
target_url = f"{DOC_URL}/server?guild_id={guild_id}"      # -> ...app//server
target_url = f"{DOC_URL}/tournament?id={id}"              # -> ...app//tournament
content.replace(f'content="{DOC_URL}/server"', ...)       # el literal buscado tampoco coincide
```
**Impacto:** Las meta-tags Open Graph/Twitter quedan con `//` (URLs canónicas malformadas, peor SEO y previsualizaciones de enlace). Además, como el HTML base contiene `${DOC_URL}/server` **sin sustituir** (placeholder literal), el `content.replace(...)` no encuentra coincidencia y la sustitución nunca ocurre.

---

## W-03 · El SSR de torneo nunca rellena los metadatos (parámetro incorrecto) · **Media**
**Archivo:** `server.py` (`serve_tournament`, línea ~65)
**Descripción:** La ruta lee el query param `id`:
```python
async def serve_tournament(id: Optional[str] = None):
```
pero **todos los enlaces reales** (generados por el bot y por el frontend) usan `?guild=...&tourney=...`:
- Bot: `f"{DOC_URL}tournament?guild={guild}&tourney={id}"` (`cogs/tourney.py`).
- Frontend: `tournament.js` lee `params.get('guild')` y `params.get('tourney')`.

**Impacto:** El bloque que personaliza `<title>` y `<meta description>` con datos del torneo nunca se ejecuta para enlaces reales, porque `id` siempre llega vacío. Las previsualizaciones de enlaces de torneo muestran siempre el texto genérico.

---

## W-04 · Placeholders `${DOC_URL}` sin sustituir en los HTML · **Media**
**Archivos:** `docLA/index.html`, `dashboard.html`, `doc.html`, `health.html`, `server.html`, `tournament.html`
**Descripción:** Todos los `<meta property="og:url">`, `og:image`, `twitter:*` y el JSON-LD de `index.html` contienen el literal `${DOC_URL}` (p. ej. `content="${DOC_URL}/dashboard"`). No existe ningún paso de plantillado que reemplace `${DOC_URL}` salvo el `replace` puntual y fallido de `server.py` (ver W-02/W-03).
**Impacto:** Las etiquetas de redes sociales apuntan a la URL literal `${DOC_URL}/...`, por lo que las imágenes/*cards* de previsualización no cargan en Discord/Twitter/Facebook.

---

## W-05 · Fechas del histórico de estado mostradas en zona horaria incorrecta · **Media**
**Archivo:** `docLA/js/health.js` (línea ~80)
**Descripción:** El backend guarda `timestamp` con `datetime.utcnow()` (naïve, sin `Z`) y lo serializa con `.isoformat()` → `"2026-06-11T10:00:00"`. En el frontend:
```js
const date = new Date(item.timestamp);
```
JavaScript interpreta una cadena ISO **sin sufijo de zona** como **hora local**, no UTC.
**Impacto:** Las horas del histórico de salud aparecen desplazadas el offset de la zona horaria del visitante (p. ej. +2h en España en verano). Mismo patrón potencial en cualquier fecha derivada de timestamps UTC sin `Z`.

---

## W-06 · Código muerto y con `ReferenceError` en `dashboard.js` · **Media**
**Archivo:** `docLA/js/dashboard.js`
**Descripción:** La función `loadServerDetail()` (y sus auxiliares `editTournament`, `submitEditTournament` con `*-img-file`) son una **vista de detalle obsoleta**: al hacer clic en una tarjeta de servidor, `refreshServers()` navega a `/server?id=...` (página `server.html` + `server.js`), por lo que `loadServerDetail` de `dashboard.js` no se invoca en el flujo normal. Además contiene un bug real:
```js
} else if (g && g.icon) {   // 'g' no está declarado en este ámbito
```
`g` no existe en `loadServerDetail` (la variable es `data.guild`), de modo que si esa rama se alcanzara lanzaría `ReferenceError: g is not defined`, capturado por el `try/catch` que muestra *"Error al actualizar vista"*.
**Impacto:** Mantenibilidad y confusión; riesgo de error si se reactiva esa vista. El `onclick` del historial usa además rutas relativas con `.html` (`tournament.html?...`) inconsistentes con el resto (`/tournament?...`).

---

## W-07 · Fuga de configuración a miembros sin permiso de gestión · **Media**
**Archivo:** `server.py` (`get_guild_details`, ruta `GET /api/guild/{guild_id}`)
**Descripción:** Esta ruta devuelve `config_safe` (IDs de canales, categoría, roles admin, prefijo, etc.) a **cualquier miembro** del servidor, sin condicionar a `can_manage`. La ruta `.../public` sí restringe `config` a quien puede gestionar; aquí no hay esa coherencia.
**Impacto:** Exposición de configuración interna del servidor a usuarios sin rol de gestión.

---

## W-08 · Posible `500` en actualización de torneo inexistente · **Baja**
**Archivo:** `server.py` (`update_tournament`, línea ~929)
**Descripción:**
```python
current_t = await DBManager.get_tournament(tournament_id)
d = update_data.get("date", current_t.get("date", ""))   # current_t puede ser None
```
Si el `tournament_id` no existe, `current_t` es `None` y `current_t.get(...)` lanza `AttributeError`, devolviendo un 500 no controlado (la función no está envuelta en try/except).
**Impacto:** Error 500 en lugar de un 404 limpio ante IDs inválidos.

---

## W-09 · Línea muerta en `saveConfig` (server.js) · **Baja**
**Archivo:** `docLA/js/server.js` (línea ~1068)
**Descripción:**
```js
const rolesStr = document.getElementById("cfg-roles").value;
const roles = rolesStr      // asignación sin uso; el payload recalcula admin_roles inline
const payload = { ... };
```
`roles` no se usa (el `payload` vuelve a hacer el `split` en línea). Resto de código con `const roles` sin punto y coma apoyado en ASI.
**Impacto:** Ruido / deuda técnica. Sin efecto funcional.

---

## W-10 · Dominios inconsistentes entre configuración y SEO · **Baja**
**Archivos:** `docLA/sitemap.xml`, `docLA/robots.txt` vs `.env` (`DOC_URL`, `REDIRECT_URI`)
**Descripción:** `sitemap.xml`/`robots.txt` referencian `https://tourneydoc.victormenjon.es`, mientras que `DOC_URL` y `REDIRECT_URI` apuntan a `https://complete-tourney.vercel.app`. Si solo uno es el dominio canónico real, el otro genera URLs/sitemap incoherentes.
**Impacto:** SEO y canónicas confusas; el `sitemap` puede indexar un dominio distinto al operativo.

---

## W-11 · Dependencia de la API widget de Discord con nombre hardcodeado · **Baja**
**Archivo:** `docLA/js/dashboard.js` (`updateBotStatusGlobal`, líneas ~12-43)
**Descripción:** El estado "Online/Desconectado" del bot se obtiene de `https://discord.com/api/guilds/<HOME_SERVER_ID>/widget.json` y busca un miembro con `username === 'LA TourneyBot'`. Depende de que el **widget del servidor esté activado** y de un **nombre/ID hardcodeados** (`HOME_SERVER_ID`, `client_id`).
**Impacto:** Si el widget se desactiva o cambia el nombre del bot, el panel mostrará siempre "Desconectado" pese a estar online. Frágil ante cambios de configuración.

---

## Resumen
| ID | Gravedad | Título |
|----|----------|--------|
| W-01 | Crítica | Endpoints de API sin verificación de permisos |
| W-02 | Alta | Doble barra `//` en URLs SSR |
| W-03 | Media | SSR de torneo no rellena metadatos (param `id` incorrecto) |
| W-04 | Media | Placeholders `${DOC_URL}` sin sustituir en HTML |
| W-05 | Media | Fechas de health en zona horaria incorrecta |
| W-06 | Media | Código muerto + `ReferenceError` en dashboard.js |
| W-07 | Media | Fuga de config a miembros sin permiso |
| W-08 | Baja | Posible 500 al actualizar torneo inexistente |
| W-09 | Baja | Línea muerta en saveConfig (server.js) |
| W-10 | Baja | Dominios inconsistentes (sitemap vs DOC_URL) |
| W-11 | Baja | Estado del bot vía widget con nombre hardcodeado |
