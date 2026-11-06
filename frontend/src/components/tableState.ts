// Lógica de `DataTable` (orden, búsqueda y página en memoria), separada del componente.

import type { ReactNode } from 'react';

/** Filas por página de todas las listas (sesión `2026-11-06-explorer-runs-lists`: «máximo 25»). */
export const PAGE_SIZE = 25;

export type SortOrder = 'asc' | 'desc';
export interface SortState<K extends string = string> {
  key: K;
  order: SortOrder;
}

export interface Column<T> {
  key: string;
  /** Texto de la cabecera (también el nombre accesible del botón de orden). */
  header: string;
  cell: (row: T) => ReactNode;
  /** Ordenable. En modo servidor, `key` es el valor de `sort` de la API. */
  sortable?: boolean;
  /** Modo cliente: valor para ordenar y buscar (por defecto, el texto de la celda no se usa). */
  value?: (row: T) => string | number | null | undefined;
  /** Modo cliente: la búsqueda mira esta columna (con `value`). */
  searchable?: boolean;
  /** Cabecera solo para lectores de pantalla (columna de acciones). */
  hiddenHeader?: boolean;
}

/** asc → desc → sin orden (el de la lista). */
export function nextSort(current: SortState | null, key: string): SortState | null {
  if (current?.key !== key) return { key, order: 'asc' };
  return current.order === 'asc' ? { key, order: 'desc' } : null;
}

function compare(a: unknown, b: unknown): number {
  if (a === b) return 0;
  if (a === null || a === undefined || a === '') return 1;
  if (b === null || b === undefined || b === '') return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' });
}

/** Filtra, ordena y pagina en memoria (listas pequeñas que la API devuelve enteras). */
export function clientRows<T>(
  rows: readonly T[],
  columns: Column<T>[],
  query: string,
  sort: SortState | null,
): T[] {
  const needle = query.trim().toLowerCase();
  const searchable = columns.filter((c) => c.searchable && c.value);
  let result = needle
    ? rows.filter((row) =>
        searchable.some((c) =>
          String(c.value?.(row) ?? '')
            .toLowerCase()
            .includes(needle),
        ),
      )
    : [...rows];
  const column = sort ? columns.find((c) => c.key === sort.key) : undefined;
  if (sort && column?.value) {
    const value = column.value;
    const sign = sort.order === 'asc' ? 1 : -1;
    result = result
      .map((row, i) => ({ row, i }))
      .sort((a, b) => sign * compare(value(a.row), value(b.row)) || a.i - b.i)
      .map(({ row }) => row);
  }
  return result;
}
