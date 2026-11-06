import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  NumberInput,
  Progress,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  Title,
} from '@mantine/core';
import { type ReactNode, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { DataTable } from '../../components/DataTable';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatBytes } from '../../components/format';
import type { Column } from '../../components/tableState';
import { useListState } from '../../components/useListState';
import {
  type PurgePreview,
  type StorageKey,
  type StorageSettings,
  type StorageUpdate,
  type Usage,
  usePreviewStorage,
  useRequestMaintenance,
  useStorageSettings,
  useStorageUsage,
  useUpdateStorage,
} from '../storage/useStorage';

/** Ajuste numérico con su rango (el mismo que valida la API). */
type NumberSpec = { key: Exclude<StorageKey, 'quota_purge'>; min: number; max: number };

/** Cuota y retención: los aplica el worker en su pasada (o con «Aplicar ahora»). */
const NUMBERS: NumberSpec[] = [
  { key: 'user_quota_mb', min: 0, max: 10_000_000 },
  { key: 'run_retention_days', min: 0, max: 3650 },
  { key: 'run_retention_per_project', min: 0, max: 100_000 },
  { key: 'upload_retention_days', min: 0, max: 365 },
];
/** Límites de la carga de ficheros (Fase 2 de ficheros grandes): se aplican al guardar y no purgan nada. */
const LIMITS: NumberSpec[] = [
  { key: 'upload_max_mb', min: 1, max: 2048 },
  { key: 'upload_max_uncompressed_mb', min: 1, max: 8192 },
  { key: 'bulk_max_rows', min: 1, max: 50_000_000 },
];
const ENV: Record<StorageKey, string> = {
  user_quota_mb: 'UBW_USER_QUOTA_MB',
  run_retention_days: 'UBW_RUN_RETENTION_DAYS',
  run_retention_per_project: 'UBW_RUN_RETENTION_PER_PROJECT',
  upload_retention_days: 'UBW_UPLOAD_RETENTION_DAYS',
  quota_purge: 'UBW_QUOTA_PURGE',
  quota_purge_target_pct: 'UBW_QUOTA_PURGE_TARGET_PCT',
  upload_max_mb: 'UBW_UPLOAD_MAX_MB',
  upload_max_uncompressed_mb: 'UBW_UPLOAD_MAX_UNCOMPRESSED_MB',
  bulk_max_rows: 'UBW_BULK_MAX_ROWS',
};

/** Cambios pendientes: un valor nuevo o `null` (volver a la variable `UBW_*`). */
type Draft = Partial<Record<StorageKey, number | boolean | null>>;

/** Borrador de una tarjeta de ajustes: valor efectivo, pista de su variable `UBW_*`, «Restablecer» y campo numérico. */
function useSettingsDraft(settings: StorageSettings) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<Draft>({});

  const value = (key: StorageKey) => {
    const pending = draft[key];
    if (pending === undefined) return settings[key].value;
    return pending ?? settings[key].default;
  };
  const set = (key: StorageKey, next: number | boolean | null) => setDraft({ ...draft, [key]: next });
  const hint = (key: StorageKey) => {
    const fallback = settings[key].default;
    const shown = typeof fallback === 'boolean' ? t(fallback ? 'common.yes' : 'common.no') : String(fallback);
    return t('storage.defaultHint', { value: shown, env: ENV[key] });
  };
  const resetButton = (key: StorageKey) =>
    settings[key].overridden && draft[key] !== null ? (
      <Button
        size="compact-xs"
        variant="subtle"
        onClick={() => set(key, null)}
        aria-label={t('storage.resetLabel', { field: t(`storage.fields.${key}`) })}
      >
        {t('storage.reset')}
      </Button>
    ) : draft[key] === null ? (
      <Text size="xs" c="dimmed">
        {t('storage.willReset')}
      </Text>
    ) : null;
  const numberField = ({ key, min, max }: NumberSpec) => (
    <Stack key={key} gap={2}>
      <NumberInput
        label={t(`storage.fields.${key}`)}
        description={`${t(`storage.help.${key}`)} ${hint(key)}`}
        min={min}
        max={max}
        allowDecimal={false}
        allowNegative={false}
        thousandSeparator="."
        decimalSeparator=","
        value={value(key) as number}
        onChange={(next) => typeof next === 'number' && set(key, next)}
      />
      {resetButton(key)}
    </Stack>
  );

  return {
    body: draft as StorageUpdate,
    dirty: Object.keys(draft).length > 0,
    clear: () => setDraft({}),
    value,
    set,
    hint,
    resetButton,
    numberField,
  };
}

/** Tarjeta con su título como nombre accesible de la región. */
function SettingsCard({ title, children }: { title: string; children: ReactNode }) {
  const titleId = useId();
  return (
    <Card withBorder component="section" aria-labelledby={titleId}>
      <Stack>
        <Title order={3} id={titleId}>
          {title}
        </Title>
        {children}
      </Stack>
    </Card>
  );
}

/** Cuota, retención y purga: guardar enseña antes qué se purgará; «Aplicar ahora» pide la pasada al worker. */
function RetentionForm({ settings }: { settings: StorageSettings }) {
  const { t } = useTranslation();
  const preview = usePreviewStorage();
  const update = useUpdateStorage();
  const maintenance = useRequestMaintenance();
  const form = useSettingsDraft(settings);
  const [confirm, setConfirm] = useState<PurgePreview | null>(null);

  return (
    <SettingsCard title={t('storage.settingsTitle')}>
      {(preview.isError || update.isError) && <ErrorAlert error={preview.error ?? update.error} />}
      <SimpleGrid cols={{ base: 1, sm: 2 }}>{NUMBERS.map(form.numberField)}</SimpleGrid>
      <Stack gap={4}>
        <Switch
          label={t('storage.fields.quota_purge')}
          description={`${t('storage.help.quota_purge')} ${form.hint('quota_purge')}`}
          checked={form.value('quota_purge') === true}
          onChange={(event) => form.set('quota_purge', event.currentTarget.checked)}
        />
        {form.resetButton('quota_purge')}
      </Stack>
      <Stack gap={2} maw={320}>
        <NumberInput
          label={t('storage.fields.quota_purge_target_pct')}
          description={`${t('storage.help.quota_purge_target_pct')} ${form.hint('quota_purge_target_pct')}`}
          min={10}
          max={95}
          suffix=" %"
          allowDecimal={false}
          disabled={form.value('quota_purge') !== true}
          value={form.value('quota_purge_target_pct') as number}
          onChange={(next) => typeof next === 'number' && form.set('quota_purge_target_pct', next)}
        />
        {form.resetButton('quota_purge_target_pct')}
      </Stack>
      <Group justify="space-between">
        <Group gap="xs">
          <Button
            variant="default"
            loading={maintenance.isPending}
            onClick={() => maintenance.mutate()}
            disabled={form.dirty}
          >
            {t('storage.applyNow')}
          </Button>
          {maintenance.isSuccess && (
            <Text size="sm" c="dimmed" role="status">
              {t('storage.applyRequested')}
            </Text>
          )}
        </Group>
        <Group gap="xs">
          <Button variant="default" disabled={!form.dirty} onClick={form.clear}>
            {t('common.cancel')}
          </Button>
          <Button
            disabled={!form.dirty}
            loading={preview.isPending}
            onClick={() => preview.mutate(form.body, { onSuccess: setConfirm })}
          >
            {t('common.save')}
          </Button>
        </Group>
      </Group>
      <Modal opened={confirm !== null} onClose={() => setConfirm(null)} title={t('storage.confirmTitle')}>
        {confirm && (
          <Stack>
            {confirm.runs + confirm.uploads > 0 ? (
              <Alert color="yellow">
                {t('storage.confirmPurge', {
                  runs: confirm.runs,
                  runBytes: formatBytes(confirm.run_bytes),
                  uploads: confirm.uploads,
                  uploadBytes: formatBytes(confirm.upload_bytes),
                  users: confirm.users,
                })}
              </Alert>
            ) : (
              <Text>{t('storage.confirmNothing')}</Text>
            )}
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setConfirm(null)}>
                {t('common.cancel')}
              </Button>
              <Button
                loading={update.isPending}
                onClick={() =>
                  update.mutate(form.body, {
                    onSuccess: () => {
                      form.clear();
                      setConfirm(null);
                    },
                  })
                }
              >
                {t('storage.confirm')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </SettingsCard>
  );
}

/** Límites de la carga: no purgan nada, así que se guardan sin vista previa. */
function UploadLimitsForm({ settings }: { settings: StorageSettings }) {
  const { t } = useTranslation();
  const update = useUpdateStorage();
  const form = useSettingsDraft(settings);

  return (
    <SettingsCard title={t('storage.uploadsTitle')}>
      <Text size="sm" c="dimmed">
        {t('storage.uploadsIntro')}
      </Text>
      {update.isError && <ErrorAlert error={update.error} />}
      <SimpleGrid cols={{ base: 1, sm: 2 }}>{LIMITS.map(form.numberField)}</SimpleGrid>
      <Group justify="space-between">
        {update.isSuccess && !form.dirty ? (
          <Text size="sm" c="dimmed" role="status">
            {t('storage.uploadsSaved')}
          </Text>
        ) : (
          <span />
        )}
        <Group gap="xs">
          <Button variant="default" disabled={!form.dirty} onClick={form.clear}>
            {t('common.cancel')}
          </Button>
          <Button
            disabled={!form.dirty}
            loading={update.isPending}
            onClick={() => update.mutate(form.body, { onSuccess: form.clear })}
          >
            {t('common.save')}
          </Button>
        </Group>
      </Group>
    </SettingsCard>
  );
}

function usageColor(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return 'gray';
  if (pct >= 100) return 'red';
  return pct >= 80 ? 'yellow' : 'blue';
}

function UsageTable() {
  const { t } = useTranslation();
  const list = useListState();
  const usage = useStorageUsage(list.state);
  const columns: Column<Usage>[] = [
    {
      key: 'username',
      header: t('storage.user'),
      sortable: true,
      cell: (u) => (
        <>
          <Text size="sm">{u.display_name}</Text>
          <Text size="xs" c="dimmed">
            {u.username}
          </Text>
        </>
      ),
    },
    { key: 'used_bytes', header: t('storage.used'), sortable: true, cell: (u) => formatBytes(u.used_bytes) },
    {
      key: 'quota_bytes',
      header: t('storage.quota'),
      sortable: true,
      cell: (u) => (
        <>
          {u.quota_bytes === null || u.quota_bytes === undefined
            ? t('storage.unlimited')
            : formatBytes(u.quota_bytes)}{' '}
          <Badge size="xs" variant="light" color={u.quota_source === 'user' ? 'grape' : 'gray'}>
            {t(`storage.sources.${u.quota_source}`)}
          </Badge>
        </>
      ),
    },
    {
      key: 'used_pct',
      header: t('storage.percent'),
      sortable: true,
      cell: (u) =>
        u.used_pct === null || u.used_pct === undefined ? (
          '—'
        ) : (
          <Group gap="xs" wrap="nowrap" miw={140}>
            <Progress
              value={Math.min(u.used_pct, 100)}
              color={usageColor(u.used_pct)}
              w={80}
              aria-label={t('storage.usedOf', { name: u.username, pct: u.used_pct })}
            />
            <Text size="xs">{u.used_pct} %</Text>
          </Group>
        ),
    },
  ];
  return (
    <Card withBorder>
      <Stack>
        <Title order={3}>{t('storage.usageTitle')}</Title>
        {usage.isPending && <Loader aria-label={t('common.loading')} />}
        {usage.isError && <ErrorAlert error={usage.error} />}
        {usage.data && (
          <DataTable
            mode="server"
            label={t('storage.usageTitle')}
            searchLabel={t('storage.search')}
            empty={t('storage.noUsers')}
            columns={columns}
            rowKey={(u) => u.user_id}
            rows={usage.data.items}
            total={usage.data.total}
            {...list.table}
          />
        )}
      </Stack>
    </Card>
  );
}

/** *Administración → Almacenamiento* (ADR-012): cuota y retención, límites de la carga y uso de cada usuario. */
export function StoragePage() {
  const { t } = useTranslation();
  const settings = useStorageSettings();
  return (
    <Stack maw={1100}>
      <Title order={2}>{t('storage.title')}</Title>
      <Text c="dimmed">{t('storage.intro')}</Text>
      {settings.isPending && <Loader aria-label={t('common.loading')} />}
      {settings.isError && <ErrorAlert error={settings.error} />}
      {settings.data && (
        <>
          <RetentionForm settings={settings.data} />
          <UploadLimitsForm settings={settings.data} />
        </>
      )}
      <UsageTable />
    </Stack>
  );
}
