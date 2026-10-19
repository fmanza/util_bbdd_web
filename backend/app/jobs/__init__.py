"""Ejecución de operaciones de util_bbdd como jobs (Fase 3, ADR-002).

Cada job corre en un subproceso hijo del worker: util_bbdd no ofrece progreso ni cancelación, así que cancelar es
terminar el subproceso, que además aísla memoria y estado de clase entre ejecuciones.
"""
