# Proxy Traps

## proxy_pass URL

- `proxy_pass http://backend` (sin slash) — preserva `/api/users` → `/api/users`
- `proxy_pass http://backend/` (con slash) — reemplaza `/api/users` → `/users`
- Mezclar `location /api/` con `proxy_pass http://x/v1` = paths inesperados
- Variables en proxy_pass (`$uri`) cambian completamente el comportamiento

## Headers

- `proxy_set_header Host $host` — sin esto, backend recibe IP del proxy como Host
- `Host $http_host` incluye puerto — `Host $host` no
- `X-Forwarded-For` se sobreescribe, no se añade — usar `$proxy_add_x_forwarded_for`
- Headers con underscore `_` ignorados por defecto — `underscores_in_headers on` para permitir

## WebSocket

- Falta `proxy_http_version 1.1` = WebSocket falla silenciosamente
- `Connection "upgrade"` debe ser literal string, no variable
- Timeout por defecto 60s mata conexiones WebSocket idle — subir `proxy_read_timeout`
- Múltiples proxies en cadena = cada uno necesita upgrade headers

## Buffering

- `proxy_buffering on` (default) — respuesta completa antes de enviar a client
- Con buffering, respuestas streaming no funcionan — SSE, chunked encoding rotos
- `X-Accel-Buffering: no` header del backend puede desactivar — pero no siempre funciona
- Buffer muy pequeño + respuesta grande = escritura a disco temporal

## Timeouts

- `proxy_connect_timeout` default 60s — muy largo para detectar backend caído
- Backend lento + `proxy_read_timeout` bajo = 504 frecuentes
- Timeout en nginx no cancela request en backend — sigue procesando

## Upstream

- Upstream server sin puerto = puerto 80 implícito
- `max_fails=0` desactiva health checks — server never marked down
- `fail_timeout` es DOBLE: período de conteo Y tiempo de ban
- Round-robin ignora peso si solo hay 1 server up
