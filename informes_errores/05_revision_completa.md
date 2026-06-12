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

## 💡 Recomendaciones (no aplicadas — requieren decisión o mayor alcance)

| Ref | Tema | Detalle |
|-----|------|---------|
| **R-06** | **Caché de llamadas a Discord** | `users/@me/guilds` y `get_guild_member` se piden varias veces por carga de página y por endpoint, sin caché. Con varios usuarios concurrentes multiplica las llamadas y acerca al *rate limit* (429). Recomendado: caché corta (30–60 s) por usuario/guild. *(Cambio de arquitectura; conviene decidir TTL y almacén.)* |
| **R-07** | **Rate limiting en reportes** | `/api/report/*` solo requieren login; un usuario podría spamear miles de reportes. Recomendado: límite por usuario/tiempo (p. ej. `slowapi`). |
| **R-08** | **Manejo de 429 (rate limit)** | Las respuestas 429 de Discord se tratan como fallo genérico; no se respeta `Retry-After`. |
| **R-09** | **Crecimiento de `health_checks`** | La colección crece sin límite (un registro por hora, indefinidamente). Recomendado: índice TTL o cap. |
| **R-10** | **Validación en `update_config`** | No se valida la longitud del `prefix` (el bot lo limita a 5) ni que `admin_roles`/`playing_role_id` sean IDs válidos. Además duplica la lógica de permisos en vez de usar el helper `user_can_manage`. |
| **R-11** | **Consolidar checks de permisos** | `delete_team_api`, `update_config`, `update_tournament` repiten el patrón de verificación inline; podrían reutilizar `user_can_manage` para consistencia. |
| **R-12** | **`except:` desnudos restantes** | Quedan algunos `except:` de "mejor esfuerzo" (p. ej. `server.py:32`, checks de rol). Son intencionados (no romper flujos best-effort), pero podrían registrar el error. |

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
- `python -m py_compile server.py utils/api.py` → **sin errores**.
- `python -c "import server"` → **importa correctamente**.
- `node --check` sobre los JS modificados (toasts) → **sin errores de sintaxis**.
- Búsqueda de `requests.*` sin `timeout` → **0 restantes**.
