# Configuration Traps

## Location Matching

- `location /api` matchea `/api`, `/api/`, `/api-v2`, `/apiary` — más amplio de lo esperado
- `location /api/` (con slash) NO matchea `/api` sin slash
- `location = /api` es exacto pero no matchea `/api/`
- Regex `location ~` tiene prioridad sobre prefix más largo — orden importa

## Root vs Alias

- `root /var/www; location /img/` → busca en `/var/www/img/`
- `alias /var/www/; location /img/` → busca en `/var/www/` (reemplaza location)
- `alias` sin trailing slash + location con slash = path mal formado
- `alias` con regex requiere captura: `alias /var/www$1`

## try_files

- `try_files $uri /index.html` sin `$uri/` — no encuentra directorios
- Último argumento es internal redirect, no file check — comportamiento diferente
- `try_files` + `proxy_pass` en mismo location = try_files siempre gana
- `=404` como fallback es código, no archivo — `/404` sería archivo

## If Statement

- `if` crea nuevo context — directivas heredadas pueden no aplicar
- `if ($request_uri ~* \.php)` en location ya procesada = doble check inútil
- `return` y `rewrite` dentro de `if` funcionan — otras directivas problemáticas
- Múltiples `if` no se combinan con AND — cada uno es independiente

## Variables

- `$uri` está normalizado (decoded) — `$request_uri` es raw
- Variable undefined = empty string, no error
- `set` dentro de `if` siempre ejecuta — solo el bloque es condicional
- `map` es más eficiente que múltiples `if` para switch/case

## Includes

- `include /etc/nginx/conf.d/*.conf` — orden alfabético, puede importar
- Include de archivo inexistente = nginx no arranca
- Include relativo es relativo a nginx.conf, no al archivo actual
- Circular includes = nginx no arranca con error confuso
