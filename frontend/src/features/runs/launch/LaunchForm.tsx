import {
  Box,
  Button,
  Group,
  NativeSelect,
  type NativeSelectProps,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
  UnstyledButton,
} from '@mantine/core';
import { IconAlertTriangle, IconChevronDown, IconInfoCircle } from '@tabler/icons-react';
import type { TFunction } from 'i18next';
import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { flushSync } from 'react-dom';
import { Controller, type FieldErrors, useForm, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { z } from 'zod';

import { isApiError } from '../../../api/client';
import { ErrorAlert } from '../../../components/ErrorAlert';
import { formatDateTime } from '../../../components/format';
import { zodResolver } from '../../../components/zodResolver';
import type { ProjectConnection } from '../../projects/useProjects';
import { type DocumentTemplate, useTemplates } from '../../templates/useTemplates';
import { PatternPreview } from '../PatternPreview';
import { type Operation, type OperationParam, type Run, useLaunchRun, useSucceededRuns } from '../useRuns';
import { DUMP_MODE_PARAMS, type DumpMode, dumpModeOf } from './dumpMode';
import { DumpTableSelection } from './DumpTableSelection';
import { autoGrid } from './grid';
import { LaunchCard } from './LaunchCard';
import {
  DISABLED_WITHOUT,
  itemParams,
  type ResolvedCard,
  type ResolvedItem,
  resolveCards,
  SHOWN_WHEN,
} from './launchLayout';

type Values = Record<string, string | boolean>;

function paramSchema(param: OperationParam, t: TFunction) {
  if (param.type === 'boolean') {
    return z.boolean();
  }
  return z.string().transform((raw, ctx): unknown => {
    const value = raw.trim();
    if (value === '') {
      if (param.required) {
        ctx.addIssue({ code: 'custom', message: t('auth.required') });
        return z.NEVER;
      }
      return param.type === 'connection' || param.type === 'template' || param.type === 'run'
        ? null
        : undefined;
    }
    if (param.type === 'integer' || param.type === 'float') {
      const number = Number(value);
      const integerOk = param.type === 'float' || /^-?\d+$/.test(value);
      if (Number.isNaN(number) || !integerOk) {
        ctx.addIssue({ code: 'custom', message: t('runs.launch.number') });
        return z.NEVER;
      }
      if (
        (param.minimum !== null && number < param.minimum) ||
        (param.maximum !== null && number > param.maximum)
      ) {
        ctx.addIssue({
          code: 'custom',
          message: t('runs.launch.range', { min: param.minimum ?? '−∞', max: param.maximum ?? '∞' }),
        });
        return z.NEVER;
      }
      return number;
    }
    return value;
  });
}

function defaultValue(param: OperationParam): string | boolean {
  if (param.type === 'boolean') return param.default === true;
  return param.default === null || param.default === undefined ? '' : String(param.default);
}

/** Grupos de `migrate_plan` que solo aplican a un motor destino: se ocultan para los demás. */
const ENGINE_GROUPS: Record<string, readonly string[]> = {
  mysql: ['mariadb', 'mysql'],
  sqlserver: ['sqlserver'],
  postgresql: ['postgresql'],
  oracle: ['oracle'],
};

/** Parámetros de `migrate_plan` que util_bbdd solo usa con origen Oracle (`NUMBER` sin precisión, ancho de INT). */
const ORACLE_SOURCE_PARAMS: ReadonlySet<string> = new Set(['number_fallback', 'int_display_width']);

/**
 * Operaciones con «Probar patrones» en su filtro (1.15.0 documentación; 1.19.0 migración y volcado): campos de la
 * conexión y del schema del formulario y si el filtro se aplica también a las vistas.
 */
const PATTERN_PREVIEW: Record<string, { connection: string; schema: string; views: boolean }> = {
  documentation: { connection: 'connection', schema: 'schema', views: true },
  migrate_plan: { connection: 'source_connection', schema: 'source_schema', views: true },
  dump_preview: { connection: 'source_connection', schema: 'source_schema', views: false },
};

/** Opciones de un parámetro de plantilla: «sin plantilla» y las del tipo pedido, las del proyecto primero. */
function templateOptions(templates: DocumentTemplate[], kind: string | null | undefined, t: TFunction) {
  const items = (scope: DocumentTemplate['scope']) =>
    templates
      .filter((template) => template.kind === kind && template.scope === scope)
      .map((template) => ({ value: template.id, label: template.name }));
  return [
    { value: '', label: t('runs.launch.noTemplate') },
    ...[
      { group: t('runs.launch.projectTemplates'), items: items('project') },
      { group: t('runs.launch.globalTemplates'), items: items('global') },
    ].filter((group) => group.items.length > 0),
  ];
}

/** Parámetros que, ocultos, se envían como `null` (la plantilla o la ejecución elegida no se usa); el resto se omite. */
const NULL_WHEN_HIDDEN: ReadonlySet<OperationParam['type']> = new Set(['template', 'run']);

/** Si `run` es de la misma conexión y schema que el formulario (y, en documentación, con Markdown). */
function comparable(run: Run, values: Partial<Values>): boolean {
  const schema = (value: unknown) => (typeof value === 'string' ? value.trim() : '');
  return (
    run.params['connection'] === values['connection'] &&
    schema(run.params['schema']) === schema(values['schema']) &&
    (run.operation !== 'documentation' || run.params['markdown'] === true)
  );
}

/** Opciones de un parámetro de ejecución anterior: «ninguna» y las comparables, la más reciente primero. */
function runOptions(runs: Run[], values: Partial<Values>, t: TFunction) {
  return [
    { value: '', label: t('runs.launch.noRun') },
    ...runs
      .filter((run) => comparable(run, values))
      .map((run) => ({
        value: run.id,
        label: t('runs.launch.runOption', {
          date: formatDateTime(run.finished_at ?? run.created_at),
          user: run.username ?? '—',
        }),
      })),
  ];
}

/** Sin condiciones (referencia estable para los efectos). */
const NONE: Readonly<Record<string, never>> = {};

/** Valor de texto de un campo del formulario (los interruptores no lo son). */
function text(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

/** Formulario de una operación: tarjetas según `launchLayout`, opciones avanzadas plegadas y pie fijo. */
export function LaunchForm({
  projectId,
  operation,
  connections,
  onClose,
}: {
  projectId: number;
  operation: Operation;
  connections: ProjectConnection[];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const launch = useLaunchRun(projectId);
  const schema = useMemo(
    () => z.object(Object.fromEntries(operation.params.map((p) => [p.name, paramSchema(p, t)]))),
    [operation, t],
  );
  const defaults = useMemo(
    () => Object.fromEntries(operation.params.map((p) => [p.name, defaultValue(p)])),
    [operation],
  );
  const form = useForm<Values, unknown, Record<string, unknown>>({
    resolver: zodResolver(schema as unknown as z.ZodType<Record<string, unknown>, Values>),
    defaultValues: defaults,
  });
  const cards = useMemo(() => resolveCards(operation), [operation]);
  const advancedParams = useMemo(
    () => new Set(cards.filter((c) => c.advanced).flatMap((c) => c.params)),
    [cards],
  );
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [dumpMode, setDumpMode] = useState<DumpMode>(() => dumpModeOf(defaults));
  const hasDumpSelection = cards.some((c) => c.widget === 'dumpSelection');

  const templateParams = operation.params.filter((p) => p.type === 'template');
  const templates = useTemplates({ kind: 'project', projectId }, templateParams.length > 0);
  const runParam = operation.params.find((p) => p.type === 'run');
  const previousRuns = useSucceededRuns(projectId, runParam?.run_operation ?? null, runParam !== undefined);
  const values = useWatch({ control: form.control });
  const patternPreview = PATTERN_PREVIEW[operation.name];
  const sourceType = connections.find((c) => c.alias === values['source_connection'])?.db_type;
  const shownWhen = SHOWN_WHEN[operation.name] ?? NONE;
  const disabledWithout = DISABLED_WITHOUT[operation.name] ?? NONE;
  const dumpHidden = hasDumpSelection
    ? new Set(
        Object.entries(DUMP_MODE_PARAMS)
          .filter(([mode]) => mode !== dumpMode)
          .flatMap(([, names]) => names)
          .filter((name) => !DUMP_MODE_PARAMS[dumpMode].includes(name)),
      )
    : new Set<string>();

  // Un parámetro con `requires` solo se ofrece si ese interruptor está activado (las opciones del Markdown); una
  // plantilla sin él, si su formato (`word`, `excel`) se va a generar; uno de `SHOWN_WHEN`, con ese valor.
  const paramVisible = (param: OperationParam) => {
    const condition = shownWhen[param.name];
    return (
      (param.requires
        ? values[param.requires] === true
        : param.type !== 'template' || !param.template_kind || values[param.template_kind] === true) &&
      (!ORACLE_SOURCE_PARAMS.has(param.name) || sourceType === 'oracle') &&
      (!condition || values[condition.param] === condition.value) &&
      !dumpHidden.has(param.name)
    );
  };
  // Al ocultarse una opción (interruptor desactivado, otro valor), vuelve al valor por defecto: un valor no válido en
  // un campo oculto bloquearía el envío con un error que no se ve.
  useEffect(() => {
    for (const param of operation.params) {
      const condition = shownWhen[param.name];
      const hidden =
        (param.requires && values[param.requires] !== true) ||
        (condition && values[condition.param] !== condition.value);
      if (hidden && values[param.name] !== defaultValue(param)) {
        form.resetField(param.name);
      }
    }
  }, [operation, values, form, shownWhen]);
  // Una ejecución anterior elegida que deja de ser comparable (otra conexión o schema) se quita.
  const selectedRun = runParam ? values[runParam.name] : undefined;
  useEffect(() => {
    if (!runParam || typeof selectedRun !== 'string' || selectedRun === '' || !previousRuns.data) return;
    const still = previousRuns.data.items.some((run) => run.id === selectedRun && comparable(run, values));
    if (!still) form.setValue(runParam.name, '');
  }, [runParam, selectedRun, previousRuns.data, values, form]);

  const targetEngine = values['target_engine'];
  const groupVisible = (group: string) =>
    !ENGINE_GROUPS[group] ||
    (typeof targetEngine === 'string' && ENGINE_GROUPS[group].includes(targetEngine));

  const changeDumpMode = (mode: DumpMode) => {
    for (const name of Object.values(DUMP_MODE_PARAMS).flat()) {
      if (!DUMP_MODE_PARAMS[mode].includes(name) && operation.params.some((p) => p.name === name)) {
        form.resetField(name);
      }
    }
    setDumpMode(mode);
  };

  /**
   * Errores en opciones avanzadas: se abre la sección (síncrono, para que sus campos existan) y, si todos los errores
   * están ahí, el foco va al primero; si hay alguno visible, el foco ya lo pone react-hook-form.
   */
  const reveal = (names: string[]) => {
    const order = cards.flatMap((c) => c.params);
    const hidden = names
      .filter((name) => advancedParams.has(name))
      .sort((a, b) => order.indexOf(a) - order.indexOf(b));
    if (hidden.length === 0) return;
    flushSync(() => setShowAdvanced(true));
    if (hidden.length === names.length && hidden[0]) form.setFocus(hidden[0]);
  };

  const onInvalid = (errors: FieldErrors<Values>) => reveal(Object.keys(errors));

  const onSubmit = form.handleSubmit((submitted) => {
    const hiddenParams = operation.params.filter((p) => !paramVisible(p));
    const nulled = new Set(hiddenParams.filter((p) => NULL_WHEN_HIDDEN.has(p.type)).map((p) => p.name));
    const omitted = new Set(
      hiddenParams
        .filter((p) => (p.requires || shownWhen[p.name] || dumpHidden.has(p.name)) && !nulled.has(p.name))
        .map((p) => p.name),
    );
    const params = Object.fromEntries(
      Object.entries(submitted)
        .filter(([name, value]) => value !== undefined && !omitted.has(name))
        .map(([name, value]) => [name, nulled.has(name) ? null : value]),
    );
    launch.mutate(
      { operation: operation.name, params },
      {
        onSuccess: (run) => void navigate(`/runs/${run.id}`),
        onError: (error) => {
          if (!isApiError(error)) return;
          const names: string[] = [];
          for (const fieldError of error.problem.errors ?? []) {
            const name = fieldError.loc[2];
            if (typeof name === 'string') {
              form.setError(name, { message: fieldError.msg });
              names.push(name);
            }
          }
          reveal(names);
        },
      },
    );
  }, onInvalid);

  /** Parámetros que dependen de otro de la misma tarjeta se sangran bajo él. */
  const renderField = (param: OperationParam, card: ResolvedCard): ReactNode => {
    const switchParam = disabledWithout[param.name];
    const parent = param.requires ?? switchParam;
    const indent = parent !== undefined && card.params.includes(parent);
    const disabled = switchParam !== undefined && values[switchParam] === false;
    return (
      <Box key={param.name} pl={indent ? 'lg' : 0}>
        <Controller
          control={form.control}
          name={param.name}
          render={({ field }) => {
            const error = form.formState.errors[param.name]?.message;
            const label = t(`runs.params.${operation.name}.${param.name}`, { defaultValue: param.name });
            if (param.type === 'boolean') {
              return (
                <Switch
                  ref={field.ref}
                  label={label}
                  description={param.description}
                  checked={field.value === true}
                  disabled={disabled}
                  onChange={(event) => field.onChange(event.currentTarget.checked)}
                />
              );
            }
            const select = (data: NonNullable<NativeSelectProps['data']>, extraError?: string) => (
              <NativeSelect
                ref={field.ref}
                label={label}
                description={param.description}
                data={data}
                disabled={disabled}
                value={typeof field.value === 'string' ? field.value : ''}
                onChange={(event) => field.onChange(event.currentTarget.value)}
                error={error ?? extraError}
              />
            );
            if (param.type === 'connection') {
              return select([
                { value: '', label: t('runs.launch.noConnection') },
                ...connections.map((c) => ({ value: c.alias, label: `${c.alias} · ${c.connection_name}` })),
              ]);
            }
            if (param.type === 'template') {
              return select(
                templateOptions(templates.data ?? [], param.template_kind, t),
                templates.isError ? t('runs.launch.templatesError') : undefined,
              );
            }
            if (param.type === 'run') {
              return select(
                runOptions(previousRuns.data?.items ?? [], values, t),
                previousRuns.isError ? t('runs.launch.runsError') : undefined,
              );
            }
            if (param.options) {
              // Sin valor por defecto, el navegador mostraría la primera opción sin elegirla (y elegirla no cambiaría
              // nada).
              const placeholder =
                param.default === null || param.default === undefined
                  ? [{ value: '', label: t('runs.launch.choose'), disabled: true }]
                  : [];
              return select([
                ...placeholder,
                ...param.options.map((option) => ({
                  value: option,
                  label: t(`runs.options.${option}`, { defaultValue: option }),
                })),
              ]);
            }
            const numeric = param.type === 'integer' || param.type === 'float';
            return (
              <TextInput
                ref={field.ref}
                label={label}
                description={param.description}
                inputMode={numeric ? 'numeric' : undefined}
                required={param.required}
                disabled={disabled}
                value={typeof field.value === 'string' ? field.value : ''}
                onChange={field.onChange}
                onBlur={field.onBlur}
                error={error}
              />
            );
          }}
        />
      </Box>
    );
  };

  const renderItem = (item: ResolvedItem, card: ResolvedCard, index: number): ReactNode => {
    if (item.kind === 'param') return paramVisible(item.param) ? renderField(item.param, card) : null;
    const shown = item.params.filter(paramVisible);
    if (shown.length === 0) return null;
    if (item.kind === 'stack') {
      return (
        <Stack key={`stack-${index}`} gap="sm">
          {shown.map((param) => renderField(param, card))}
        </Stack>
      );
    }
    if (!groupVisible(item.group)) return null;
    return (
      <Box
        key={`group-${item.group}`}
        component="fieldset"
        aria-labelledby={`launch-group-${item.group}`}
        m={0}
        p={0}
        style={{ border: 0, gridColumn: '1 / -1', minWidth: 0 }}
      >
        <Text id={`launch-group-${item.group}`} size="sm" fw={600} mb="xs">
          {t(`runs.groups.${item.group}`, { defaultValue: item.group })}
        </Text>
        <Box style={autoGrid(13, 2)}>{shown.map((param) => renderField(param, card))}</Box>
      </Box>
    );
  };

  const renderCard = (card: ResolvedCard): ReactNode => {
    const visible = card.items.some((item) =>
      item.kind === 'group'
        ? groupVisible(item.group) && item.params.some(paramVisible)
        : itemParams(item).some(paramVisible),
    );
    if (!visible && !card.widget) return null;
    const errors = card.params.filter((name) => form.formState.errors[name]).length;
    const fields = card.items.map((item, index) => renderItem(item, card, index));
    const preview = patternPreview && (card.widget === 'patternPreview' || dumpMode === 'patterns') && (
      <PatternPreview
        operation={operation.name}
        views={patternPreview.views}
        connections={connections}
        connectionAlias={text(values[patternPreview.connection])}
        schema={text(values[patternPreview.schema])}
        include={text(values['table_include'])}
        exclude={text(values['table_exclude'])}
      />
    );
    let body: ReactNode = fields;
    if (card.widget === 'patternPreview') {
      body = (
        <>
          <Stack gap="sm">{fields}</Stack>
          <Box>{preview}</Box>
        </>
      );
    } else if (card.widget === 'dumpSelection') {
      body = (
        <DumpTableSelection mode={dumpMode} onModeChange={changeDumpMode}>
          <Box style={autoGrid(18, 2)}>
            <Stack gap="sm">{fields}</Stack>
            {dumpMode === 'patterns' && <Box>{preview}</Box>}
          </Box>
        </DumpTableSelection>
      );
    }
    return (
      <LaunchCard
        key={card.id}
        title={t(card.title, { defaultValue: card.id })}
        errors={errors}
        span={card.span}
        cols={card.widget ? 2 : (card.cols ?? 1)}
      >
        {body}
      </LaunchCard>
    );
  };

  const main = cards.filter((c) => !c.advanced);
  const advanced = cards.filter((c) => c.advanced);
  const advancedErrors = advanced.flatMap((c) => c.params).filter((n) => form.formState.errors[n]).length;
  const summary = t(`runs.launch.summary.${operation.name}`, { defaultValue: '' });

  return (
    <form onSubmit={onSubmit} noValidate>
      <Stack gap="md">
        <div>
          <Title order={3} size="h4">
            {operation.title}
          </Title>
          <Text size="sm" c="dimmed">
            {operation.description}
          </Text>
        </div>
        {launch.isError && <ErrorAlert error={launch.error} />}
        <Box style={autoGrid(22, 3)}>{main.map(renderCard)}</Box>
        {advanced.length > 0 && (
          <Stack gap="sm">
            <UnstyledButton
              onClick={() => setShowAdvanced((open) => !open)}
              aria-expanded={showAdvanced}
              aria-controls="launch-advanced"
            >
              <Group gap={6}>
                <IconChevronDown
                  size={16}
                  aria-hidden
                  style={{
                    transform: showAdvanced ? 'rotate(180deg)' : undefined,
                    transition: 'transform 150ms',
                  }}
                />
                <Text size="sm" fw={600}>
                  {t('runs.launch.advanced')}
                </Text>
                {advancedErrors > 0 && (
                  <Text size="xs" c="red">
                    {t('runs.launch.cardErrors', { count: advancedErrors })}
                  </Text>
                )}
              </Group>
            </UnstyledButton>
            {showAdvanced && (
              <Box id="launch-advanced" style={autoGrid(22, 3)}>
                {advanced.map(renderCard)}
              </Box>
            )}
          </Stack>
        )}
        <Group
          justify="space-between"
          wrap="wrap"
          gap="sm"
          py="sm"
          style={{
            position: 'sticky',
            bottom: 0,
            zIndex: 2,
            background: 'var(--mantine-color-body)',
            borderTop: '1px solid var(--mantine-color-default-border)',
          }}
        >
          <Stack gap={2} style={{ flex: '1 1 18rem', minWidth: 0 }}>
            {summary && (
              <Group gap={6} wrap="nowrap">
                <IconInfoCircle size={16} aria-hidden style={{ flexShrink: 0 }} />
                <Text size="sm" c="dimmed">
                  {summary}
                </Text>
              </Group>
            )}
            {values['truncate_target'] === true && (
              <Group gap={6} wrap="nowrap">
                <IconAlertTriangle
                  size={16}
                  aria-hidden
                  color="var(--mantine-color-red-6)"
                  style={{ flexShrink: 0 }}
                />
                <Text size="sm" c="red" fw={600}>
                  {t('runs.launch.truncateWarning')}
                </Text>
              </Group>
            )}
          </Stack>
          <Group gap="sm">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={launch.isPending}>
              {t('runs.launch.submit')}
            </Button>
          </Group>
        </Group>
      </Stack>
    </form>
  );
}
