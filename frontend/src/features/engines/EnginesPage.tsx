import { Anchor, Badge, Center, Loader, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { DataTable } from '../../components/DataTable';
import type { Column } from '../../components/tableState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { DriverBadges } from './DriverBadges';
import { type Engine, useEngines } from './useEngines';

export function YesNo({ value }: { value: boolean }) {
  const { t } = useTranslation();
  return (
    <Badge color={value ? 'green' : 'gray'} variant="light">
      {value ? t('common.yes') : t('common.no')}
    </Badge>
  );
}

export function EnginesPage() {
  const { t } = useTranslation();
  const { data, isPending, isError, error } = useEngines();

  const columns: Column<Engine>[] = [
    {
      key: 'name',
      header: t('engines.engine'),
      sortable: true,
      searchable: true,
      rowHeader: true,
      value: (e) => `${e.name} ${e.db_type}`,
      cell: (e) => (
        <Anchor component={Link} to={`/engines/${e.db_type}`}>
          {e.name}
        </Anchor>
      ),
    },
    { key: 'versions', header: t('engines.versions'), cell: (e) => e.version_range || '—' },
    {
      key: 'port',
      header: t('engines.port'),
      sortable: true,
      value: (e) => e.default_port ?? null,
      cell: (e) => e.default_port ?? '—',
    },
    { key: 'drivers', header: t('engines.drivers'), cell: (e) => <DriverBadges engine={e} /> },
    {
      key: 'async',
      header: t('engines.async'),
      sortable: true,
      value: (e) => Number(e.capabilities.async_supported),
      cell: (e) => <YesNo value={e.capabilities.async_supported} />,
    },
    {
      key: 'migrate_source',
      header: t('engines.migrateSource'),
      sortable: true,
      value: (e) => Number(e.capabilities.migrate_source),
      cell: (e) => <YesNo value={e.capabilities.migrate_source} />,
    },
    {
      key: 'migrate_target',
      header: t('engines.migrateTarget'),
      sortable: true,
      value: (e) => Number(e.capabilities.migrate_target),
      cell: (e) => <YesNo value={e.capabilities.migrate_target} />,
    },
    {
      key: 'readiness',
      header: t('engines.readiness'),
      sortable: true,
      value: (e) => Number(e.capabilities.readiness),
      cell: (e) => <YesNo value={e.capabilities.readiness} />,
    },
  ];

  return (
    <Stack>
      <Title order={2}>{t('engines.title')}</Title>
      <Text c="dimmed">{t('engines.intro')}</Text>
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && (
        <DataTable
          mode="client"
          label={t('engines.title')}
          caption={t('engines.matrixCaption')}
          searchLabel={t('engines.search')}
          empty={t('table.noMatches')}
          columns={columns}
          rowKey={(engine) => engine.db_type}
          rows={data}
          minWidth={900}
        />
      )}
    </Stack>
  );
}
