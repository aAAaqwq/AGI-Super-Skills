# Performance Traps

## Worker Configuration

- `worker_processes auto` puede ser excesivo en containers — limitar manualmente
- `worker_connections 1024` es por worker — total = workers × connections
- `multi_accept on` puede causar starvation en algunos workers
- CPU pinning (`worker_cpu_affinity`) rara vez ayuda en práctica

## Buffers

- `client_body_buffer_size` pequeño + uploads = escritura a disco tmp
- Buffer overflow silencioso — request se procesa pero más lento
- `proxy_buffer_size` debe ser suficiente para headers de respuesta
- Muchos buffers pequeños peor que pocos grandes para memoria

## Gzip

- `gzip on` sin `gzip_types` = solo text/html comprimido
- Gzip en archivos ya comprimidos (jpg, png, zip) = CPU waste + archivo más grande
- `gzip_vary on` crítico para CDN — sin él, CDN puede servir versión wrong
- `gzip_comp_level 9` rara vez vale la pena — 6 es sweet spot

## Caching

- `proxy_cache` sin `proxy_cache_key` usa default que puede colisionar
- Cache key con `$request_uri` incluye query string — puede explotar caché
- `proxy_cache_valid 200 1h` — pero 301/302 se cachean para siempre por defecto
- `inactive` vs `max_size` — inactive borra por tiempo, max_size por espacio

## Static Files

- `sendfile on` sin `tcp_nopush on` = no aprovecha kernel optimization
- `expires` header sin `Cache-Control` = browsers ignoran
- `try_files` con muchos paths = múltiples syscalls
- Symlinks + `disable_symlinks` por seguridad puede romper deploys

## Logging

- `access_log` sync por defecto = I/O block en cada request
- `buffer=32k flush=5s` para async logging — pero puedes perder logs en crash
- Log rotation sin `reopen` signal = nginx escribe a archivo borrado
- JSON logging parseable pero más bytes por línea
