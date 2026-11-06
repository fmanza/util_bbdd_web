import { Anchor, Code, Progress, Text } from '@mantine/core';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { DataTable } from '../../components/DataTable';
import { formatBytes, formatDateTime, formatDuration } from '../../components/format';
import type { Column, SortState } from '../../components/tableState';
import { RunStatusBadge } from './RunStatusBadge';
import type { Run } from './useRuns';

interface RunsTableProps {
  runs: Run[];
  total: number;
  showProject?: boolean;
  label: string;
  empty: string;
  toolbar?: ReactNode;
  page: number;
  onPage: (page: number) => void;
  sort: SortState | null;
  onSort: (sort: SortState | null) => void;
  query: string;
  onQuery: (query: string) => void;
}

/** Historial agrupado por ejecución: una fila por run con operación, usuario, estado, duración y artefactos; orden,
 *  búsqueda y paginación en el servidor. */
export function RunsTable({
  runs,
  total,
  showProject = false,
  label,
  empty,
  toolbar,
  ...list
}: RunsTableProps) {
  const { t } = useTranslation();
  const columns: Column<Run>[] = [
    {
      key: 'id',
      header: t('runs.run'),
      rowHeader: true,
      cell: (run) => (
        <Anchor component={Link} to={`/runs/${run.id}`} aria-label={t('runs.openLabel', { id: run.id })}>
          <Code>{run.id.slice(-8)}</Code>
        </Anchor>
      ),
    },
    ...(showProject
      ? [
          {
            key: 'project',
            header: t('runs.project'),
            cell: (run: Run) => (
              <Anchor component={Link} to={`/projects/${run.project_id}`}>
                {run.project_name}
              </Anchor>
            ),
          },
        ]
      : []),
    { key: 'operation', header: t('runs.operation'), sortable: true, cell: (run) => run.operation },
    { key: 'user', header: t('runs.user'), sortable: true, cell: (run) => run.username ?? '—' },
    {
      key: 'status',
      header: t('runs.statusLabel'),
      sortable: true,
      cell: (run) => (
        <>
          <RunStatusBadge status={run.status} />
          {run.status === 'running' && run.progress_pct !== null && (
            <Progress
              value={run.progress_pct}
              size="xs"
              mt={4}
              aria-label={t('runs.progressLabel', { pct: run.progress_pct })}
            />
          )}
        </>
      ),
    },
    {
      key: 'created_at',
      header: t('runs.createdAt'),
      sortable: true,
      cell: (run) => formatDateTime(run.created_at),
    },
    { key: 'duration', header: t('runs.duration'), cell: (run) => formatDuration(run.duration_seconds) },
    { key: 'size', header: t('runs.size'), sortable: true, cell: (run) => formatBytes(run.size_bytes) },
    {
      key: 'artifacts',
      header: t('runs.artifacts'),
      cell: (run) => <Text size="sm">{run.artifacts_count}</Text>,
    },
  ];
  return (
    <DataTable
      mode="server"
      label={label}
      searchLabel={t('runs.search')}
      empty={empty}
      columns={columns}
      rowKey={(run) => run.id}
      rows={runs}
      total={total}
      minWidth={860}
      toolbar={toolbar}
      {...list}
    />
  );
}
