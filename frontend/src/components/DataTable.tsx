import {
  Group,
  Pagination,
  Stack,
  Table,
  Text,
  TextInput,
  UnstyledButton,
  VisuallyHidden,
} from '@mantine/core';
import { useDebouncedCallback } from '@mantine/hooks';
import { type ReactNode, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { type Column, PAGE_SIZE, type SortState, clientRows, nextSort } from './tableState';

const SEARCH_DELAY_MS = 300;

interface CommonProps<T> {
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  /** Nombre de la tabla (para lectores de pantalla). */
  label: string;
  searchLabel: string;
  empty: string;
  minWidth?: number;
  /** Controles extra junto a la búsqueda (filtros propios de la lista). */
  toolbar?: ReactNode;
}

interface ServerProps<T> extends CommonProps<T> {
  mode: 'server';
  rows: T[];
  total: number;
  page: number;
  onPage: (page: number) => void;
  sort: SortState | null;
  onSort: (sort: SortState | null) => void;
  query: string;
  /** Se llama 300 ms después de dejar de escribir; el padre vuelve a la página 1. */
  onQuery: (query: string) => void;
}

interface ClientProps<T> extends CommonProps<T> {
  mode: 'client';
  rows: readonly T[];
  /** Orden inicial (si no, el de `rows`). */
  initialSort?: SortState;
}

export type DataTableProps<T> = ServerProps<T> | ClientProps<T>;

function SortHeader<T>({
  column,
  sort,
  onSort,
}: {
  column: Column<T>;
  sort: SortState | null;
  onSort: (sort: SortState | null) => void;
}) {
  const { t } = useTranslation();
  const active = sort?.key === column.key ? sort.order : null;
  const ariaSort = active === 'asc' ? 'ascending' : active === 'desc' ? 'descending' : 'none';
  if (column.hiddenHeader) {
    return (
      <Table.Th>
        <VisuallyHidden>{column.header}</VisuallyHidden>
      </Table.Th>
    );
  }
  if (!column.sortable) return <Table.Th>{column.header}</Table.Th>;
  return (
    <Table.Th aria-sort={ariaSort}>
      <UnstyledButton
        onClick={() => onSort(nextSort(sort, column.key))}
        aria-label={t('table.sortBy', { column: column.header })}
        fw={600}
        fz="sm"
      >
        <Group gap={4} wrap="nowrap">
          {column.header}
          <Text span size="xs" {...(active ? {} : { c: 'dimmed' })} aria-hidden>
            {active === 'asc' ? '▲' : active === 'desc' ? '▼' : '↕'}
          </Text>
        </Group>
      </UnstyledButton>
    </Table.Th>
  );
}

/**
 * Tabla de una lista con orden por columna, búsqueda y paginación de {@link PAGE_SIZE} filas.
 *
 * - `mode="server"`: la API pagina, ordena (`sort`, `order`) y busca (`q`); el padre guarda el estado.
 * - `mode="client"`: la lista llega entera y todo se hace en memoria.
 */
export function DataTable<T>(props: DataTableProps<T>) {
  const { t } = useTranslation();
  const { columns, rowKey, label, searchLabel, empty, minWidth = 640, toolbar } = props;
  const [clientQuery, setClientQuery] = useState('');
  const [clientSort, setClientSort] = useState<SortState | null>(
    props.mode === 'client' ? (props.initialSort ?? null) : null,
  );
  const [clientPage, setClientPage] = useState(1);
  const [typed, setTyped] = useState(props.mode === 'server' ? props.query : '');
  const serverQuery = useDebouncedCallback((value: string) => {
    if (props.mode === 'server') props.onQuery(value);
  }, SEARCH_DELAY_MS);

  const clientResult = useMemo(
    () => (props.mode === 'client' ? clientRows(props.rows, columns, clientQuery, clientSort) : []),
    [props.mode, props.rows, columns, clientQuery, clientSort],
  );

  const server = props.mode === 'server';
  const total = server ? props.total : clientResult.length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const page = Math.min(server ? props.page : clientPage, pages);
  const rows = server ? props.rows : clientResult.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const sort = server ? props.sort : clientSort;
  const onSort = (next: SortState | null) => {
    if (server) {
      props.onSort(next);
      props.onPage(1);
    } else {
      setClientSort(next);
      setClientPage(1);
    }
  };
  const onPage = (next: number) => (server ? props.onPage(next) : setClientPage(next));
  const first = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const last = Math.min(page * PAGE_SIZE, total);

  return (
    <Stack gap="xs">
      <Group align="flex-end" gap="sm">
        <TextInput
          label={searchLabel}
          value={server ? typed : clientQuery}
          onChange={(event) => {
            const value = event.currentTarget.value;
            if (server) {
              setTyped(value);
              serverQuery(value);
            } else {
              setClientQuery(value);
              setClientPage(1);
            }
          }}
          maw={320}
          style={{ flex: 1 }}
        />
        {toolbar}
      </Group>
      {rows.length === 0 ? (
        <Text c="dimmed">{empty}</Text>
      ) : (
        <Table.ScrollContainer minWidth={minWidth}>
          <Table striped highlightOnHover aria-label={label}>
            <Table.Thead>
              <Table.Tr>
                {columns.map((column) => (
                  <SortHeader key={column.key} column={column} sort={sort} onSort={onSort} />
                ))}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((row) => (
                <Table.Tr key={rowKey(row)}>
                  {columns.map((column) => (
                    <Table.Td key={column.key}>{column.cell(row)}</Table.Td>
                  ))}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      <Group justify="space-between">
        <Text size="xs" c="dimmed" aria-live="polite">
          {total > 0 ? t('table.range', { first, last, total }) : ''}
        </Text>
        {total > PAGE_SIZE && <Pagination total={pages} value={page} onChange={onPage} size="sm" />}
      </Group>
    </Stack>
  );
}
