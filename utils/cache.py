import time
import threading

class TTLCache:
    """
    Caché simple en memoria con expiración por TTL y seguro entre hilos.

    Pensada para la web (FastAPI): reduce las llamadas repetidas a la API de
    Discord durante una misma carga de página (varios endpoints piden lo mismo
    en segundos). En Vercel serverless solo persiste dentro de una instancia
    "caliente", que es justo donde ocurren esas ráfagas de peticiones.
    """
    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, expires = entry
            if time.time() > expires:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key, value, ttl):
        with self._lock:
            self._store[key] = (value, time.time() + ttl)

    def invalidate(self, key):
        with self._lock:
            self._store.pop(key, None)


class RateLimiter:
    """
    Limitador de tasa en memoria (ventana deslizante simple) y seguro entre hilos.
    Evita el spam de endpoints (p. ej. reportes) por usuario.
    """
    def __init__(self):
        self._hits = {}
        self._lock = threading.Lock()

    def allow(self, key, max_hits: int, window: int) -> bool:
        """Devuelve True si la acción está permitida; False si se superó el límite."""
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < window]
            if len(hits) >= max_hits:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True


# Instancia compartida para las llamadas a la API de Discord (server.py / api.py)
discord_cache = TTLCache()

# Limitador de tasa para reportes (bugs/sugerencias)
report_limiter = RateLimiter()
