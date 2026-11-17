import { Group, Radio, Stack, Text, ThemeIcon } from '@mantine/core';
import {
  type Icon,
  IconArrowsDiff,
  IconDatabaseExport,
  IconFileDescription,
  IconHierarchy,
  IconPlayerPlay,
  IconStethoscope,
  IconTransform,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import type { Operation } from '../useRuns';
import { categorize } from './launchLayout';

const ICONS: Record<string, Icon> = {
  documentation: IconFileDescription,
  relationship_graph: IconHierarchy,
  compare: IconArrowsDiff,
  migrate_plan: IconTransform,
  dump_preview: IconDatabaseExport,
  noop: IconStethoscope,
};

/** Lista de operaciones agrupadas por intención: un `radiogroup` «Operación» con una tarjeta por operación. */
export function OperationRail({
  operations,
  value,
  onChange,
}: {
  operations: Operation[];
  value: string;
  onChange: (name: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <Radio.Group label={t('runs.operation')} value={value} onChange={onChange}>
      <Stack gap="md" mt="xs">
        {categorize(operations).map((category) => (
          <Stack key={category.key} gap={6}>
            <Text size="xs" fw={700} c="dimmed" tt="uppercase" aria-hidden>
              {t(`runs.launch.categories.${category.key}`)}
            </Text>
            {category.operations.map((op) => {
              const OperationIcon = ICONS[op.name] ?? IconPlayerPlay;
              const descriptionId = `operation-${op.name}-description`;
              return (
                <Radio.Card
                  key={op.name}
                  value={op.name}
                  p="xs"
                  aria-label={op.title}
                  aria-describedby={descriptionId}
                >
                  <Group wrap="nowrap" align="flex-start" gap="sm">
                    <ThemeIcon variant={value === op.name ? 'filled' : 'light'} size="md" aria-hidden>
                      <OperationIcon size={18} stroke={1.6} />
                    </ThemeIcon>
                    <div style={{ minWidth: 0 }}>
                      <Text size="sm" fw={600}>
                        {op.title}
                      </Text>
                      <Text id={descriptionId} size="xs" c="dimmed" lineClamp={3}>
                        {op.description}
                      </Text>
                    </div>
                  </Group>
                </Radio.Card>
              );
            })}
          </Stack>
        ))}
      </Stack>
    </Radio.Group>
  );
}
