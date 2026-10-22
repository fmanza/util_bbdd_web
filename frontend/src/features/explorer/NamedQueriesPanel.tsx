import { Button, Group, NativeSelect, Stack, Text, TextInput } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { isApiError } from '../../api/client';
import { ErrorAlert } from '../../components/ErrorAlert';
import { ResultTable } from '../../components/ResultTable';
import { useConnectionQueries, useRunNamedQuery } from './useExplorer';

/** Queries nombradas del motor de la conexión: parámetros (solo identificadores o números) y resultados. */
export function NamedQueriesPanel({ connectionId }: { connectionId: number }) {
  const { t } = useTranslation();
  const queries = useConnectionQueries(connectionId);
  const run = useRunNamedQuery(connectionId);
  const [selectedId, setSelectedId] = useState<string>('');
  const [values, setValues] = useState<Record<string, string>>({});
  const [limit, setLimit] = useState('');
  const selected = queries.data?.find((q) => String(q.id) === selectedId) ?? queries.data?.[0];
  const fieldErrors = new Map(
    (isApiError(run.error) ? (run.error.problem.errors ?? []) : []).map((e) => [
      String(e.loc[2] ?? ''),
      e.msg,
    ]),
  );

  if (queries.isPending) return <Text>{t('common.loading')}</Text>;
  if (queries.isError) return <ErrorAlert error={queries.error} />;
  if (!selected) return <Text c="dimmed">{t('explorer.queries.empty')}</Text>;

  return (
    <Stack>
      <NativeSelect
        label={t('explorer.queries.query')}
        data={queries.data.map((q) => ({ value: String(q.id), label: q.name }))}
        value={String(selected.id)}
        onChange={(event) => {
          setSelectedId(event.currentTarget.value);
          setValues({});
          run.reset();
        }}
        maw={420}
      />
      {selected.description && <Text c="dimmed">{selected.description}</Text>}
      <Text size="xs" c="dimmed">
        {t('explorer.queries.paramsHint')}
      </Text>
      <Group align="flex-start">
        {selected.params.map((param) => (
          <TextInput
            key={param}
            label={param}
            required
            value={values[param] ?? ''}
            onChange={(event) => {
              const value = event.currentTarget.value;
              setValues((previous) => ({ ...previous, [param]: value }));
            }}
            error={fieldErrors.get(param)}
            w={200}
          />
        ))}
        <TextInput
          label={t('explorer.limit')}
          inputMode="numeric"
          value={limit}
          onChange={(event) => setLimit(event.currentTarget.value)}
          w={120}
        />
      </Group>
      <Group>
        <Button
          loading={run.isPending}
          onClick={() =>
            run.mutate({ queryId: selected.id, params: values, limit: limit ? Number(limit) : null })
          }
        >
          {t('explorer.run')}
        </Button>
      </Group>
      {run.isError && <ErrorAlert error={run.error} />}
      {run.data && <ResultTable result={run.data} />}
    </Stack>
  );
}
