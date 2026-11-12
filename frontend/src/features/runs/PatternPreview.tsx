import { Alert, Anchor, Button, Code, Collapse, Group, List, Stack, Text } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { useSchemaTree, useSchemas } from '../explorer/useExplorer';
import type { ProjectConnection } from '../projects/useProjects';
import { buildFilter, matches } from './tablePatterns';

/** Nombres que se listan de cada grupo (el resto se cuenta). */
const SHOWN = 30;

interface Props {
  connections: ProjectConnection[];
  connectionAlias: string | undefined;
  schema: string | undefined;
  include: string | undefined;
  exclude: string | undefined;
}

function Names({ names }: { names: string[] }) {
  const { t } = useTranslation();
  if (names.length === 0) return null;
  return (
    <Text size="xs" style={{ wordBreak: 'break-word' }}>
      {names.slice(0, SHOWN).join(', ')}
      {names.length > SHOWN && ` ${t('runs.patterns.more', { count: names.length - SHOWN })}`}
    </Text>
  );
}

/**
 * Ayuda del filtro de tablas y «Probar patrones» (1.15.0): aplica los patrones, con la semántica de util_bbdd, a las
 * tablas y vistas del schema (el árbol del explorador, en caché) antes de lanzar la documentación. La frontera necesita
 * las FK y se calcula al generar.
 */
export function PatternPreview({ connections, connectionAlias, schema, include, exclude }: Props) {
  const { t } = useTranslation();
  const [helpOpen, setHelpOpen] = useState(false);
  const [requested, setRequested] = useState(false);
  const connection = connections.find((c) => c.alias === connectionAlias);
  const connectionId = connection?.connection_id ?? 0;
  const explicit = schema?.trim() || null;
  const schemas = useSchemas(connectionId, requested && connection !== undefined && explicit === null);
  const target = explicit ?? schemas.data?.default ?? null;
  const tree = useSchemaTree(connectionId, requested && connection !== undefined ? target : null);

  const filter = buildFilter(include, exclude);
  const tables = tree.data?.tables.map((item) => item.name) ?? [];
  const views = tree.data?.views.filter((item) => !item.materialized).map((item) => item.name) ?? [];
  const keptTables = tables.filter((name) => matches(filter, name));
  const keptViews = views.filter((name) => matches(filter, name));
  const leftOut = [...tables, ...views].filter((name) => !matches(filter, name));
  const error = schemas.error ?? tree.error;

  return (
    <Stack gap="xs" style={{ gridColumn: '1 / -1' }}>
      <Group gap="xs">
        <Button
          size="xs"
          variant="light"
          disabled={connection === undefined}
          loading={requested && (schemas.isFetching || tree.isFetching)}
          // Activa la lectura del árbol (en caché del explorador); después el resultado sigue a los patrones al escribir
          onClick={() => setRequested(true)}
        >
          {t('runs.patterns.try')}
        </Button>
        <Anchor component="button" type="button" size="sm" onClick={() => setHelpOpen((open) => !open)}>
          {helpOpen ? t('runs.patterns.hideHelp') : t('runs.patterns.showHelp')}
        </Anchor>
      </Group>
      {connection === undefined && (
        <Text size="xs" c="dimmed">
          {t('runs.patterns.chooseConnection')}
        </Text>
      )}
      <Collapse expanded={helpOpen}>
        <Alert variant="light" color="gray" title={t('runs.patterns.helpTitle')}>
          <List size="sm" spacing={4}>
            <List.Item>
              <Code>*</Code> {t('runs.patterns.star')}; <Code>?</Code> {t('runs.patterns.question')};{' '}
              <Code>[ABC]</Code> {t('runs.patterns.set')}; <Code>[!ABC]</Code> {t('runs.patterns.notSet')}.
            </List.Item>
            <List.Item>{t('runs.patterns.caseAndCommas')}</List.Item>
            <List.Item>
              <Code>MVG_*</Code> {t('runs.patterns.exampleModule')}
            </List.Item>
            <List.Item>
              <Code>MVG_*, COB_*</Code> {t('runs.patterns.exampleTwo')}
            </List.Item>
            <List.Item>
              <Code>*_BAK, TMP_*</Code> {t('runs.patterns.exampleExclude')}
            </List.Item>
            <List.Item>{t('runs.patterns.frontier')}</List.Item>
          </List>
        </Alert>
      </Collapse>
      {requested && error && <ErrorAlert error={error} />}
      {requested && tree.data && (
        <Alert variant="light" color="blue" title={t('runs.patterns.resultTitle', { schema: target ?? '' })}>
          <Stack gap={4} aria-live="polite">
            <Text size="sm">
              {t('runs.patterns.result', {
                tables: keptTables.length,
                totalTables: tables.length,
                views: keptViews.length,
                totalViews: views.length,
              })}
            </Text>
            {keptTables.length + keptViews.length === 0 && (
              <Text size="sm" c="orange">
                {t('runs.patterns.nothing')}
              </Text>
            )}
            {keptTables.length + keptViews.length > 0 && (
              <>
                <Text size="xs" fw={500}>
                  {t('runs.patterns.documented')}
                </Text>
                <Names names={[...keptTables, ...keptViews]} />
              </>
            )}
            {leftOut.length > 0 && (
              <>
                <Text size="xs" fw={500}>
                  {t('runs.patterns.leftOut', { count: leftOut.length })}
                </Text>
                <Names names={leftOut} />
              </>
            )}
          </Stack>
        </Alert>
      )}
    </Stack>
  );
}
