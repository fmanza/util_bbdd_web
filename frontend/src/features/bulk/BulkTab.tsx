import {
  ActionIcon,
  Autocomplete,
  Button,
  Card,
  FileInput,
  Group,
  Loader,
  NativeSelect,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatBytes, formatDateTime } from '../../components/format';
import { useSchemas, useSchemaTree, useTable } from '../explorer/useExplorer';
import { type Project, useProjectConnections } from '../projects/useProjects';
import { useLaunchRun } from '../runs/useRuns';
import {
  type ReadOptions,
  suggestTarget,
  type Upload,
  useDeleteUpload,
  useUploadFile,
  useUploadInfo,
  useUploads,
} from './useBulk';

const NO_TARGET = '';
const OPERATIONS = ['insert', 'update', 'delete'] as const;

function UploadsList({ project, uploads }: { project: Project; uploads: Upload[] }) {
  const { t } = useTranslation();
  const remove = useDeleteUpload(project.id);
  if (uploads.length === 0) return <Text c="dimmed">{t('bulk.uploads.empty')}</Text>;
  return (
    <Stack gap="xs">
      {remove.isError && <ErrorAlert error={remove.error} />}
      <Table striped withTableBorder aria-label={t('bulk.uploads.title')}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('bulk.uploads.file')}</Table.Th>
            <Table.Th>{t('bulk.uploads.size')}</Table.Th>
            <Table.Th>{t('bulk.uploads.created')}</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {uploads.map((u) => (
            <Table.Tr key={u.id}>
              <Table.Td>{u.filename}</Table.Td>
              <Table.Td>{formatBytes(u.size_bytes)}</Table.Td>
              <Table.Td>
                {formatDateTime(u.created_at)}
                {u.username ? ` · ${u.username}` : ''}
              </Table.Td>
              <Table.Td>
                <ActionIcon
                  variant="subtle"
                  color="red"
                  aria-label={t('bulk.uploads.delete', { name: u.filename })}
                  onClick={() => remove.mutate(u.id)}
                >
                  ×
                </ActionIcon>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}

/** Pestaña *Carga* del proyecto (Fase 9): subir ficheros y lanzar la vista previa de una carga (ADR-010). */
export function BulkTab({ project }: { project: Project }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const uploads = useUploads(project.id);
  const send = useUploadFile(project.id);
  const connections = useProjectConnections(project.id);
  const launch = useLaunchRun(project.id);
  const [file, setFile] = useState<File | null>(null);
  const [uploadId, setUploadId] = useState('');
  const [alias, setAlias] = useState('');
  const [schema, setSchema] = useState('');
  const [table, setTable] = useState('');
  const [operation, setOperation] = useState<(typeof OPERATIONS)[number]>('insert');
  const [read, setRead] = useState<ReadOptions>({ sheet: null, delimiter: null, encoding: null });
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [isolate, setIsolate] = useState(false);
  const [parallel, setParallel] = useState(false);
  const [syncPk, setSyncPk] = useState(true);
  const [overrideIdentity, setOverrideIdentity] = useState(false);

  const info = useUploadInfo(project.id, uploadId || null, read);
  const connection = (connections.data ?? []).find((c) => c.alias === alias);
  const connectionId = connection?.connection_id ?? 0;
  const postgres = connection?.db_type === 'postgresql';
  // Schemas y tablas del destino para elegirlos (catálogo del explorador). Si la conexión no se puede explorar
  // (p. ej. privada de otro miembro), se siguen escribiendo a mano.
  const schemas = useSchemas(connectionId, Boolean(connection));
  const schemaOptions = useMemo(
    () => (schemas.data?.schemas ?? []).filter((s) => !s.system).map((s) => s.name),
    [schemas.data],
  );
  // Columnas de la tabla para los desplegables del mapeo; vacío = el schema de la conexión.
  // Con retardo para no consultar en cada tecla.
  const [lookupSchema] = useDebouncedValue(schema.trim() || (schemas.data?.default ?? ''), 500);
  const [lookupTable] = useDebouncedValue(table.trim(), 500);
  const tree = useSchemaTree(connectionId, connection && lookupSchema ? lookupSchema : null);
  const tableOptions = useMemo(() => (tree.data?.tables ?? []).map((item) => item.name), [tree.data]);
  const detail = useTable(
    connectionId,
    connection && lookupSchema ? lookupSchema : null,
    lookupTable || null,
  );
  const tableColumns = useMemo(() => (detail.data?.columns ?? []).map((c) => c.name), [detail.data]);
  const fileColumns = useMemo(() => info.data?.columns ?? [], [info.data]);

  // Mapeo efectivo: lo elegido por el usuario o, si no, la propuesta por nombre.
  const mapping = useMemo(
    () =>
      Object.fromEntries(
        fileColumns.map((c) => [
          c,
          overrides[c] ?? (tableColumns.length ? suggestTarget(c, tableColumns) : c),
        ]),
      ),
    [fileColumns, tableColumns, overrides],
  );
  const setMapping = (column: string, target: string) => setOverrides({ ...overrides, [column]: target });

  const ready = Boolean(uploadId && alias && table.trim() && info.data);
  const submit = () =>
    launch.mutate(
      {
        operation: 'bulk_preview',
        params: {
          upload: uploadId,
          target_connection: alias,
          ...(schema.trim() ? { target_schema: schema.trim() } : {}),
          table: table.trim(),
          operation,
          mapping: Object.fromEntries(Object.entries(mapping).filter(([, target]) => target !== NO_TARGET)),
          ...(read.sheet ? { sheet: read.sheet } : {}),
          ...(read.delimiter ? { delimiter: read.delimiter } : {}),
          ...(read.encoding ? { encoding: read.encoding } : {}),
          on_error: isolate ? 'isolate' : 'raise',
          parallel,
          // Solo en un insert; `override_identity` solo en PostgreSQL (GENERATED ALWAYS AS IDENTITY).
          ...(operation === 'insert'
            ? { sync_pk_sequences: syncPk, override_identity: postgres && overrideIdentity }
            : {}),
        },
      },
      { onSuccess: (run) => void navigate(`/runs/${run.id}`) },
    );

  return (
    <Stack>
      <Card withBorder>
        <Stack>
          <Title order={3}>{t('bulk.uploads.title')}</Title>
          <Text size="sm" c="dimmed">
            {t('bulk.uploads.hint')}
          </Text>
          {send.isError && <ErrorAlert error={send.error} />}
          <Group align="flex-end">
            <FileInput
              label={t('bulk.uploads.choose')}
              accept=".csv,.xlsx"
              value={file}
              onChange={setFile}
              clearable
              w={320}
            />
            <Button
              disabled={!file}
              loading={send.isPending}
              onClick={() =>
                file &&
                send.mutate(file, {
                  onSuccess: (created) => {
                    setFile(null);
                    setUploadId(created.id);
                  },
                })
              }
            >
              {t('bulk.uploads.send')}
            </Button>
          </Group>
          {uploads.isError && <ErrorAlert error={uploads.error} />}
          {uploads.data && <UploadsList project={project} uploads={uploads.data} />}
        </Stack>
      </Card>

      <Card withBorder>
        <Stack>
          <Title order={3}>{t('bulk.form.title')}</Title>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <NativeSelect
              label={t('bulk.form.file')}
              value={uploadId}
              onChange={(event) => setUploadId(event.currentTarget.value)}
              data={[
                { value: '', label: t('bulk.form.chooseFile') },
                ...(uploads.data ?? []).map((u) => ({ value: u.id, label: u.filename })),
              ]}
            />
            <NativeSelect
              label={t('bulk.form.operation')}
              value={operation}
              onChange={(event) => setOperation(event.currentTarget.value as (typeof OPERATIONS)[number])}
              data={OPERATIONS.map((op) => ({ value: op, label: t(`bulk.operations.${op}`) }))}
            />
            <NativeSelect
              label={t('bulk.form.connection')}
              value={alias}
              onChange={(event) => {
                setAlias(event.currentTarget.value);
                setSchema('');
                setTable('');
                setOverrides({});
              }}
              data={[
                { value: '', label: t('bulk.form.chooseConnection') },
                ...(connections.data ?? []).map((c) => ({
                  value: c.alias,
                  label: `${c.alias} · ${c.connection_name}${c.read_only ? ` (${t('bulk.form.readOnly')})` : ''}`,
                })),
              ]}
            />
            <Autocomplete
              label={t('bulk.form.schema')}
              description={schemas.isError ? t('bulk.form.catalogUnavailable') : t('bulk.form.schemaHint')}
              placeholder={schemas.data?.default ?? undefined}
              data={schemaOptions}
              value={schema}
              onChange={(value) => {
                setSchema(value);
                setTable('');
                setOverrides({});
              }}
              rightSection={schemas.isFetching ? <Loader size="xs" /> : null}
            />
            <Autocomplete
              label={t('bulk.form.table')}
              description={
                tree.isError
                  ? t('bulk.form.catalogUnavailable')
                  : tree.data && tableOptions.length === 0
                    ? t('bulk.form.noTables')
                    : undefined
              }
              data={tableOptions}
              value={table}
              onChange={(value) => {
                setTable(value);
                setOverrides({});
              }}
              rightSection={tree.isFetching ? <Loader size="xs" /> : null}
            />
            {info.data?.sheets ? (
              <NativeSelect
                label={t('bulk.form.sheet')}
                description={t('bulk.form.sheetHint')}
                value={read.sheet ?? ''}
                onChange={(event) => setRead({ ...read, sheet: event.currentTarget.value || null })}
                data={info.data.sheets.map((s) => ({ value: s, label: s }))}
              />
            ) : (
              <Stack gap={4}>
                <Group grow>
                  <NativeSelect
                    label={t('bulk.form.delimiter')}
                    value={read.delimiter ?? ''}
                    onChange={(event) => setRead({ ...read, delimiter: event.currentTarget.value || null })}
                    data={[
                      { value: '', label: t('bulk.form.auto', { value: info.data?.delimiter ?? '' }) },
                      { value: ',', label: ',' },
                      { value: ';', label: ';' },
                      { value: '\t', label: t('bulk.form.tab') },
                      { value: '|', label: '|' },
                    ]}
                  />
                  <NativeSelect
                    label={t('bulk.form.encoding')}
                    value={read.encoding ?? ''}
                    onChange={(event) => setRead({ ...read, encoding: event.currentTarget.value || null })}
                    data={[
                      { value: '', label: t('bulk.form.auto', { value: info.data?.encoding ?? '' }) },
                      { value: 'utf-8', label: 'UTF-8' },
                      { value: 'cp1252', label: 'Windows-1252' },
                      { value: 'latin-1', label: 'Latin-1' },
                    ]}
                  />
                </Group>
                <Text size="xs" c="dimmed">
                  {t('bulk.form.readHint')}
                </Text>
              </Stack>
            )}
          </SimpleGrid>
          {info.isError && <ErrorAlert error={info.error} />}
          {fileColumns.length > 0 && (
            <Stack gap="xs">
              <Title order={4}>{t('bulk.form.mapping')}</Title>
              <Text size="sm" c="dimmed">
                {tableColumns.length ? t('bulk.form.mappingHint') : t('bulk.form.mappingFree')}
                {operation === 'insert' && ` ${t('bulk.form.pkHint')}`}
              </Text>
              <Table withTableBorder aria-label={t('bulk.form.mapping')}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('bulk.form.fileColumn')}</Table.Th>
                    <Table.Th>{t('bulk.form.example')}</Table.Th>
                    <Table.Th>{t('bulk.form.tableColumn')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {fileColumns.map((column, index) => (
                    <Table.Tr key={column}>
                      <Table.Td>{column}</Table.Td>
                      <Table.Td>{info.data?.sample[0]?.[index] ?? ''}</Table.Td>
                      <Table.Td>
                        {tableColumns.length ? (
                          <NativeSelect
                            aria-label={t('bulk.form.targetFor', { column })}
                            value={mapping[column] ?? NO_TARGET}
                            onChange={(event) => setMapping(column, event.currentTarget.value)}
                            data={[
                              { value: NO_TARGET, label: t('bulk.form.skip') },
                              ...tableColumns.map((c) => ({ value: c, label: c })),
                            ]}
                          />
                        ) : (
                          <TextInput
                            aria-label={t('bulk.form.targetFor', { column })}
                            value={mapping[column] ?? ''}
                            onChange={(event) => setMapping(column, event.currentTarget.value)}
                          />
                        )}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Stack>
          )}
          <Group>
            <Switch
              label={t('bulk.form.isolate')}
              checked={isolate}
              onChange={(event) => setIsolate(event.currentTarget.checked)}
            />
            <Switch
              label={t('bulk.form.parallel')}
              description={t('bulk.form.parallelHint')}
              checked={parallel}
              onChange={(event) => setParallel(event.currentTarget.checked)}
            />
            {operation === 'insert' && (
              <Switch
                label={t('bulk.form.syncPk')}
                description={t('bulk.form.syncPkHint')}
                checked={syncPk}
                onChange={(event) => setSyncPk(event.currentTarget.checked)}
              />
            )}
            {operation === 'insert' && postgres && (
              <Switch
                label={t('bulk.form.overrideIdentity')}
                description={t('bulk.form.overrideIdentityHint')}
                checked={overrideIdentity}
                onChange={(event) => setOverrideIdentity(event.currentTarget.checked)}
              />
            )}
          </Group>
          {launch.isError && <ErrorAlert error={launch.error} />}
          <Group justify="flex-end">
            <Button disabled={!ready} loading={launch.isPending} onClick={submit}>
              {t('bulk.form.preview')}
            </Button>
          </Group>
        </Stack>
      </Card>
    </Stack>
  );
}
