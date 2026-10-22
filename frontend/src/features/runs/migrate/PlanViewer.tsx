import {
  Accordion,
  Alert,
  Badge,
  Card,
  Group,
  Loader,
  NativeSelect,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../../components/ErrorAlert';
import type { RunDetail } from '../useRuns';
import { ApplyPanel } from './ApplyPanel';
import { SqlBlock } from './SqlBlock';
import { type FkMismatch, type MigrationPlan, type PlanWarning, usePlan } from './useMigrate';

const SEVERITY_COLORS: Record<PlanWarning['severity'], string> = {
  ERROR: 'red',
  WARNING: 'yellow',
  INFO: 'gray',
};
const STATEMENTS_SHOWN = 200;

function Stat({ label, value, color }: { label: string; value: number; color?: string | undefined }) {
  return (
    <Card withBorder padding="sm">
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700} size="xl" {...(color ? { c: color } : {})}>
        {value}
      </Text>
    </Card>
  );
}

export function FkMismatches({ items, blocking }: { items: FkMismatch[]; blocking: boolean }) {
  const { t } = useTranslation();
  if (items.length === 0) return null;
  return (
    <Alert
      color={blocking ? 'red' : 'yellow'}
      title={t(blocking ? 'migrate.fk.blockingTitle' : 'migrate.fk.title')}
    >
      <Stack gap="xs">
        <Text size="sm">{t(blocking ? 'migrate.fk.blocking' : 'migrate.fk.warning')}</Text>
        <Table withTableBorder aria-label={t('migrate.fk.title')}>
          <Table.Tbody>
            {items.map((m) => (
              <Table.Tr key={`${m.table}.${m.column}.${m.foreign_key}`}>
                <Table.Td>
                  {m.table}.{m.column} ({m.column_type})
                </Table.Td>
                <Table.Td>→</Table.Td>
                <Table.Td>
                  {m.ref_table}.{m.ref_column} ({m.ref_type})
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Stack>
    </Alert>
  );
}

function Warnings({ warnings }: { warnings: PlanWarning[] }) {
  const { t } = useTranslation();
  const [severity, setSeverity] = useState<PlanWarning['severity'] | 'all'>('all');
  const visible = warnings.filter((w) => severity === 'all' || w.severity === severity);
  if (warnings.length === 0) return <Text c="dimmed">{t('migrate.noWarnings')}</Text>;
  return (
    <Stack>
      <NativeSelect
        label={t('migrate.severity')}
        value={severity}
        onChange={(event) => setSeverity(event.currentTarget.value as PlanWarning['severity'] | 'all')}
        data={[
          { value: 'all', label: t('migrate.allSeverities') },
          ...(['ERROR', 'WARNING', 'INFO'] as const).map((s) => ({
            value: s,
            label: t(`migrate.severities.${s}`),
          })),
        ]}
        w={220}
      />
      <Table striped withTableBorder aria-label={t('migrate.tabs.warnings')}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('migrate.severity')}</Table.Th>
            <Table.Th>{t('migrate.object')}</Table.Th>
            <Table.Th>{t('migrate.category')}</Table.Th>
            <Table.Th>{t('migrate.message')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {visible.map((w, index) => (
            <Table.Tr key={index}>
              <Table.Td>
                <Badge color={SEVERITY_COLORS[w.severity]} variant="light">
                  {t(`migrate.severities.${w.severity}`)}
                </Badge>
              </Table.Td>
              <Table.Td>{w.column ? `${w.table}.${w.column}` : w.table}</Table.Td>
              <Table.Td>{w.category}</Table.Td>
              <Table.Td>{w.message}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}

function Tables({ plan }: { plan: MigrationPlan }) {
  const { t } = useTranslation();
  return (
    <Accordion multiple variant="separated">
      {(plan.tables ?? []).map((table) => (
        <Accordion.Item key={table.name} value={table.name}>
          <Accordion.Control>
            <Group gap="sm">
              <Text fw={500}>{table.name}</Text>
              <Text size="sm" c="dimmed">
                {t('migrate.columnsCount', { count: table.columns?.length ?? 0 })}
              </Text>
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <Table striped withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('migrate.column')}</Table.Th>
                  <Table.Th>{t('migrate.sourceType')}</Table.Th>
                  <Table.Th>{t('migrate.targetType')}</Table.Th>
                  <Table.Th>{t('migrate.nullable')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {(table.columns ?? []).map((col) => (
                  <Table.Tr key={col.name}>
                    <Table.Td>
                      {col.name}
                      {table.primary_key?.includes(col.name) ? ' (PK)' : ''}
                      {col.omit ? ` — ${t('migrate.omitted')}` : ''}
                    </Table.Td>
                    <Table.Td>{col.source_type}</Table.Td>
                    <Table.Td>{col.target_type}</Table.Td>
                    <Table.Td>{col.nullable ? t('common.yes') : t('common.no')}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Accordion.Panel>
        </Accordion.Item>
      ))}
    </Accordion>
  );
}

function Statements({ statements }: { statements: string[] }) {
  const { t } = useTranslation();
  return (
    <Stack>
      {statements.slice(0, STATEMENTS_SHOWN).map((statement, index) => (
        <Stack key={index} gap={2}>
          <Text size="xs" c="dimmed">
            {t('migrate.statementN', { n: index + 1, total: statements.length })}
          </Text>
          <SqlBlock code={statement} maxHeight={240} />
        </Stack>
      ))}
      {statements.length > STATEMENTS_SHOWN && (
        <Text size="sm" c="dimmed">
          {t('migrate.moreStatements', { count: statements.length - STATEMENTS_SHOWN })}
        </Text>
      )}
    </Stack>
  );
}

/** Visor de un plan `migrate_plan` y panel para aplicarlo (Fase 7, ADR-008). */
export function PlanViewer({ run }: { run: RunDetail }) {
  const { t } = useTranslation();
  const plan = usePlan(run.id, true);
  return (
    <Card withBorder>
      <Stack>
        <Title order={3}>{t('migrate.title')}</Title>
        {plan.isPending && <Loader size="sm" aria-label={t('common.loading')} />}
        {plan.isError && <ErrorAlert error={plan.error} />}
        {plan.data && (
          <>
            <Text size="sm">
              {t('migrate.route', {
                source: plan.data.source_engine,
                schema: plan.data.source_schema,
                target: plan.data.target_engine,
              })}
            </Text>
            <SimpleGrid cols={{ base: 2, sm: 5 }}>
              <Stat label={t('migrate.stats.tables')} value={plan.data.tables?.length ?? 0} />
              <Stat label={t('migrate.stats.statements')} value={plan.data.statements.length} />
              <Stat
                label={t('migrate.severities.ERROR')}
                value={plan.data.error_count}
                color={plan.data.error_count ? 'red' : undefined}
              />
              <Stat label={t('migrate.severities.WARNING')} value={plan.data.warning_count} />
              <Stat label={t('migrate.severities.INFO')} value={plan.data.info_count} />
            </SimpleGrid>
            {plan.data.error_count > 0 && (
              <Alert color="red" title={t('migrate.blockedTitle')}>
                {t('migrate.blocked')}
              </Alert>
            )}
            <FkMismatches items={plan.data.fk_mismatches ?? []} blocking={plan.data.fk_blocking ?? false} />
            <Tabs defaultValue="warnings" keepMounted={false}>
              <Tabs.List>
                <Tabs.Tab value="warnings">
                  {t('migrate.tabs.warnings')} ({plan.data.warnings?.length ?? 0})
                </Tabs.Tab>
                <Tabs.Tab value="tables">
                  {t('migrate.tabs.tables')} ({plan.data.tables?.length ?? 0})
                </Tabs.Tab>
                <Tabs.Tab value="statements">
                  {t('migrate.tabs.statements')} ({plan.data.statements.length})
                </Tabs.Tab>
              </Tabs.List>
              <Tabs.Panel value="warnings" pt="sm">
                <Warnings warnings={plan.data.warnings ?? []} />
              </Tabs.Panel>
              <Tabs.Panel value="tables" pt="sm">
                <Tables plan={plan.data} />
              </Tabs.Panel>
              <Tabs.Panel value="statements" pt="sm">
                <Statements statements={plan.data.statements} />
              </Tabs.Panel>
            </Tabs>
            <ApplyPanel run={run} plan={plan.data} />
          </>
        )}
      </Stack>
    </Card>
  );
}
