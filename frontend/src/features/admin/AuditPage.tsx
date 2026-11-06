import { Badge, Center, Code, Loader, SegmentedControl, Stack, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DataTable } from '../../components/DataTable';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import type { Column } from '../../components/tableState';
import { useListState } from '../../components/useListState';
import { type AuditEntry, useAudit } from './useAdmin';

// Filtro por prefijo de acción (`auth.login`, `user.create`…).
const ACTION_FILTERS = [
  { value: '', key: 'all' },
  { value: 'auth.', key: 'auth' },
  { value: 'user.', key: 'user' },
  { value: 'session.', key: 'session' },
  { value: 'connection.', key: 'connection' },
  { value: 'allowlist.', key: 'allowlist' },
  { value: 'project.', key: 'project' },
  { value: 'run.', key: 'run' },
  { value: 'sql.', key: 'sql' },
  { value: 'query.', key: 'query' },
] as const;

export function AuditPage() {
  const { t } = useTranslation();
  const [action, setAction] = useState('');
  const list = useListState();
  const { data, isPending, isError, error } = useAudit(action, list.state);
  const columns: Column<AuditEntry>[] = [
    { key: 'ts', header: t('admin.audit.ts'), sortable: true, cell: (e) => formatDateTime(e.ts) },
    {
      key: 'action',
      header: t('admin.audit.action'),
      sortable: true,
      cell: (e) => t(`admin.audit.actions.${e.action}`, { defaultValue: e.action }),
    },
    {
      key: 'outcome',
      header: t('admin.audit.outcome'),
      sortable: true,
      cell: (e) => (
        <Badge color={e.outcome === 'success' ? 'green' : 'red'} variant="light">
          {t(`admin.audit.outcomes.${e.outcome}`, { defaultValue: e.outcome })}
        </Badge>
      ),
    },
    {
      key: 'actor',
      header: t('admin.audit.actor'),
      sortable: true,
      cell: (e) => e.actor_username ?? t('admin.audit.system'),
    },
    {
      key: 'target',
      header: t('admin.audit.target'),
      sortable: true,
      cell: (e) => (e.target_type ? `${e.target_type} #${e.target_id ?? ''}` : '—'),
    },
    { key: 'ip', header: t('admin.sessions.ip'), cell: (e) => e.ip ?? '—' },
    {
      key: 'details',
      header: t('admin.audit.details'),
      cell: (e) => (e.details ? <Code>{JSON.stringify(e.details)}</Code> : '—'),
    },
  ];

  return (
    <Stack>
      <Title order={2}>{t('admin.audit.title')}</Title>
      <Stack gap={4}>
        <Text size="sm" fw={500} id="audit-filter-label">
          {t('admin.audit.filter')}
        </Text>
        <SegmentedControl
          aria-labelledby="audit-filter-label"
          data={ACTION_FILTERS.map(({ value, key }) => ({ value, label: t(`admin.audit.filters.${key}`) }))}
          value={action}
          onChange={(value) => {
            setAction(value);
            list.resetPage();
          }}
          w="fit-content"
        />
      </Stack>
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && (
        <DataTable
          mode="server"
          label={t('admin.audit.title')}
          searchLabel={t('admin.audit.search')}
          empty={t('admin.audit.empty')}
          columns={columns}
          rowKey={(e) => e.id}
          rows={data.items}
          total={data.total}
          minWidth={820}
          {...list.table}
        />
      )}
    </Stack>
  );
}
