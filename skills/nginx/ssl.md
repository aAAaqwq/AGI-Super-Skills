# SSL Traps

## Certificates

- `ssl_certificate` debe ser fullchain (cert + intermediate) — solo cert = warning en browsers
- Orden del chain importa: cert primero, luego intermediates, NO root
- Key y cert mismatch = nginx no arranca con error críptico
- Cert expirado = nginx arranca OK pero browsers rechazan

## Configuration

- `ssl on` está deprecated — usar `listen 443 ssl` en su lugar
- `ssl_protocols TLSv1 TLSv1.1` = inseguro — mínimo TLSv1.2
- `ssl_prefer_server_ciphers on` ya no recomendado para TLS 1.3 — solo para 1.2
- `ssl_ciphers` mal ordenados = servidor elige cipher débil

## OCSP Stapling

- `ssl_stapling on` sin `ssl_trusted_certificate` = stapling silenciosamente desactivado
- DNS resolver necesario para OCSP — `resolver 8.8.8.8` si no hay local
- OCSP de algunas CAs es lento/unreliable — puede añadir latencia

## HTTP/2

- `http2` directive en listen, no como módulo separado
- `http2_push` deprecated en nginx 1.25+
- HTTP/2 + proxy a HTTP/1.1 backend funciona — pero pierde multiplexing
- `large_client_header_buffers` puede necesitar ajuste para HTTP/2

## Client Certificates

- `ssl_verify_client on` rechaza sin cert — usar `optional` para hacer opcional
- `ssl_client_certificate` es la CA, no el cert del cliente
- `$ssl_client_verify` es "SUCCESS", no "true" o "1"
- CRL checking requiere config adicional — sin ella certs revocados son aceptados

## Common Mistakes

- Redirect loop: 80→443→80 porque `X-Forwarded-Proto` no se chequea
- Mixed content: HTTPS página carga HTTP recursos — `upgrade-insecure-requests` ayuda
- HSTS con max-age muy largo + certificado inválido = sitio inaccesible
- Cert para `example.com` no cubre `www.example.com` — necesita SAN o wildcard
