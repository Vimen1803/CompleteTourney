# Informe de Errores — BOT (Discord / Python)

> Ámbito: `main.py`, `config.py`, `cogs/` (`tourney.py`, `admin.py`, `reports.py`, `status_check.py`), `utils/` (`db.py`, `api.py`, `visual.py`) en lo que afecta **exclusivamente** al funcionamiento del bot de Discord.
> Fecha del informe: 2026-06-11
> Estado: **solo diagnóstico** (sin correcciones aplicadas en esta fase).

## Escala de gravedad
- **Crítica**: rompe una funcionalidad central o corrompe datos.
- **Alta**: comportamiento incorrecto visible o riesgo serio.
- **Media**: fallo funcional acotado o degradación notable.
- **Baja**: code smell, deuda técnica o caso borde poco probable.

---

## B-01 · `aiohttp` usado pero no importado en `tourney.py` · **Crítica**
**Archivo:** `cogs/tourney.py` (funciones internas `fetch_image` en `process_round` ~línea 722 y en `advance_round` ~línea 1011)
**Descripción:** Ambas funciones hacen:
```python
async with aiohttp.ClientSession() as session:
    ...
```
pero `aiohttp` **no está importado** en el módulo (los imports de cabecera son `discord, commands, uuid, datetime, random, io, DBManager/Tournament/Match, generate_bracket_image, config`). La llamada lanza `NameError: name 'aiohttp' is not defined`, que queda **silenciado por el `except:` desnudo** de `fetch_image`, devolviendo siempre `None`.

**Impacto:** Las imágenes de los brackets **nunca** descargan el icono del servidor ni la imagen del torneo: el pie del bracket sale sin logo y los bytes de imagen siempre son `None`. El fallo es **silencioso** (no aparece en logs por el `except` mudo), lo que dificulta su diagnóstico. Es la causa raíz de que "no se vean las imágenes" en los cuadros.

---

## B-02 · `init_bot_stats(1)` resetea el contador de servidores a 1 en cada arranque · **Alta**
**Archivo:** `main.py` (línea ~55, dentro de `on_ready`)
**Descripción:**
```python
await DBManager.init_bot_stats(1)
```
Se pasa el literal `1` en lugar de `len(bot.guilds)`. En `db.py`, `init_bot_stats` **sobrescribe** `serversOn` con el valor recibido en cada arranque ("On startup, we trust the bot's current guild count"), por lo que el contador siempre queda en **1**, independientemente de en cuántos servidores esté el bot.

**Impacto:** La estadística `serversOn` (mostrada en la web — contador "Servidores" de la home, y usada en `/api/stats`) es incorrecta tras cada reinicio. Solo se corrige parcialmente con eventos `on_guild_join/remove` posteriores.

---

## B-03 · Estado final inconsistente `"Terminado"` en final por BYE · **Media**
**Archivo:** `cogs/tourney.py` (`advance_round`, ~línea 993)
**Descripción:** Cuando la final se resuelve con una rama vacía (BYE):
```python
tourney['status'] = "finished"
await DBManager.update_tournament(tourney['id'], {"status": "Terminado"})
```
Se guarda el estado literal `"Terminado"` (español) en lugar de `"finished"`, que es el valor canónico usado en el resto del código y en la web.

**Impacto:** Inconsistencia de datos:
- `get_active_tournament` busca `["open", "active", "pending"]`, así que el torneo no se considera activo (correcto), pero…
- el `statusMap` del frontend no reconoce `"Terminado"` y muestra el texto crudo.
- No se asigna `winner_id` en ese camino.

---

## B-04 · Sin categoría configurada → no se crean canales de enfrentamiento (sin aviso) · **Media**
**Archivo:** `cogs/tourney.py` (`process_round`, ~líneas 760-805)
**Descripción:**
```python
category = guild.get_channel(category_id) if category_id else None
if not category:
    pass   # no se avisa
...
if t1 and t2 and category:   # sin categoría, jamás se crea el canal del match
```
Si el administrador no ha configurado `category_id`, los partidos con dos equipos reales **no generan canal** ni notifican a los participantes, pero el torneo "arranca" igualmente (sí publica el bracket).

**Impacto:** Torneo iniciado en un estado inutilizable (sin salas de partido) y **sin ningún mensaje de error** que explique por qué. Confusión para el organizador.

---

## B-05 · Método `count_tournaments` duplicado en `db.py` · **Baja**
**Archivo:** `utils/db.py` (líneas ~224-229 y ~231-236)
**Descripción:** `count_tournaments` está definido **dos veces** de forma idéntica; la segunda definición simplemente oculta a la primera.
**Impacto:** Código muerto / deuda técnica. Sin efecto funcional, pero confunde y es propenso a divergencias si se edita solo una copia.

---

## B-06 · Comprobación de zona horaria inútil en `ping` y health · **Baja**
**Archivos:** `cogs/tourney.py` (`ping`, ~línea 210), `server.py` (`perform_health_check`, ~línea 733)
**Descripción:**
```python
if last_seen.tzinfo is None:
    last_seen = last_seen.replace(tzinfo=None)   # no-op: ya es None
```
La rama solo se ejecuta cuando `tzinfo` ya es `None`, y entonces vuelve a ponerlo a `None`. No hace nada útil. Funciona por casualidad porque tanto el guardado (`utcnow()`) como la comparación son naïve-UTC.
**Impacto:** Confusión / código engañoso. Riesgo latente si en el futuro se guardan timestamps *aware*.

---

## B-07 · `except:` desnudos que ocultan errores · **Baja**
**Archivos:** `cogs/tourney.py` (múltiples: `fetch_image`, asignación de roles, `kick`, parsing de menciones…), `main.py` (`get_or_create_invite`), `utils/api.py`, `cogs/admin.py`.
**Descripción:** Uso extendido de `except:`/`except Exception` mudos que descartan la excepción sin registrarla. Es lo que enmascara B-01.
**Impacto:** Diagnóstico muy difícil ante fallos (los errores desaparecen sin traza). Mala práctica generalizada.

---

## B-08 · Latencia/heartbeat puede registrar valores no numéricos al arrancar · **Baja**
**Archivo:** `cogs/status_check.py` (`heartbeat_loop`, ~línea 17)
**Descripción:** `round(self.bot.latency * 1000, 2)`; antes de que el websocket esté listo, `bot.latency` puede ser `nan`/`inf`. Está mitigado por `before_loop → wait_until_ready`, pero no hay validación explícita.
**Impacto:** Riesgo bajo de almacenar `NaN` como latencia si el orden de readiness cambia.

---

## B-09 · `config.py` revienta el arranque si falta una variable de canal · **Baja**
**Archivo:** `config.py` (líneas ~23-27)
**Descripción:**
```python
ERROR_CHANNEL: int = int(os.getenv("ERROR_CHANNEL"))
```
Si la variable no existe, `os.getenv` devuelve `None` y `int(None)` lanza `TypeError` en tiempo de import, impidiendo arrancar el bot, sin un mensaje claro de qué variable falta.
**Impacto:** Arranque frágil; mensaje de error poco descriptivo ante `.env` incompleto.

---

## B-10 · Validación de creación de torneo más estricta en el bot que en la web · **Baja**
**Archivo:** `cogs/tourney.py` (`create_tourney`, ~líneas 393-399)
**Descripción:** El comando de Discord exige `max_teams` múltiplo de 2 y entre 2 y 64. La ruta web equivalente (`create_tournament` en `server.py`) **no aplica** esas mismas validaciones (acepta cualquier entero). Genera comportamiento divergente según el origen.
**Impacto:** Inconsistencia de reglas de negocio entre canales (ver también informe "ambos").

---

## Resumen
| ID | Gravedad | Título |
|----|----------|--------|
| B-01 | Crítica | `aiohttp` usado sin importar → imágenes de bracket nunca cargan |
| B-02 | Alta | `init_bot_stats(1)` resetea servidores a 1 en cada arranque |
| B-03 | Media | Estado `"Terminado"` en lugar de `"finished"` (final por BYE) |
| B-04 | Media | Sin categoría → no se crean canales de partido, sin aviso |
| B-05 | Baja | `count_tournaments` duplicado |
| B-06 | Baja | Comprobación de tzinfo inútil en ping/health |
| B-07 | Baja | `except:` desnudos ocultan errores |
| B-08 | Baja | Heartbeat puede registrar NaN al arrancar |
| B-09 | Baja | `config.py` revienta con `.env` incompleto |
| B-10 | Baja | Validación de torneo más laxa en web que en bot |
