# ADR-007 — Sitio HTML de la documentación: origen opaco y URL firmada

- **Estado**: Aceptado
- **Fecha**: 2026-10-22

## Contexto

`DatabaseDocumentation` de util_bbdd genera un sitio HTML de varias páginas (`index.html`, `tables/`, `views/`,
`graphs/*.svg`, `assets/`) que necesita JavaScript para la navegación y el resaltado SQL (un script en línea más
`assets/sql-highlight.js`). Las plantillas escapan los datos (Jinja2 con autoescape), pero los nombres y comentarios
de los objetos vienen de la BD documentada y no son de confianza.

Las vistas previas de la Fase 3 (`iframe sandbox=""` y CSP `sandbox` sin scripts) dejan el sitio sin navegación.
Además, un documento con origen opaco hace las peticiones de sus subrecursos como de otro sitio: la cookie de sesión
(`SameSite=Lax`) no viaja con ellas y el CSS, el JS y los enlaces internos darían 401.

## Decisión

1. **Origen opaco con scripts**: el sitio se sirve con la CSP
   `sandbox allow-scripts allow-popups allow-downloads; default-src 'none'; script-src 'self' 'unsafe-inline';
   style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'none';
   form-action 'none'; base-uri 'none'; frame-ancestors 'self'`, y en la SPA dentro de un
   `iframe sandbox="allow-scripts allow-popups allow-downloads"`, **nunca** con `allow-same-origin`. Los scripts se
   ejecutan, pero no pueden leer la cookie, el DOM de la SPA ni llamar a la API (`connect-src 'none'`).
2. **URL de capacidad**: `GET /api/v1/runs/{id}/site/{token}/{ruta}`. El token es
   `<user_id>.<caducidad>.<HMAC-SHA256(UBW_APP_SECRET_KEY, "site:{run}:{user}:{caducidad}")>`, caduca a los
   `UBW_SESSION_IDLE_MINUTES` y lo emite `GET /runs/{id}` (`site_url`). En cada petición se comprueba la firma, que el
   usuario sigue activo y que es miembro del proyecto.
3. Solo se sirven **artefactos registrados** del run de tipo `html` (comparación exacta con `artifacts.path`, más
   `safe_path`): ni `run.json`, ni el log, ni rutas con `..`.
4. `Referrer-Policy: no-referrer` para que el token no salga en el `Referer` de los enlaces externos;
   `X-Content-Type-Options: nosniff`.
5. «Abrir en pestaña nueva» usa la misma URL: la CSP `sandbox` mantiene el origen opaco también como documento
   principal.

## Consecuencias

- Quien obtenga la URL puede leer ese sitio mientras no caduque y su usuario siga teniendo acceso; no da acceso a
  nada más. Cerrar la sesión no invalida las URL ya emitidas (caducan solas).
- El Markdown de los artefactos se convierte con `marked` y se muestra en un `iframe srcdoc` con `sandbox=""` y una
  CSP `default-src 'none'`, sin scripts.

## Alternativas descartadas

- **`allow-same-origin` + scripts**: el sitio podría leer la cookie CSRF y llamar a la API como el usuario.
- **Sin scripts** (como las vistas previas): el sitio pierde la navegación por pestañas y el resaltado.
- **Cookie `SameSite=None`**: abre CSRF en toda la API para resolver un problema de una sola ruta.
- **Subdominio dedicado**: exige DNS y TLS adicionales en un despliegue autoalojado.
