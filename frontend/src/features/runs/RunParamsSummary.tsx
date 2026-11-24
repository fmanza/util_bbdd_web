import {
  Anchor,
  Badge,
  Box,
  Code,
  Group,
  Loader,
  Paper,
  Stack,
  Switch,
  Text,
  Title,
  UnstyledButton,
  VisuallyHidden,
} from '@mantine/core';
import { IconCheck, IconChevronDown, IconMinus } from '@tabler/icons-react';
import { type ReactNode, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { useProjectConnections } from '../projects/useProjects';
import { useTemplates } from '../templates/useTemplates';
import { autoGrid } from './launch/grid';
import { buildParamsView, type ParamCard, type ParamEntry } from './runParamsView';
import type { Operation, RunDetail } from './useRuns';

/**
 * «Configuración» del detalle de una ejecución: las tarjetas de «Lanzar ejecución» en solo lectura, plegadas al abrir.
 * Conexiones y plantillas (para mostrar nombres en lugar de alias e ids) solo se piden al desplegar.
 */
export function RunParamsSummary({
  run,
  operation,
  operationPending,
}: {
  run: RunDetail;
  /** Operación del catálogo; `undefined` si no está o falló el catálogo (se muestran las claves guardadas). */
  operation: Operation | undefined;
  operationPending: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [onlyChanged, setOnlyChanged] = useState(false);
  const types = new Set(operation?.params.map((p) => p.type));
  const connections = useProjectConnections(run.project_id, open && types.has('connection'));
  const templates = useTemplates(
    { kind: 'project', projectId: run.project_id },
    open && types.has('template'),
  );
  const view = useMemo(
    () => buildParamsView(run.operation, operation, run.params, onlyChanged),
    [run.operation, operation, run.params, onlyChanged],
  );

  const connectionName = new Map((connections.data ?? []).map((c) => [c.alias, c.connection_name]));
  const templateName = new Map((templates.data ?? []).map((tpl) => [tpl.id, tpl.name]));

  const label = (entry: ParamEntry) =>
    t(`runs.params.${run.operation}.${entry.param.name}`, { defaultValue: entry.param.name });

  const display = ({ param, value }: ParamEntry): ReactNode => {
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'object') return <Code>{JSON.stringify(value)}</Code>;
    const raw = String(value);
    if (param.type === 'connection') {
      const name = connectionName.get(raw);
      return name ? `${raw} · ${name}` : raw;
    }
    if (param.type === 'template') return templateName.get(raw) ?? raw;
    if (param.type === 'run') {
      return (
        <Anchor component={Link} to={`/runs/${raw}`} size="sm">
          <Code>{raw}</Code>
        </Anchor>
      );
    }
    if (param.options) return t(`runs.options.${raw}`, { defaultValue: raw });
    return raw;
  };

  const flag = (entry: ParamEntry) => {
    const on = entry.value === true;
    return (
      <Badge
        key={entry.param.name}
        component="li"
        variant={on ? 'light' : 'outline'}
        {...(on ? {} : { color: 'gray' })}
        tt="none"
        fw={500}
        style={entry.inactive ? { opacity: 0.55 } : undefined}
        leftSection={on ? <IconCheck size={12} aria-hidden /> : <IconMinus size={12} aria-hidden />}
      >
        {label(entry)}
        <VisuallyHidden>: {t(on ? 'runs.detail.on' : 'runs.detail.off')}</VisuallyHidden>
      </Badge>
    );
  };

  const card = (c: ParamCard) => (
    <Paper
      key={c.id}
      withBorder
      p="sm"
      component="section"
      aria-labelledby={`run-config-${c.id}`}
      style={{ gridColumn: c.span === 'full' ? '1 / -1' : undefined, minWidth: 0 }}
    >
      <Title order={4} size="sm" mb="xs" id={`run-config-${c.id}`}>
        {t(c.title, { defaultValue: c.id })}
      </Title>
      <Stack gap="xs">
        {c.flags.length > 0 && (
          <Group component="ul" gap={6} m={0} p={0} style={{ listStyle: 'none' }}>
            {c.flags.map(flag)}
          </Group>
        )}
        {c.fields.length > 0 && (
          <Box component="dl" m={0} style={autoGrid(11, c.cols, 'var(--mantine-spacing-sm)')}>
            {c.fields.map((entry) => (
              <div key={entry.param.name} style={{ minWidth: 0, opacity: entry.inactive ? 0.55 : undefined }}>
                <Text component="dt" size="xs" c="dimmed">
                  {label(entry)}
                </Text>
                <Text component="dd" size="sm" m={0} style={{ overflowWrap: 'anywhere' }}>
                  {display(entry)}
                </Text>
              </div>
            ))}
          </Box>
        )}
      </Stack>
    </Paper>
  );

  return (
    <Stack gap="sm">
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Title order={3} size="h4">
          <UnstyledButton onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls="run-config">
            <Group gap={6} wrap="nowrap">
              <IconChevronDown
                size={18}
                aria-hidden
                style={{ transform: open ? 'rotate(180deg)' : undefined, transition: 'transform 150ms' }}
              />
              <span>{t('runs.detail.config')}</span>
              {!operationPending && operation && (
                <Text component="span" size="sm" c="dimmed" fw={400}>
                  {t('runs.detail.changedCount', { changed: view.changed, total: view.total })}
                </Text>
              )}
            </Group>
          </UnstyledButton>
        </Title>
        {open && operation && (
          <Switch
            size="sm"
            label={t('runs.detail.onlyChanged')}
            checked={onlyChanged}
            onChange={(event) => setOnlyChanged(event.currentTarget.checked)}
          />
        )}
      </Group>
      {open && (
        <Box id="run-config">
          {operationPending ? (
            <Loader size="sm" aria-label={t('common.loading')} />
          ) : view.cards.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t(onlyChanged ? 'runs.detail.noneChanged' : 'runs.detail.noParams')}
            </Text>
          ) : (
            <Box style={autoGrid(18, 3)}>{view.cards.map(card)}</Box>
          )}
        </Box>
      )}
    </Stack>
  );
}
