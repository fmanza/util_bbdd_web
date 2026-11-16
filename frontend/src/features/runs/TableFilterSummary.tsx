import { Alert, Code, Group, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import type { components } from '../../api/schema';

type TableFilter = components['schemas']['TableFilterOut'];

/** Nombres de la frontera que se listan (el resto se cuenta). */
const SHOWN = 30;

function Patterns({ label, patterns }: { label: string; patterns: string[] | undefined }) {
  if (!patterns?.length) return null;
  return (
    <Group gap={4}>
      <Text size="sm">{label}</Text>
      {patterns.map((pattern) => (
        <Code key={pattern}>{pattern}</Code>
      ))}
    </Group>
  );
}

/**
 * Filtro de tablas con que se planificó la migración o se preparó el volcado (util_bbdd 5.9.0) y, en el plan, la
 * frontera: tablas de fuera unidas por FK a las de dentro, que deben existir ya en el destino.
 */
export function TableFilterSummary({
  filter,
  frontier = [],
}: {
  filter: TableFilter | null | undefined;
  frontier?: string[] | undefined;
}) {
  const { t } = useTranslation();
  if (!filter) return null;
  return (
    <Alert variant="light" color="blue" title={t('runs.filterSummary.title')}>
      <Patterns label={t('runs.filterSummary.include')} patterns={filter.include} />
      <Patterns label={t('runs.filterSummary.exclude')} patterns={filter.exclude} />
      {frontier.length > 0 && (
        <Text size="sm" mt={4} style={{ wordBreak: 'break-word' }}>
          {t('runs.filterSummary.frontier', { count: frontier.length })} {frontier.slice(0, SHOWN).join(', ')}
          {frontier.length > SHOWN && ` ${t('runs.patterns.more', { count: frontier.length - SHOWN })}`}
        </Text>
      )}
    </Alert>
  );
}
