import { Alert, Button, Group, Loader, NativeSelect, Stack, Text, Textarea, TextInput } from '@mantine/core';
import { type KeyboardEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { ResultTable } from '../../components/ResultTable';
import { useRunSql, useSqlCapabilities } from './useExplorer';

/** SQL libre de solo lectura sobre una conexión ``read_only`` del proyecto (permiso ``can_run_sql`` y editor). */
export function SqlConsole({ projectId }: { projectId: number }) {
  const { t } = useTranslation();
  const capabilities = useSqlCapabilities(projectId);
  const run = useRunSql(projectId);
  const [alias, setAlias] = useState<string>('');
  const [sql, setSql] = useState('');
  const [limit, setLimit] = useState('');

  if (capabilities.isPending) return <Loader aria-label={t('common.loading')} />;
  if (capabilities.isError) return <ErrorAlert error={capabilities.error} />;
  const caps = capabilities.data;
  if (!caps.allowed) {
    return (
      <Alert color="yellow" title={t('common.noPermission')}>
        {t(`explorer.sql.denied.${caps.reason ?? 'permission'}`)}
      </Alert>
    );
  }
  const usable = caps.connections.filter((c) => c.read_only && c.supported);
  if (usable.length === 0) {
    return <Text c="dimmed">{t('explorer.sql.noConnections')}</Text>;
  }
  const current = usable.find((c) => c.alias === alias) ?? usable[0];

  const execute = () => {
    if (!current || !sql.trim()) return;
    run.mutate({ alias: current.alias, sql, limit: limit ? Number(limit) : null });
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      execute();
    }
  };

  return (
    <Stack>
      <Text c="dimmed" size="sm">
        {t('explorer.sql.intro')}
      </Text>
      <Group align="flex-end">
        <NativeSelect
          label={t('explorer.sql.connection')}
          data={caps.connections.map((c) => ({
            value: c.alias,
            label: `${c.alias} · ${c.connection_name} (${c.db_type})`,
            disabled: !(c.read_only && c.supported),
          }))}
          value={current?.alias ?? ''}
          onChange={(event) => setAlias(event.currentTarget.value)}
          w={360}
        />
        <TextInput
          label={t('explorer.limit')}
          inputMode="numeric"
          value={limit}
          onChange={(event) => setLimit(event.currentTarget.value)}
          w={120}
        />
      </Group>
      {current && !current.read_only_transaction && (
        <Alert color="orange">{t('explorer.sql.noReadOnlyTransaction', { engine: current.db_type })}</Alert>
      )}
      <Textarea
        label={t('explorer.sql.query')}
        description={t('explorer.sql.hint')}
        value={sql}
        onChange={(event) => setSql(event.currentTarget.value)}
        onKeyDown={onKeyDown}
        autosize
        minRows={6}
        styles={{ input: { fontFamily: 'monospace' } }}
      />
      <Group>
        <Button onClick={execute} loading={run.isPending} disabled={!sql.trim()}>
          {t('explorer.run')}
        </Button>
      </Group>
      {run.isError && <ErrorAlert error={run.error} />}
      {run.data && <ResultTable result={run.data} />}
    </Stack>
  );
}
