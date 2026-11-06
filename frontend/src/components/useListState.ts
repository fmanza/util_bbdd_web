import { useState } from 'react';

import { PAGE_SIZE, type SortState } from './tableState';

/** Estado de una lista paginada en el servidor: búsqueda, página y orden (lo que `DataTable` muestra y cambia). */
export interface ListState {
  q: string;
  page: number;
  sort: SortState | null;
}

/** Parámetros de la API (`q`, `sort`, `order`, `limit`, `offset`) a partir del estado de la lista. */
export function listQuery<S extends string>(list: ListState, pageSize: number = PAGE_SIZE) {
  return {
    q: list.q.trim() || null,
    sort: (list.sort?.key ?? null) as S | null,
    order: list.sort?.order ?? null,
    limit: pageSize,
    offset: (list.page - 1) * pageSize,
  };
}

/** Primera página sin búsqueda ni orden (selectores). */
export const FIRST_PAGE: ListState = { q: '', page: 1, sort: null };

/** Estado y manejadores para `<DataTable mode="server" {...list.table} />`. Buscar u ordenar vuelve a la página 1. */
export function useListState(initialSort: SortState | null = null) {
  const [state, setState] = useState<ListState>({ q: '', page: 1, sort: initialSort });
  return {
    state,
    /** Para reiniciar la página al cambiar un filtro propio de la lista. */
    resetPage: () => setState((s) => ({ ...s, page: 1 })),
    table: {
      page: state.page,
      onPage: (page: number) => setState((s) => ({ ...s, page })),
      sort: state.sort,
      onSort: (sort: SortState | null) => setState((s) => ({ ...s, sort, page: 1 })),
      query: state.q,
      onQuery: (q: string) => setState((s) => ({ ...s, q, page: 1 })),
    },
  };
}
