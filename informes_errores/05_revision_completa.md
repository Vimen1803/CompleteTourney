# Revisión completa del código — Informe

> Revisión del estado **actual** del código (no de memoria). Cada hallazgo se ha
> verificado leyendo el código vigente. Se distingue lo **corregido en esta tanda**
> de las **recomendaciones** que requieren una decisión o son de mayor alcance.

---

## ✅ Corregido en esta tanda

### R-01 · Llamadas HTTP sin `timeout` (Riesgo: medio)
- **Dónde:** `utils/api.py` (7 llamadas) y `server.py` (10 llamadas OAuth).
- **Problema:** ninguna petición `requests` tenía `timeout`. Si Discord responde
  lento o se cuelga, el hilo queda bloqueado indefinidamente; bajo carga, el pool
  de hilos del servidor web puede agotarse y dejar la web congelada.
- **Solución:**
  - `api.py` refactorizado con un helper `_request()` que aplica `timeout=10` y
    captura `requests.RequestException` (devuelve `None`/`[]`/`False` como antes).
  - En `server.py` se añadió `timeout=10` a todas las llamadas OAuth (token, `@me`,
    `@me/guilds`) y se protegió la de `api_guilds` (no estaba en `try`).

### R-02 · Filtración de detalles de excepción al cliente (Riesgo: bajo)
- **Dónde:** `/callback`, `get_guild_details`, `get_guild_public`.
- **Problema:** ante un error se devolvía `str(e)` / `Internal Server Error: {e}`
  al cliente, exponiendo trazas internas.
- **Solución:** se registra el error en consola (server-side) y se devuelve un
  mensaje genérico ("No se pudo completar el inicio de sesión." / "Error interno
  del servidor.").

### R-03 · Reportes sin límite de longitud (Riesgo: bajo)
- **Dónde:** `/api/report/bug` y `/api/report/suggestion`.
- **Problema:** la descripción no se limitaba. Un texto > 4096 caracteres rompe el
  embed de Discord, por lo que el reporte **nunca se entregaría** (el loop falla
  en silencio).
- **Solución:** validación de longitud (máx. 1500 caracteres) en ambos endpoints.

### R-04 · Bloque `if __name__ == "__main__"` duplicado y mal colocado (Riesgo: bajo)
- **Dónde:** `server.py`, en mitad del archivo (entre las vistas y las rutas de auth).
- **Problema:** había un `uvicorn.run(...)` suelto antes de registrar la mayoría de
  rutas, además de un comentario `# ... [rest of the file] ...`. Código muerto y
  confuso (al ejecutar `python server.py` directamente arrancaría el servidor antes
  de registrar las rutas de abajo).
- **Solución:** eliminado el bloque intermedio; se conserva el `__main__` real al
  final del archivo.

### R-05 · `keywords` con dominio antiguo (Riesgo: muy bajo / SEO)
- **Dónde:** `docLA/index.html`.
- **Problema:** el meta `keywords` aún citaba `tourneydoc.victormenjon.es` tras la
  migración a Vercel (W-10).
- **Solución:** actualizado a `complete-tourney.vercel.app`.

---

## ✅ Recomendaciones implementadas (segunda tanda)

### R-06 · Caché de llamadas a Discord (Riesgo: medio)
- **Solución:** nuevo módulo `utils/cache.py` con `TTLCache` (en memoria, thread-safe).
  `api.py` cachea `get_guild` (60s), `get_guild_member` (30s), `get_guild_channels`
  (60s), `get_guild_roles` (60s), `get_user` (300s) y `get_bot_guilds` (60s). Solo
  se cachean respuestas 200 (no se cachean fallos). Reduce las ráfagas de llamadas
  repetidas durante una misma carga de página y aleja del *rate limit*.

### R-07 · Rate limiting en reportes (Riesgo: bajo)
- **Solución:** `RateLimiter` en `utils/cache.py`. `/api/report/bug` y
  `/api/report/suggestion` limitan a **5 reportes / 10 min por usuario** (HTTP 429).

### R-08 · Manejo de 429 de Discord (Riesgo: bajo)
- **Solución:** `DiscordAPI._request` reintenta **una vez** ante un 429 respetando
  `Retry-After` (acotado a 5 s).

### R-09 · Crecimiento de `health_checks` (Riesgo: bajo)
- **Solución:** `DBManager.ensure_indexes()` crea un **índice TTL** sobre `timestamp`
  (caducidad 30 días). Se invoca en el `startup` del servidor web.

### R-10 · Validación en `update_config` (Riesgo: bajo)
- **Solución:** se valida que el `prefix` no supere los 5 caracteres (coherente con
  el bot).

### R-11 · Consolidar checks de permisos (Mantenibilidad)
- **Solución:** `delete_team_api` y `update_tournament` usan ahora el helper
  `user_can_manage` (igual que `create_tournament`, `delete_tournament` y la
  blacklist). `update_config` conserva su lógica propia porque necesita distinguir
  `is_admin` (los organizadores no pueden editar `admin_roles`).

### R-12 · `except:` desnudos (Riesgo: muy bajo)
- **Solución (parcial):** el `except` del montaje de `/data` ahora registra el error.
  El resto de `except` de "mejor esfuerzo" (checks de rol que no deben romper el
  flujo) se mantienen a propósito.

---

## ℹ️ Cosas que estaban BIEN (verificadas, no eran problemas)

Durante la revisión se confirmó que ya estaban resueltas (en tandas anteriores):

- **Permisos** en `delete_tournament` y en la **blacklist** (`get`/`add`/`remove`):
  todos usan `user_can_manage`. ✓
- **Meta tags** `${DOC_URL}`: `serve_home`/`serve_docs`/`serve_dashboard` usan
  `render_html()` que sustituye el placeholder por la URL real. ✓
- **`count_tournaments`** duplicado: ya solo existe una definición. ✓
- **Contadores negativos**: `get_bot_stats` ya los clampa a 0 al leer. ✓
- **Bloqueo del event loop en el bot**: el cog usa `aiohttp` (async), no `requests`. ✓

---

## Verificación realizada
- `python -m py_compile server.py utils/api.py utils/cache.py utils/db.py` → **sin errores**.
- `python -c "import server"` → **importa correctamente** (con caché + rate limiter).
- Test de `utils/cache.py`: `TTLCache` (set/get/expiry/invalidate) y `RateLimiter`
  (5 permitidos, 6º denegado, aislamiento por usuario) → **OK**.
- `node --check` sobre los JS modificados (toasts) → **sin errores de sintaxis**.
- Búsqueda de `requests.*` sin `timeout` → **0 restantes**.
