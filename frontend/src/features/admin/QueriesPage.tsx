import {
  Button,
  Code,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { isApiError } from '../../api/client';
import { DataTable } from '../../components/DataTable';
import type { Column } from '../../components/tableState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { useEngines } from '../engines/useEngines';
import { type NamedQuery, useAdminQueries, useDeleteQuery, useSaveQuery } from '../explorer/useExplorer';

function QueryModal({ query, onClose }: { query: NamedQuery | null; onClose: () => void }) {
  const { t } = useTranslation();
  const engines = useEngines();
  const save = useSaveQuery();
  const [dbType, setDbType] = useState(query?.db_type ?? 'postgresql');
  const [name, setName] = useState(query?.name ?? '');
  const [description, setDescription] = useState(query?.description ?? '');
  const [template, setTemplate] = useState(query?.sql_template ?? '');
  const fieldError = (field: string) =>
    isApiError(save.error) ? save.error.problem.errors?.find((e) => e.loc[1] === field)?.msg : undefined;

  return (
    <Modal
      opened
      onClose={onClose}
      title={query ? t('admin.queries.editTitle') : t('admin.queries.createTitle')}
      size="lg"
    >
      <Stack>
        {save.isError && <ErrorAlert error={save.error} />}
        <NativeSelect
          label={t('connections.engine')}
          data={(engines.data ?? []).map((e) => ({ value: e.db_type, label: e.name }))}
          value={dbType}
          onChange={(event) => setDbType(event.currentTarget.value)}
          disabled={query !== null}
        />
        <TextInput
          label={t('admin.queries.name')}
          description={t('admin.queries.nameHint')}
          required
          value={name}
          onChange={(event) => setName(event.currentTarget.value)}
          error={fieldError('name')}
        />
        <TextInput
          label={t('projects.description')}
          value={description}
          onChange={(event) => setDescription(event.currentTarget.value)}
        />
        <Textarea
          label={t('admin.queries.template')}
          description={t('admin.queries.templateHint')}
          required
          autosize
          minRows={5}
          value={template}
          onChange={(event) => setTemplate(event.currentTarget.value)}
          error={fieldError('sql_template')}
          styles={{ input: { fontFamily: 'monospace' } }}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            loading={save.isPending}
            disabled={!name.trim() || !template.trim()}
            onClick={() =>
              save.mutate(
                {
                  id: query?.id ?? null,
                  body: { db_type: dbType, name: name.trim(), description, sql_template: template },
                },
                { onSuccess: onClose },
              )
            }
          >
            {t('common.save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function QueriesPage() {
  const { t } = useTranslation();
  const queries = useAdminQueries();
  const remove = useDeleteQuery();
  const [editing, setEditing] = useState<{ query: NamedQuery | null } | null>(null);
  const [deleting, setDeleting] = useState<NamedQuery | null>(null);

  const columns: Column<NamedQuery>[] = [
    {
      key: 'db_type',
      header: t('connections.engine'),
      sortable: true,
      searchable: true,
      value: (q) => q.db_type,
      cell: (q) => q.db_type,
    },
    {
      key: 'name',
      header: t('admin.queries.name'),
      sortable: true,
      searchable: true,
      value: (q) => `${q.name} ${q.description}`,
      cell: (q) => (
        <>
          <Code>{q.name}</Code>
          {q.description && (
            <Text size="xs" c="dimmed">
              {q.description}
            </Text>
          )}
        </>
      ),
    },
    {
      key: 'params',
      header: t('admin.queries.params'),
      cell: (q) => (
        <Text size="sm" ff="monospace">
          {q.params.join(', ') || '—'}
        </Text>
      ),
    },
    {
      key: 'actions',
      header: t('common.actions'),
      hiddenHeader: true,
      cell: (query) => (
        <Group gap={4}>
          <Button
            size="xs"
            variant="light"
            onClick={() => setEditing({ query })}
            aria-label={t('admin.queries.editLabel', { name: query.name })}
          >
            {t('common.edit')}
          </Button>
          <Button
            size="xs"
            color="red"
            variant="light"
            onClick={() => setDeleting(query)}
            aria-label={t('admin.queries.deleteLabel', { name: query.name })}
          >
            {t('common.delete')}
          </Button>
        </Group>
      ),
    },
  ];

  return (
    <Stack maw={1000}>
      <Group justify="space-between">
        <Title order={2}>{t('admin.queries.title')}</Title>
        <Button onClick={() => setEditing({ query: null })}>{t('admin.queries.new')}</Button>
      </Group>
      <Text c="dimmed">{t('admin.queries.intro')}</Text>
      {queries.isPending && <Loader aria-label={t('common.loading')} />}
      {queries.isError && <ErrorAlert error={queries.error} />}
      {queries.data && queries.data.length === 0 && <Text c="dimmed">{t('admin.queries.empty')}</Text>}
      {queries.data && queries.data.length > 0 && (
        <DataTable
          mode="client"
          label={t('admin.queries.title')}
          searchLabel={t('admin.queries.search')}
          empty={t('table.noMatches')}
          columns={columns}
          rowKey={(query) => query.id}
          rows={queries.data}
        />
      )}
      {editing && (
        <QueryModal key={editing.query?.id ?? 'new'} query={editing.query} onClose={() => setEditing(null)} />
      )}
      <Modal
        opened={deleting !== null}
        onClose={() => setDeleting(null)}
        title={t('admin.queries.deleteTitle')}
      >
        {deleting && (
          <Stack>
            <Text>{t('admin.queries.deleteBody', { name: deleting.name, engine: deleting.db_type })}</Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setDeleting(null)}>
                {t('common.cancel')}
              </Button>
              <Button
                color="red"
                loading={remove.isPending}
                onClick={() => remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
              >
                {t('common.delete')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
