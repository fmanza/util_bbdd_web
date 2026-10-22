import { Anchor, Code, Progress, Table, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { formatDateTime, formatDuration } from '../../components/format';
import { RunStatusBadge } from './RunStatusBadge';
import type { Run } from './useRuns';

/** Historial agrupado por ejecución: una fila por run con operación, usuario, estado, duración y artefactos. */
export function RunsTable({ runs, showProject = false }: { runs: Run[]; showProject?: boolean }) {
  const { t } = useTranslation();
  return (
    <Table.ScrollContainer minWidth={860}>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('runs.run')}</Table.Th>
            {showProject && <Table.Th>{t('runs.project')}</Table.Th>}
            <Table.Th>{t('runs.operation')}</Table.Th>
            <Table.Th>{t('runs.user')}</Table.Th>
            <Table.Th>{t('runs.statusLabel')}</Table.Th>
            <Table.Th>{t('runs.createdAt')}</Table.Th>
            <Table.Th>{t('runs.duration')}</Table.Th>
            <Table.Th>{t('runs.artifacts')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {runs.map((run) => (
            <Table.Tr key={run.id}>
              <Table.Th scope="row">
                <Anchor
                  component={Link}
                  to={`/runs/${run.id}`}
                  aria-label={t('runs.openLabel', { id: run.id })}
                >
                  <Code>{run.id.slice(-8)}</Code>
                </Anchor>
              </Table.Th>
              {showProject && (
                <Table.Td>
                  <Anchor component={Link} to={`/projects/${run.project_id}`}>
                    {run.project_name}
                  </Anchor>
                </Table.Td>
              )}
              <Table.Td>{run.operation}</Table.Td>
              <Table.Td>{run.username ?? '—'}</Table.Td>
              <Table.Td>
                <RunStatusBadge status={run.status} />
                {run.status === 'running' && run.progress_pct !== null && (
                  <Progress
                    value={run.progress_pct}
                    size="xs"
                    mt={4}
                    aria-label={t('runs.progressLabel', { pct: run.progress_pct })}
                  />
                )}
              </Table.Td>
              <Table.Td>{formatDateTime(run.created_at)}</Table.Td>
              <Table.Td>{formatDuration(run.duration_seconds)}</Table.Td>
              <Table.Td>
                <Text size="sm">{run.artifacts_count}</Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
