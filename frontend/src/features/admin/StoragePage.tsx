import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  NumberInput,
  Pagination,
  Progress,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatBytes } from '../../components/format';
import {
  type PurgePreview,
  type StorageKey,
  type StorageSettings,
  type StorageUpdate,
  USAGE_PAGE_SIZE,
  type Usage,
  usePreviewStorage,
  useRequestMaintenance,
  useStorageSettings,
  useStorageUsage,
  useUpdateStorage,
} from '../storage/useStorage';

/** Ajustes numéricos con su rango (el mismo que valida la API). */
const NUMBERS: { key: Exclude<StorageKey, 'quota_purge'>; min: number; max: number }[] = [
  { key: 'user_quota_mb', min: 0, max: 10_000_000 },
  { key: 'run_retention_days', min: 0, max: 3650 },
  { key: 'run_retention_per_project', min: 0, max: 100_000 },
  { key: 'upload_retention_days', min: 0, max: 365 },
];
/** Límites de la carga de ficheros (Fase 2 de ficheros grandes; mismos rangos que la API). */
const LIMITS: typeof NUMBERS = [
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

function SettingsForm({ settings }: { settings: StorageSettings }) {
  const { t } = useTranslation();
  const preview = usePreviewStorage();
  const update = useUpdateStorage();
  const maintenance = useRequestMaintenance();
  const [draft, setDraft] = useState<Draft>({});
  const [confirm, setConfirm] = useState<PurgePreview | null>(null);

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

  const body = draft as StorageUpdate;
  const dirty = Object.keys(draft).length > 0;
  const numberField = ({ key, min, max }: (typeof NUMBERS)[number]) => (
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

  return (
    <Card withBorder>
      <Stack>
        <Title order={3}>{t('storage.settingsTitle')}</Title>
        {(preview.isError || update.isError) && <ErrorAlert error={preview.error ?? update.error} />}
        <SimpleGrid cols={{ base: 1, sm: 2 }}>{NUMBERS.map(numberField)}</SimpleGrid>
        <Stack gap={4}>
          <Switch
            label={t('storage.fields.quota_purge')}
            description={`${t('storage.help.quota_purge')} ${hint('quota_purge')}`}
            checked={value('quota_purge') === true}
            onChange={(event) => set('quota_purge', event.currentTarget.checked)}
          />
          {resetButton('quota_purge')}
        </Stack>
        <Stack gap={2} maw={320}>
          <NumberInput
            label={t('storage.fields.quota_purge_target_pct')}
            description={`${t('storage.help.quota_purge_target_pct')} ${hint('quota_purge_target_pct')}`}
            min={10}
            max={95}
            suffix=" %"
            allowDecimal={false}
            disabled={value('quota_purge') !== true}
            value={value('quota_purge_target_pct') as number}
            onChange={(next) => typeof next === 'number' && set('quota_purge_target_pct', next)}
          />
          {resetButton('quota_purge_target_pct')}
        </Stack>
        <Title order={4}>{t('storage.uploadsTitle')}</Title>
        <Text size="sm" c="dimmed">
          {t('storage.uploadsIntro')}
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>{LIMITS.map(numberField)}</SimpleGrid>
        <Group justify="space-between">
          <Group gap="xs">
            <Button
              variant="default"
              loading={maintenance.isPending}
              onClick={() => maintenance.mutate()}
              disabled={dirty}
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
            <Button variant="default" disabled={!dirty} onClick={() => setDraft({})}>
              {t('common.cancel')}
            </Button>
            <Button
              disabled={!dirty}
              loading={preview.isPending}
              onClick={() => preview.mutate(body, { onSuccess: setConfirm })}
            >
              {t('common.save')}
            </Button>
          </Group>
        </Group>
      </Stack>
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
                  update.mutate(body, {
                    onSuccess: () => {
                      setDraft({});
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
    </Card>
  );
}

function usageColor(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return 'gray';
  if (pct >= 100) return 'red';
  return pct >= 80 ? 'yellow' : 'blue';
}

function UsageRow({ usage }: { usage: Usage }) {
  const { t } = useTranslation();
  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm">{usage.display_name}</Text>
        <Text size="xs" c="dimmed">
          {usage.username}
        </Text>
      </Table.Td>
      <Table.Td>{formatBytes(usage.used_bytes)}</Table.Td>
      <Table.Td>
        {usage.quota_bytes === null || usage.quota_bytes === undefined
          ? t('storage.unlimited')
          : formatBytes(usage.quota_bytes)}{' '}
        <Badge size="xs" variant="light" color={usage.quota_source === 'user' ? 'grape' : 'gray'}>
          {t(`storage.sources.${usage.quota_source}`)}
        </Badge>
      </Table.Td>
      <Table.Td miw={140}>
        {usage.used_pct === null || usage.used_pct === undefined ? (
          '—'
        ) : (
          <Group gap="xs" wrap="nowrap">
            <Progress
              value={Math.min(usage.used_pct, 100)}
              color={usageColor(usage.used_pct)}
              w={80}
              aria-label={t('storage.usedOf', { name: usage.username, pct: usage.used_pct })}
            />
            <Text size="xs">{usage.used_pct} %</Text>
          </Group>
        )}
      </Table.Td>
    </Table.Tr>
  );
}

function UsageTable() {
  const { t } = useTranslation();
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const usage = useStorageUsage(q.trim(), page);
  return (
    <Card withBorder>
      <Stack>
        <Title order={3}>{t('storage.usageTitle')}</Title>
        <TextInput
          label={t('storage.search')}
          value={q}
          onChange={(event) => {
            setQ(event.currentTarget.value);
            setPage(1);
          }}
          maxLength={64}
          w={280}
        />
        {usage.isPending && <Loader aria-label={t('common.loading')} />}
        {usage.isError && <ErrorAlert error={usage.error} />}
        {usage.data && usage.data.items.length === 0 && <Text c="dimmed">{t('storage.noUsers')}</Text>}
        {usage.data && usage.data.items.length > 0 && (
          <Table striped aria-label={t('storage.usageTitle')}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('storage.user')}</Table.Th>
                <Table.Th>{t('storage.used')}</Table.Th>
                <Table.Th>{t('storage.quota')}</Table.Th>
                <Table.Th>{t('storage.percent')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {usage.data.items.map((item) => (
                <UsageRow key={item.user_id} usage={item} />
              ))}
            </Table.Tbody>
          </Table>
        )}
        {usage.data && usage.data.total > USAGE_PAGE_SIZE && (
          <Pagination total={Math.ceil(usage.data.total / USAGE_PAGE_SIZE)} value={page} onChange={setPage} />
        )}
      </Stack>
    </Card>
  );
}

/** *Administración → Almacenamiento* (ADR-012): cuota, retención y purga por cuota, y el uso de cada usuario. */
export function StoragePage() {
  const { t } = useTranslation();
  const settings = useStorageSettings();
  return (
    <Stack maw={1100}>
      <Title order={2}>{t('storage.title')}</Title>
      <Text c="dimmed">{t('storage.intro')}</Text>
      {settings.isPending && <Loader aria-label={t('common.loading')} />}
      {settings.isError && <ErrorAlert error={settings.error} />}
      {settings.data && <SettingsForm settings={settings.data} />}
      <UsageTable />
    </Stack>
  );
}
