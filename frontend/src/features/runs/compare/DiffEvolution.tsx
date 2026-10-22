import { Alert, Badge, Group, Loader, NativeSelect, Stack, Table, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../../components/ErrorAlert';
import { formatDateTime } from '../../../components/format';
import { type DiffItem, useBaselineCandidates, useDiffEvolution } from './useDiff';

function ItemTable({ title, items, color }: { title: string; items: DiffItem[]; color: string }) {
  const { t } = useTranslation();
  return (
    <Stack gap="xs">
      <Group gap="xs">
        <Title order={5}>{title}</Title>
        <Badge color={color} variant="light">
          {items.length}
        </Badge>
      </Group>
      {items.length === 0 ? (
        <Text size="sm" c="dimmed">
          {t('diff.evolution.none')}
        </Text>
      ) : (
        <Table striped withTableBorder aria-label={title}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('diff.evolution.kind')}</Table.Th>
              <Table.Th>{t('diff.evolution.object')}</Table.Th>
              <Table.Th>{t('diff.state')}</Table.Th>
              <Table.Th>{t('diff.source')}</Table.Th>
              <Table.Th>{t('diff.target')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((item) => (
              <Table.Tr key={`${item.kind}|${item.table ?? ''}|${item.name}|${item.attribute ?? ''}`}>
                <Table.Td>{t(`diff.kinds.${item.kind}`)}</Table.Td>
                <Table.Td>
                  {item.table ? `${item.table}.${item.name}` : item.name}
                  {item.attribute && item.kind === 'column'
                    ? ` (${t(`diff.attributes.${item.attribute}`)})`
                    : ''}
                </Table.Td>
                <Table.Td>{t(`diff.status.${item.status}`)}</Table.Td>
                <Table.Td>{item.source}</Table.Td>
                <Table.Td>{item.target}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}

/** Mejora de la Fase 6: qué cambió respecto a otra comparación del proyecto. */
export function DiffEvolutionPanel({ runId, projectId }: { runId: string; projectId: number }) {
  const { t } = useTranslation();
  const candidates = useBaselineCandidates(projectId, runId, true);
  const [baseline, setBaseline] = useState<string | null>(null);
  const evolution = useDiffEvolution(runId, baseline);

  return (
    <Stack>
      <Title order={4}>{t('diff.evolution.title')}</Title>
      {candidates.isError && <ErrorAlert error={candidates.error} />}
      {candidates.data && candidates.data.length === 0 && (
        <Text size="sm" c="dimmed">
          {t('diff.evolution.noCandidates')}
        </Text>
      )}
      {candidates.data && candidates.data.length > 0 && (
        <NativeSelect
          label={t('diff.evolution.baseline')}
          value={baseline ?? ''}
          onChange={(event) => setBaseline(event.currentTarget.value || null)}
          data={[
            { value: '', label: t('diff.evolution.choose') },
            ...candidates.data.map((run) => ({
              value: run.id,
              label: `${formatDateTime(run.created_at)} · ${run.id.slice(-8)}${run.username ? ` · ${run.username}` : ''}`,
            })),
          ]}
        />
      )}
      {evolution.isPending && baseline !== null && <Loader size="sm" aria-label={t('common.loading')} />}
      {evolution.isError && <ErrorAlert error={evolution.error} />}
      {evolution.data && (
        <Stack>
          {!evolution.data.labels_match && (
            <Alert color="yellow" title={t('diff.evolution.differentTitle')}>
              {t('diff.evolution.different')}
            </Alert>
          )}
          <ItemTable title={t('diff.evolution.new')} items={evolution.data.new} color="red" />
          <ItemTable title={t('diff.evolution.resolved')} items={evolution.data.resolved} color="green" />
          <ItemTable title={t('diff.evolution.persisting')} items={evolution.data.persisting} color="gray" />
        </Stack>
      )}
    </Stack>
  );
}
