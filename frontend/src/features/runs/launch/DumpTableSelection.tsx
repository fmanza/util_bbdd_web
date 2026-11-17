import { SegmentedControl, Stack, Text } from '@mantine/core';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { type DumpMode, DUMP_MODES } from './dumpMode';

/** Selector «Todas / Lista exacta / Patrones» del volcado y los campos del modo elegido. */
export function DumpTableSelection({
  mode,
  onModeChange,
  children,
}: {
  mode: DumpMode;
  onModeChange: (mode: DumpMode) => void;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <Stack gap="sm" style={{ gridColumn: '1 / -1' }}>
      <SegmentedControl
        aria-label={t('runs.launch.dumpMode.label')}
        value={mode}
        onChange={(next) => onModeChange(next as DumpMode)}
        data={DUMP_MODES.map((value) => ({ value, label: t(`runs.launch.dumpMode.${value}`) }))}
        style={{ alignSelf: 'flex-start' }}
      />
      {mode === 'all' ? (
        <Text size="sm" c="dimmed">
          {t('runs.launch.dumpMode.allHint')}
        </Text>
      ) : (
        children
      )}
    </Stack>
  );
}
