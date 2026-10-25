import { Alert, Card, Group, List, Loader, Progress, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatBytes } from '../../components/format';
import { useMyStorage } from './useStorage';

/** Aviso a partir de este porcentaje de la cuota. */
const NEAR_LIMIT = 80;

/** «Mi espacio» (ADR-012): el espacio del usuario de la sesión frente a su cuota. */
export function MyStoragePage() {
  const { t } = useTranslation();
  const storage = useMyStorage();
  const data = storage.data;
  const pct = data?.used_pct ?? null;

  return (
    <Stack maw={640}>
      <Title order={2}>{t('storage.mine.title')}</Title>
      {storage.isPending && <Loader aria-label={t('common.loading')} />}
      {storage.isError && <ErrorAlert error={storage.error} />}
      {data && (
        <Card withBorder>
          <Stack>
            {data.quota_bytes === null || data.quota_bytes === undefined ? (
              <Text>{t('storage.mine.unlimited', { used: formatBytes(data.used_bytes) })}</Text>
            ) : (
              <Stack gap={4}>
                <Group justify="space-between">
                  <Text>
                    {t('storage.mine.usedOf', {
                      used: formatBytes(data.used_bytes),
                      quota: formatBytes(data.quota_bytes),
                    })}
                  </Text>
                  <Text fw={600}>{pct} %</Text>
                </Group>
                <Progress
                  value={Math.min(pct ?? 0, 100)}
                  color={(pct ?? 0) >= 100 ? 'red' : (pct ?? 0) >= NEAR_LIMIT ? 'yellow' : 'blue'}
                  aria-label={t('storage.mine.progress', { pct })}
                />
                <Text size="xs" c="dimmed">
                  {t(`storage.mine.source.${data.quota_source}`)}
                </Text>
              </Stack>
            )}
            <List size="sm">
              <List.Item>{t('storage.mine.runs', { bytes: formatBytes(data.run_bytes) })}</List.Item>
              <List.Item>{t('storage.mine.uploads', { bytes: formatBytes(data.upload_bytes) })}</List.Item>
            </List>
            {pct !== null && pct >= NEAR_LIMIT && (
              <Alert color={pct >= 100 ? 'red' : 'yellow'} title={t('storage.mine.nearTitle')}>
                {t('storage.mine.nearBody')}
              </Alert>
            )}
            {data.quota_purge && data.quota_bytes !== null && (
              <Alert color="blue" title={t('storage.mine.purgeTitle')}>
                {t('storage.mine.purgeBody', { pct: data.quota_purge_target_pct })}
              </Alert>
            )}
          </Stack>
        </Card>
      )}
    </Stack>
  );
}
