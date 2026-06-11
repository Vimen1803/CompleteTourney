# Informe de Errores — AMBOS (Bot + Web simultáneamente)

> Ámbito: errores cuya causa o efecto implica **a la vez** al bot de Discord y al soporte web (datos compartidos en MongoDB, convenciones de URL, modelos comunes, etc.).
> Fecha del informe: 2026-06-11
> Estado: **solo diagnóstico** (sin correcciones aplicadas en esta fase).

## Escala de gravedad
- **Crítica**: compromete seguridad/datos o rompe una funcionalidad central.
- **Alta**: comportamiento incorrecto visible o riesgo serio.
- **Media**: fallo funcional acotado o degradación notable.
- **Baja**: code smell, deuda técnica o caso borde poco probable.

---

## A-01 · XSS almacenado: contenido de usuario renderizado sin escapar · **Crítica**
**Origen del dato (bot y web):** nombres y descripciones de torneos, nombres de equipos, motivos de blacklist, nombres de miembros.
- Vía **bot**: `,tourney create`, `,tourney register`, `,tourney blacklist add` (Discord).
- Vía **web**: formularios de crear/editar torneo y modal de blacklist.

**Sink (web):** `docLA/js/server.js`, `tournament.js`, `dashboard.js` insertan esos valores directamente con `innerHTML` sin sanitizar, por ejemplo:
```js
<h1 ...>${t.name}</h1>
<p ...>${t.description || 'Sin descripción'}</p>
<span ...>${tm.name}</span>
<td>${b.reason}</td>
```
**Descripción:** Ni el bot ni la web sanitizan la entrada, y la web la imprime como HTML. Un nombre de torneo/equipo como `<img src=x onerror=alert(document.cookie)>` se ejecuta en el navegador de **cualquiera** que abra la página del servidor o del torneo.

**Impacto:** **Cross-Site Scripting almacenado**. Como la cookie de sesión la gestiona `SessionMiddleware`, el robo de sesión/realización de acciones en nombre de la víctima es plausible. Afecta a ambos lados porque el vector de inyección está tanto en el bot como en la web, y el render vulnerable está en la web que ambos alimentan.

---

## A-02 · Convención de barra final de `DOC_URL` incoherente entre bot y web · **Alta**
**Archivos:** `cogs/tourney.py` (genera enlaces) y `server.py` (genera enlaces SSR), ambos consumen `DOC_URL`.
**Descripción:** No hay una convención común sobre si `DOC_URL` lleva `/` final:
- El **bot** asume **con** barra: `f"{DOC_URL}tournament?..."`, `f"{DOC_URL}docs"`.
- La **web** asume **sin** barra: `f"{DOC_URL}/tournament?..."`, `f"{DOC_URL}/server"`.

Con el valor actual (`.../vercel.app/`, con barra), el bot produce URLs correctas y la web produce `//` (ver W-02). Si alguien quitara la barra de `.env`, se invertiría el problema y se romperían los enlaces del bot.

**Impacto:** Cualquier cambio en `DOC_URL` rompe uno de los dos lados. Fuente de bugs recurrentes en enlaces compartidos. Requiere normalización centralizada (p. ej. `DOC_URL.rstrip('/')` + barra explícita en cada uso).

---

## A-03 · Semántica del contador `tournamentsDone` (incrementa/decrementa, puede ir negativo) · **Media**
**Archivos:** `utils/db.py` (`increment_tournaments`/`decrement_tournaments`/`get_bot_stats`), llamado desde **bot** (`cogs/tourney.py` create/delete) y **web** (`server.py` create/delete).
**Descripción:** El campo `tournamentsDone` se **incrementa al crear** y se **decrementa al borrar** un torneo, tanto desde el bot como desde la web. Esto:
1. Lo convierte en un "número de torneos vivos", no en un total histórico ("torneos hechos"), pese a su nombre y a mostrarse como "Torneos" en la home.
2. Permite valores **negativos** (`$inc: -1` sin suelo) si se borran torneos creados antes de implementar el contador.

**Impacto:** La métrica pública puede ser engañosa o negativa. Dos orígenes (bot y web) escriben sobre el mismo contador sin una semántica clara y compartida.

---

## A-04 · Campo de logs con dos nombres: `tourney_logs` vs `tourney_logs_enabled` · **Media**
**Archivos:** `utils/db.py` (dataclass `GuildConfig`), `cogs/tourney.py` (lectura/escritura), `server.py` (lectura/escritura), `docLA/js/*` (formularios).
**Descripción:** El modelo `GuildConfig` declara el campo `tourney_logs`, pero tanto el **bot** (`send_log`, `set logs`) como la **web** (`update_config`, `get_guild_*`) leen y escriben `tourney_logs_enabled`. El campo `tourney_logs` del dataclass **nunca se usa** para lectura efectiva, y `server.py` arrastra parches de compatibilidad (`config['tourney_logs_enabled'] = config.get('tourney_logs', False)`).
**Impacto:** Modelo de datos incoherente con el uso real; documentos antiguos podrían tener `tourney_logs` y no `tourney_logs_enabled`, provocando que los logs no se activen como se espera. Deuda que afecta a ambos lados.

---

## A-05 · Reportes (bug/sugerencia) tardan hasta 60 min en entregarse · **Media**
**Archivos:** `cogs/reports.py` (`@tasks.loop(minutes=LOOP_TIME)`, `LOOP_TIME=60` en `config.py`), alimentado por **web** (`/api/report/bug|suggestion`) y **bot** (`,tourney bug|suggest`).
**Descripción:** Tanto los reportes creados desde la web como desde el bot se guardan en MongoDB con `sent_to_discord=False` y se entregan al canal de Discord mediante un loop que corre **cada 60 minutos**. No hay disparo inmediato.
**Impacto:** Un usuario que reporta un bug puede esperar hasta una hora a que aparezca en el canal de soporte. Percepción de que "no llega" el reporte. Afecta a ambos canales de entrada.

---

## A-06 · Reglas de negocio divergentes entre bot y web al crear/editar torneos · **Media**
**Archivos:** `cogs/tourney.py` (`create_tourney`) vs `server.py` (`create_tournament`, `update_tournament`).
**Descripción:** Validaciones inconsistentes para el mismo recurso (torneo):
- `max_teams`: el bot exige múltiplo de 2 y rango 2-64; la web acepta cualquier entero (incluido impar o fuera de rango).
- Fechas/horas: ninguno valida formato (`YYYY-MM-DD`, `HH:MM`); se aceptan cadenas arbitrarias.
- `min_members`/`max_members`: la web no garantiza `min <= max`.

**Impacto:** Un torneo creado por web puede entrar en estados que el bot no maneja bien (p. ej. `max_teams` impar afecta al *seeding* de `start_tourney`, que asume potencia/multiplicidad de 2). Datos inconsistentes según el origen.

---

## A-07 · Uso de `datetime.utcnow()` (deprecado) en bot y web · **Baja**
**Archivos:** `utils/db.py`, `server.py`, `cogs/tourney.py`, `cogs/reports.py`.
**Descripción:** Uso generalizado de `datetime.datetime.utcnow()`, **deprecado** desde Python 3.12 (el entorno usa CPython 3.13, según los `.pyc`). Lo recomendado es `datetime.now(datetime.UTC)`. Además, al guardar timestamps *naïve* sin `Z` se favorece el bug de zona horaria del frontend (ver W-05).
**Impacto:** Avisos de deprecación y, a futuro, posible ruptura; raíz del desfase horario en la web.

---

## A-08 · Sin sanitización/validación de entrada compartida (longitudes, tipos) · **Baja**
**Archivos:** entrada del **bot** (`cogs/tourney.py`) y de la **web** (`server.py`), que comparten colecciones.
**Descripción:** No se validan longitudes máximas de nombre/descripción ni se normaliza texto antes de persistir. Discord limita los embeds a ciertos tamaños; un nombre/descr. muy largo (introducido por web) puede provocar fallos al renderizar embeds del bot (p. ej. `,tourney info`).
**Impacto:** Posibles errores de envío de embed en el bot por datos introducidos desde la web, y viceversa. Baja probabilidad pero efecto cruzado real.

---

## Resumen
| ID | Gravedad | Título |
|----|----------|--------|
| A-01 | Crítica | XSS almacenado (datos de bot/web renderizados sin escapar) |
| A-02 | Alta | Convención de barra final de `DOC_URL` incoherente bot↔web |
| A-03 | Media | Semántica/negativos del contador `tournamentsDone` |
| A-04 | Media | Campo de logs con dos nombres (`tourney_logs` vs `_enabled`) |
| A-05 | Media | Reportes tardan hasta 60 min en llegar a Discord |
| A-06 | Media | Validaciones divergentes bot↔web al crear/editar torneos |
| A-07 | Baja | `datetime.utcnow()` deprecado en ambos lados |
| A-08 | Baja | Falta de validación/longitud de entrada compartida |
