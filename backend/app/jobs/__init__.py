"""Ejecución de operaciones de util_bbdd como jobs (Fase 3, ADR-002).

Cada job corre en un subproceso hijo del worker, que aísla memoria y estado de clase entre ejecuciones. Al cancelar
(``worker.py``): las operaciones con progreso de util_bbdd paran por sí mismas y, si no, el worker termina el
subproceso tras un margen; las escrituras en destino solo paran entre pasos y nunca se terminan por una cancelación
(solo por ``job_timeout``); el resto se termina directamente.
"""
