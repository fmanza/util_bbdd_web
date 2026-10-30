# ADR-012 — Almacenamiento administrable y purga por cuota

- **Estado**: Aceptado
- **Fecha**: 2026-10-26

## Contexto

La cuota por usuario (`UBW_USER_QUOTA_MB`) y la retención (`UBW_RUN_RETENTION_DAYS`,
`UBW_RUN_RETENTION_PER_PROJECT`, `UBW_UPLOAD_RETENTION_DAYS`) eran variables de entorno: cambiarlas exigía editar el
despliegue y reiniciar. La cuota solo **bloquea** (409 al encolar o subir) y no libera nada; la retención va por
antigüedad y por número, una vez por hora (ADR-005). Los administradores quieren cambiar estos valores desde la web,
dar más o menos espacio a usuarios concretos y, opcionalmente, que llegar a la cuota libere espacio en lugar de
bloquear.

## Decisión

1. **Ajustes efectivos**: tabla `app_settings` (clave, valor JSON, quién y cuándo). El valor por defecto de cada ajuste
   es su variable `UBW_*`; un admin lo sobrescribe en *Administración → Almacenamiento* y `null` lo devuelve a la
   variable. Los ajustes efectivos son una copia de `Settings` con esas filas aplicadas
   (`domain/storage/settings.py`): la retención, las subidas y el worker los reciben sin cambiar de firma. Se leen en
   cada uso, así que la API y el worker ven los cambios **sin reiniciar**. Solo se admiten las claves conocidas, con
   sus rangos (una fila fuera de rango se ignora y se avisa en el log); no guarda secretos.

    | Clave | Variable | Rango |
    |---|---|---|
    | `user_quota_mb` | `UBW_USER_QUOTA_MB` (1024) | 0–10 000 000; 0 = sin límite |
    | `run_retention_days` | `UBW_RUN_RETENTION_DAYS` (30) | 0–3650 |
    | `run_retention_per_project` | `UBW_RUN_RETENTION_PER_PROJECT` (100) | 0–100 000 |
    | `upload_retention_days` | `UBW_UPLOAD_RETENTION_DAYS` (7) | 0–365 |
    | `quota_purge` | `UBW_QUOTA_PURGE` (false) | sí/no |
    | `quota_purge_target_pct` | `UBW_QUOTA_PURGE_TARGET_PCT` (80) | 10–95 |

2. **Cuota por usuario**: `users.storage_quota_mb` (`null` = la global, `0` = sin límite) desde la ficha del usuario.
3. **Purga por cuota** (opcional, desactivada por defecto): cuando el espacio de un usuario llega a su cuota, se
   purgan **sus** ejecuciones terminadas, de la más antigua a la más reciente, hasta bajar al
   `quota_purge_target_pct`. Nunca las terminadas hace menos de **60 minutos** (vistas previas y modos secos que aún
   sirven, resultados recién generados) ni las que cita una ejecución en cola o en curso (`preview_run`, `plan_run`,
   `dry_run_run`). Se aplica al encolar y al subir un fichero (antes de responder 409) y en el mantenimiento del
   worker. Se audita como `run.purge` con `reason=quota`. Los ficheros subidos y las plantillas siguen con su
   retención.
4. **Vista previa y «Aplicar ahora»**: antes de guardar, la pantalla enseña cuántas ejecuciones y ficheros (y cuánto
   espacio) purgaría la siguiente pasada con los valores propuestos. «Aplicar ahora» deja una marca que el worker
   recoge en su siguiente ciclo, sin esperar a la pasada horaria.
5. **«Mi espacio»** (`GET /api/v1/auth/me/storage`): cada usuario ve solo cantidades de su uso frente a su cuota y si
   le afecta la purga por cuota; nunca la lista de ejecuciones (podría incluir proyectos de los que ya no es miembro).

## Consecuencias

- **Positivas**: cuota y retención ajustables sin tocar el despliegue; cuotas a medida; la purga por cuota evita el
  bloqueo cuando se activa; los usuarios ven su espacio antes de llegar al límite.
- **Negativas**:
    - La purga por cuota borra resultados que nadie pidió borrar; en proyectos compartidos, también los ven otros
      miembros (como ya pasaba con la purga manual y la retención). Por eso está desactivada por defecto y se audita.
    - Un plan de migración (sin límite de edad para aplicarlo) puede purgarse por cuota; hay que repetir el plan.
    - Las variables `UBW_*` de estos ajustes pasan a ser el **valor por defecto**: si un admin cambió un ajuste, editar
      la variable no tiene efecto hasta restablecerlo en la web.
    - Purgar al encolar borra carpetas durante la petición (lo justo para bajar al objetivo).

## Alternativas descartadas

- **Seguir con variables de entorno**: cada cambio exige editar el despliegue y reiniciar.
- **Purgar solo en el worker**: más predecible, pero el usuario recibiría el 409 hasta la siguiente pasada.
- **Purgar también ficheros subidos y plantillas por cuota**: los ficheros tienen su propia retención y las plantillas
  no cuentan en la cuota; mezclarlos complicaría explicar qué se borra.

## Enmienda (2026-10-30): límites de la carga de ficheros

Tres ajustes más, en *Administración → Almacenamiento → Carga de ficheros*, con el mismo mecanismo (`app_settings`,
la variable `UBW_*` como valor por defecto, sin reiniciar):

| Clave | Variable | Rango |
|---|---|---|
| `upload_max_mb` | `UBW_UPLOAD_MAX_MB` (50) | 1–2048 |
| `upload_max_uncompressed_mb` | `UBW_UPLOAD_MAX_UNCOMPRESSED_MB` (300) | 1–8192 |
| `bulk_max_rows` | `UBW_BULK_MAX_ROWS` (1 000 000) | 1–50 000 000 |

La API comprueba `Content-Length` y los bytes recibidos con el valor efectivo; el job de carga recibe los ajustes
efectivos (`run_job` aplica `effective_settings`, antes solo los usaba el mantenimiento del worker), y las plantillas
usan también el tamaño descomprimido efectivo. «Mi espacio» devuelve `upload_max_mb` para que la pantalla *Carga*
muestre el máximo vigente a cualquier usuario. Un límite alto amplía lo que un editor puede subir (disco, CPU de la
vista previa); lo siguen acotando la cuota, el rate limiting y el tope de 2048 MB.
