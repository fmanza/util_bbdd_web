import {
  Alert,
  Button,
  Center,
  Code,
  Group,
  List,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DataTable } from '../../components/DataTable';
import type { Column, SortState } from '../../components/tableState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatBytes, formatDateTime } from '../../components/format';
import { RunStatusBadge } from '../runs/RunStatusBadge';
import {
  type AdminRun,
  type ProjectRunsDeleteResult,
  useAdminRuns,
  useDeleteProjectRuns,
  useDeleteRun,
  useProjectRunsSummary,
} from './useAdminRuns';

/** Palabra que hay que escribir para borrar una ejecución (D8: el id de 26 caracteres es poco práctico). */
const DELETE_WORD = 'ELIMINAR';
const STATUSES = ['queued', 'running', 'succeeded', 'failed', 'cancelled', 'purged'] as const;

function DeleteRunModal({ run, onClose }: { run: AdminRun; onClose: () => void }) {
  const { t } = useTranslation();
  const [typed, setTyped] = useState('');
  const remove = useDeleteRun();
  return (
    <Modal opened onClose={onClose} title={t('admin.runs.deleteTitle')}>
      <Stack>
        <Text size="sm">{t('admin.runs.deleteBody')}</Text>
        <List size="sm">
          <List.Item>{t('admin.runs.summaryProject', { name: run.project_name })}</List.Item>
          <List.Item>
            {t('admin.runs.summaryRun', { operation: run.operation })} <Code>{run.id}</Code>
          </List.Item>
          <List.Item>{t('admin.runs.summarySize', { size: formatBytes(run.size_bytes) })}</List.Item>
        </List>
        <TextInput
          label={t('admin.runs.typeWord', { word: DELETE_WORD })}
          value={typed}
          onChange={(event) => setTyped(event.currentTarget.value)}
          autoComplete="off"
        />
        {remove.isError && <ErrorAlert error={remove.error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            color="red"
            disabled={typed !== DELETE_WORD}
            loading={remove.isPending}
            onClick={() => remove.mutate(run.id, { onSuccess: onClose })}
          >
            {t('admin.runs.delete')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function DeleteProjectRunsModal({
  projectId,
  projectName,
  onClose,
}: {
  projectId: number;
  projectName: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [typed, setTyped] = useState('');
  const summary = useProjectRunsSummary(projectId);
  const remove = useDeleteProjectRuns();
  const [result, setResult] = useState<ProjectRunsDeleteResult | null>(null);

  return (
    <Modal opened onClose={onClose} title={t('admin.runs.deleteProjectTitle', { name: projectName })}>
      {result ? (
        <Stack>
          <Alert color="green" title={t('admin.runs.deletedTitle')}>
            <List size="sm">
              <List.Item>
                {t('admin.runs.deleted', { count: result.deleted, size: formatBytes(result.freed_bytes) })}
              </List.Item>
              {result.skipped_active > 0 && (
                <List.Item>{t('admin.runs.skippedActive', { count: result.skipped_active })}</List.Item>
              )}
              {result.skipped_pending_dump > 0 && (
                <List.Item>{t('admin.runs.skippedDump', { count: result.skipped_pending_dump })}</List.Item>
              )}
            </List>
          </Alert>
          <Group justify="flex-end">
            <Button onClick={onClose}>{t('admin.runs.close')}</Button>
          </Group>
        </Stack>
      ) : (
        <Stack>
          {summary.isPending && <Loader size="sm" aria-label={t('common.loading')} />}
          {summary.isError && <ErrorAlert error={summary.error} />}
          {summary.data && (
            <Text size="sm">
              {t('admin.runs.deleteProjectBody', {
                count: summary.data.runs,
                size: formatBytes(summary.data.size_bytes),
              })}
            </Text>
          )}
          <Text size="sm" c="dimmed">
            {t('admin.runs.deleteProjectSkips')}
          </Text>
          <TextInput
            label={t('admin.runs.typeProject', { name: projectName })}
            value={typed}
            onChange={(event) => setTyped(event.currentTarget.value)}
            autoComplete="off"
          />
          {remove.isError && <ErrorAlert error={remove.error} />}
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button
              color="red"
              disabled={typed !== projectName || !summary.data || summary.data.runs === 0}
              loading={remove.isPending}
              onClick={() => remove.mutate({ projectId, confirm: typed }, { onSuccess: setResult })}
            >
              {t('admin.runs.deleteProject')}
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}

/**
 * Administración → Ejecuciones: las de todos los proyectos, solo metadatos (un admin no miembro no ve su contenido).
 * Eliminar borra la fila y los ficheros; las de un proyecto, todas las terminadas (D1-D3).
 */
export function RunsAdminPage() {
  const { t } = useTranslation();
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<AdminRun['status'] | null>(null);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<SortState | null>(null);
  const [deleting, setDeleting] = useState<AdminRun | null>(null);
  const [project, setProject] = useState<{ id: number; name: string } | null>(null);
  const runs = useAdminRuns({ q: q.trim(), status, page, sort });

  const columns: Column<AdminRun>[] = [
    {
      key: 'created_at',
      header: t('admin.runs.created'),
      sortable: true,
      cell: (r) => formatDateTime(r.created_at),
    },
    { key: 'project', header: t('admin.runs.project'), sortable: true, cell: (r) => r.project_name },
    { key: 'operation', header: t('admin.runs.operation'), sortable: true, cell: (r) => r.operation },
    {
      key: 'status',
      header: t('admin.runs.status'),
      sortable: true,
      cell: (r) => <RunStatusBadge status={r.status} />,
    },
    { key: 'user', header: t('admin.runs.user'), sortable: true, cell: (r) => r.username ?? '—' },
    { key: 'size', header: t('admin.runs.size'), sortable: true, cell: (r) => formatBytes(r.size_bytes) },
    {
      key: 'actions',
      header: t('common.actions'),
      hiddenHeader: true,
      cell: (r) => (
        <Group gap="xs" wrap="nowrap">
          <Button
            size="xs"
            color="red"
            variant="light"
            onClick={() => setDeleting(r)}
            aria-label={t('admin.runs.deleteLabel', { id: r.id })}
          >
            {t('admin.runs.delete')}
          </Button>
          <Button
            size="xs"
            color="red"
            variant="subtle"
            onClick={() => setProject({ id: r.project_id, name: r.project_name })}
            aria-label={t('admin.runs.deleteProjectLabel', { name: r.project_name })}
          >
            {t('admin.runs.deleteProjectShort')}
          </Button>
        </Group>
      ),
    },
  ];

  return (
    <Stack>
      <Title order={2}>{t('admin.runs.title')}</Title>
      <Text size="sm" c="dimmed">
        {t('admin.runs.intro')}
      </Text>
      {runs.isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {runs.isError && <ErrorAlert error={runs.error} />}
      {runs.data && (
        <DataTable
          mode="server"
          label={t('admin.runs.title')}
          searchLabel={t('admin.runs.search')}
          empty={t('admin.runs.empty')}
          columns={columns}
          rowKey={(r) => r.id}
          rows={runs.data.items}
          total={runs.data.total}
          page={page}
          onPage={setPage}
          sort={sort}
          onSort={setSort}
          query={q}
          onQuery={(value) => {
            setQ(value);
            setPage(1);
          }}
          minWidth={900}
          toolbar={
            <NativeSelect
              label={t('admin.runs.status')}
              value={status ?? ''}
              onChange={(event) => {
                setStatus((event.currentTarget.value || null) as AdminRun['status'] | null);
                setPage(1);
              }}
              data={[
                { value: '', label: t('admin.runs.allStatuses') },
                ...STATUSES.map((s) => ({ value: s, label: t(`runs.status.${s}`) })),
              ]}
            />
          }
        />
      )}
      {deleting && <DeleteRunModal run={deleting} onClose={() => setDeleting(null)} />}
      {project && (
        <DeleteProjectRunsModal
          projectId={project.id}
          projectName={project.name}
          onClose={() => setProject(null)}
        />
      )}
    </Stack>
  );
}
