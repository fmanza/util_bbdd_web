import {
  Anchor,
  Badge,
  Button,
  Card,
  FileInput,
  Group,
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
import type { Column } from '../../components/tableState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatBytes, formatDateTime } from '../../components/format';
import {
  baseTemplateUrl,
  type DocumentTemplate,
  type TemplateScope,
  templateFileUrl,
  useDeleteTemplate,
  useTemplates,
  useUpdateTemplate,
  useUploadTemplate,
} from './useTemplates';

function UploadForm({ scope }: { scope: TemplateScope }) {
  const { t } = useTranslation();
  const upload = useUploadTemplate(scope);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  return (
    <Card withBorder>
      <Stack>
        <Title order={3}>{t('templates.upload')}</Title>
        {upload.isError && <ErrorAlert error={upload.error} />}
        <Group align="flex-end">
          <FileInput
            label={t('templates.file')}
            accept=".docx,.dotx,.xlsx,.xltx,.toml,.json"
            value={file}
            onChange={setFile}
            clearable
            w={280}
          />
          <TextInput
            label={t('templates.name')}
            description={t('templates.nameHint')}
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
            maxLength={100}
            w={240}
          />
          <Button
            disabled={!file}
            loading={upload.isPending}
            onClick={() =>
              file &&
              upload.mutate(
                { file, name },
                {
                  onSuccess: () => {
                    setFile(null);
                    setName('');
                  },
                },
              )
            }
          >
            {t('templates.send')}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}

function RenameModal({
  scope,
  template,
  onClose,
}: {
  scope: TemplateScope;
  template: DocumentTemplate;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const update = useUpdateTemplate(scope);
  const [name, setName] = useState(template.name);
  return (
    <Modal opened onClose={onClose} title={t('templates.renameTitle')}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          update.mutate({ id: template.id, name: name.trim() }, { onSuccess: onClose });
        }}
      >
        <Stack>
          {update.isError && <ErrorAlert error={update.error} />}
          <TextInput
            label={t('templates.name')}
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
            maxLength={100}
            required
            data-autofocus
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={update.isPending} disabled={!name.trim()}>
              {t('common.save')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

function TemplatesTable({
  scope,
  templates,
  canEdit,
}: {
  scope: TemplateScope;
  templates: DocumentTemplate[];
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  const update = useUpdateTemplate(scope);
  const remove = useDeleteTemplate(scope);
  const [renaming, setRenaming] = useState<DocumentTemplate | null>(null);
  const [deleting, setDeleting] = useState<DocumentTemplate | null>(null);
  // En un proyecto, las globales se ven y se descargan, pero las gestionan los admins.
  const editable = (template: DocumentTemplate) =>
    canEdit && (scope.kind === 'global' || template.scope === 'project');

  const columns: Column<DocumentTemplate>[] = [
    {
      key: 'name',
      header: t('templates.name'),
      sortable: true,
      searchable: true,
      value: (tpl) => `${tpl.name} ${tpl.filename}`,
      cell: (tpl) => (
        <>
          <Text size="sm">{tpl.name}</Text>
          <Text size="xs" c="dimmed">
            {tpl.filename} · {formatBytes(tpl.size_bytes)}
          </Text>
        </>
      ),
    },
    {
      key: 'kind',
      header: t('templates.kind'),
      sortable: true,
      value: (tpl) => t(`templates.kinds.${tpl.kind}`),
      cell: (tpl) => <Badge variant="light">{t(`templates.kinds.${tpl.kind}`)}</Badge>,
    },
    ...(scope.kind === 'project'
      ? [
          {
            key: 'scope',
            header: t('templates.scope'),
            sortable: true,
            value: (tpl: DocumentTemplate) => tpl.scope,
            cell: (tpl: DocumentTemplate) => (
              <Badge variant="outline" color={tpl.scope === 'global' ? 'gray' : 'blue'}>
                {t(`templates.scopes.${tpl.scope}`)}
              </Badge>
            ),
          },
        ]
      : []),
    {
      key: 'table_style',
      header: t('templates.tableStyle'),
      cell: (template) =>
        template.kind === 'trace' ? (
          // Un mapa de trazabilidad no tiene estilos de tabla.
          <Text size="sm">—</Text>
        ) : editable(template) ? (
          <NativeSelect
            size="xs"
            aria-label={t('templates.tableStyleOf', { name: template.name })}
            data={[
              // Sin estilo elegido: Word usa el de util_bbdd y Excel `TableStyleMedium2`.
              { value: '', label: t('templates.defaultStyle') },
              ...template.table_styles,
            ]}
            value={template.table_style ?? ''}
            disabled={update.isPending}
            onChange={(event) =>
              update.mutate({ id: template.id, table_style: event.currentTarget.value || null })
            }
          />
        ) : (
          <Text size="sm">{template.table_style ?? '—'}</Text>
        ),
    },
    {
      key: 'created_at',
      header: t('templates.created'),
      sortable: true,
      value: (tpl) => tpl.created_at,
      cell: (tpl) => (
        <Text size="sm">
          {formatDateTime(tpl.created_at)}
          {tpl.username ? ` · ${tpl.username}` : ''}
        </Text>
      ),
    },
    {
      key: 'actions',
      header: t('common.actions'),
      hiddenHeader: true,
      cell: (template) => (
        <Group gap={4} wrap="nowrap">
          <Button
            component="a"
            href={templateFileUrl(scope, template.id)}
            size="xs"
            variant="default"
            aria-label={t('templates.downloadLabel', { name: template.name })}
          >
            {t('templates.download')}
          </Button>
          {editable(template) && (
            <>
              <Button
                size="xs"
                variant="light"
                onClick={() => setRenaming(template)}
                aria-label={t('templates.renameLabel', { name: template.name })}
              >
                {t('templates.rename')}
              </Button>
              <Button
                size="xs"
                color="red"
                variant="light"
                onClick={() => setDeleting(template)}
                aria-label={t('templates.deleteLabel', { name: template.name })}
              >
                {t('common.delete')}
              </Button>
            </>
          )}
        </Group>
      ),
    },
  ];

  return (
    <Stack gap="xs">
      {update.isError && <ErrorAlert error={update.error} />}
      {remove.isError && <ErrorAlert error={remove.error} />}
      <DataTable
        mode="client"
        label={t('templates.title')}
        searchLabel={t('templates.search')}
        empty={t('table.noMatches')}
        columns={columns}
        rowKey={(template) => template.id}
        rows={templates}
        minWidth={760}
      />
      {renaming && (
        <RenameModal key={renaming.id} scope={scope} template={renaming} onClose={() => setRenaming(null)} />
      )}
      <Modal opened={deleting !== null} onClose={() => setDeleting(null)} title={t('templates.deleteTitle')}>
        {deleting && (
          <Stack>
            <Text>{t('templates.deleteBody', { name: deleting.name })}</Text>
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

/** Plantillas Word y Excel de la documentación (ADR-011): catálogo global (admins) o de un proyecto (editores). */
export function TemplatesPanel({ scope, canEdit }: { scope: TemplateScope; canEdit: boolean }) {
  const { t } = useTranslation();
  const templates = useTemplates(scope);
  return (
    <Stack>
      <Text c="dimmed">{t(scope.kind === 'global' ? 'templates.introGlobal' : 'templates.intro')}</Text>
      <Text size="sm" c="dimmed">
        {t('templates.limits')}
      </Text>
      <Group gap="md">
        <Text size="sm" fw={500}>
          {t('templates.base')}:
        </Text>
        <Anchor href={baseTemplateUrl('word')} size="sm">
          {t('templates.baseWord')}
        </Anchor>
        <Anchor href={baseTemplateUrl('excel')} size="sm">
          {t('templates.baseExcel')}
        </Anchor>
        <Anchor href={baseTemplateUrl('trace')} size="sm">
          {t('templates.baseTrace')}
        </Anchor>
      </Group>
      {canEdit ? (
        <UploadForm scope={scope} />
      ) : (
        <Text size="sm" c="dimmed">
          {t('templates.readOnly')}
        </Text>
      )}
      {templates.isPending && <Loader aria-label={t('common.loading')} />}
      {templates.isError && <ErrorAlert error={templates.error} />}
      {templates.data && templates.data.length === 0 && <Text c="dimmed">{t('templates.empty')}</Text>}
      {templates.data && templates.data.length > 0 && (
        <TemplatesTable scope={scope} templates={templates.data} canEdit={canEdit} />
      )}
    </Stack>
  );
}
