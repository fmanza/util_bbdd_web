import {
  Button,
  Fieldset,
  Group,
  Modal,
  NativeSelect,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
} from '@mantine/core';
import type { TFunction } from 'i18next';
import { type ReactNode, useMemo, useState } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { z } from 'zod';

import { isApiError } from '../../api/client';
import { ErrorAlert } from '../../components/ErrorAlert';
import { zodResolver } from '../../components/zodResolver';
import type { ProjectConnection } from '../projects/useProjects';
import { type DocumentTemplate, useTemplates } from '../templates/useTemplates';
import { type Operation, type OperationParam, useLaunchRun, useOperations } from './useRuns';

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
      return param.type === 'connection' || param.type === 'template' ? null : undefined;
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

/** Parámetros sin grupo primero; después cada grupo en el orden en que aparece. */
function sections(params: OperationParam[]): [string | null, OperationParam[]][] {
  const result = new Map<string | null, OperationParam[]>([[null, []]]);
  for (const param of params) {
    const key = param.group ?? null;
    result.set(key, [...(result.get(key) ?? []), param]);
  }
  return [...result.entries()].filter(([, items]) => items.length > 0);
}

function LaunchForm({
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
  const form = useForm<Values, unknown, Record<string, unknown>>({
    resolver: zodResolver(schema as unknown as z.ZodType<Record<string, unknown>, Values>),
    defaultValues: Object.fromEntries(operation.params.map((p) => [p.name, defaultValue(p)])),
  });

  const templateParams = operation.params.filter((p) => p.type === 'template');
  const templates = useTemplates({ kind: 'project', projectId }, templateParams.length > 0);
  const values = useWatch({ control: form.control });
  // Una plantilla solo se ofrece si su formato (`word`, `excel`) se va a generar.
  const paramVisible = (param: OperationParam) =>
    param.type !== 'template' || !param.template_kind || values[param.template_kind] === true;
  const targetEngine = values['target_engine'];
  const groupVisible = (group: string | null) =>
    group === null ||
    !ENGINE_GROUPS[group] ||
    (typeof targetEngine === 'string' && ENGINE_GROUPS[group].includes(targetEngine));

  const onSubmit = form.handleSubmit((values) => {
    const hidden = new Set(templateParams.filter((p) => !paramVisible(p)).map((p) => p.name));
    const params = Object.fromEntries(
      Object.entries(values)
        .filter(([, value]) => value !== undefined)
        .map(([name, value]) => [name, hidden.has(name) ? null : value]),
    );
    launch.mutate(
      { operation: operation.name, params },
      {
        onSuccess: (run) => void navigate(`/runs/${run.id}`),
        onError: (error) => {
          if (!isApiError(error)) return;
          for (const fieldError of error.problem.errors ?? []) {
            const name = fieldError.loc[2];
            if (typeof name === 'string') form.setError(name, { message: fieldError.msg });
          }
        },
      },
    );
  });

  const renderField = (param: OperationParam): ReactNode => (
    <Controller
      control={form.control}
      name={param.name}
      render={({ field }) => {
        const error = form.formState.errors[param.name]?.message;
        const label = t(`runs.params.${operation.name}.${param.name}`, { defaultValue: param.name });
        if (param.type === 'boolean') {
          return (
            <Switch
              label={label}
              description={param.description}
              checked={field.value === true}
              onChange={(event) => field.onChange(event.currentTarget.checked)}
            />
          );
        }
        if (param.type === 'connection') {
          return (
            <NativeSelect
              label={label}
              description={param.description}
              data={[
                { value: '', label: t('runs.launch.noConnection') },
                ...connections.map((c) => ({ value: c.alias, label: `${c.alias} · ${c.connection_name}` })),
              ]}
              value={typeof field.value === 'string' ? field.value : ''}
              onChange={(event) => field.onChange(event.currentTarget.value)}
              error={error}
            />
          );
        }
        if (param.type === 'template') {
          return (
            <NativeSelect
              label={label}
              description={param.description}
              data={templateOptions(templates.data ?? [], param.template_kind, t)}
              value={typeof field.value === 'string' ? field.value : ''}
              onChange={(event) => field.onChange(event.currentTarget.value)}
              error={error ?? (templates.isError ? t('runs.launch.templatesError') : undefined)}
            />
          );
        }
        if (param.options) {
          return (
            <NativeSelect
              label={label}
              description={param.description}
              data={param.options.map((option) => ({
                value: option,
                label: t(`runs.options.${option}`, { defaultValue: option }),
              }))}
              value={typeof field.value === 'string' ? field.value : ''}
              onChange={(event) => field.onChange(event.currentTarget.value)}
              error={error}
            />
          );
        }
        const numeric = param.type === 'integer' || param.type === 'float';
        return (
          <TextInput
            label={label}
            description={param.description}
            inputMode={numeric ? 'numeric' : undefined}
            required={param.required}
            value={typeof field.value === 'string' ? field.value : ''}
            onChange={field.onChange}
            onBlur={field.onBlur}
            error={error}
          />
        );
      }}
    />
  );

  return (
    <form onSubmit={onSubmit} noValidate>
      <Stack>
        <Text size="sm" c="dimmed">
          {operation.description}
        </Text>
        {launch.isError && <ErrorAlert error={launch.error} />}
        {sections(operation.params)
          .filter(([group]) => groupVisible(group))
          .map(([group, params]) => {
            const shown = params.filter(paramVisible);
            if (shown.length === 0) return null;
            const fields = shown.map((param) => <div key={param.name}>{renderField(param)}</div>);
            if (group === null) return <Stack key="__main__">{fields}</Stack>;
            return (
              <Fieldset key={group} legend={t(`runs.groups.${group}`, { defaultValue: group })}>
                <SimpleGrid cols={{ base: 1, sm: 2 }}>{fields}</SimpleGrid>
              </Fieldset>
            );
          })}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" loading={launch.isPending}>
            {t('runs.launch.submit')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function LaunchRunModal({
  projectId,
  connections,
  opened,
  onClose,
}: {
  projectId: number;
  connections: ProjectConnection[];
  opened: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const operations = useOperations();
  const [name, setName] = useState<string | null>(null);
  // `form=false` (p. ej. `migrate_apply`) se lanza desde otra pantalla.
  const launchable = (operations.data ?? []).filter((op) => op.form !== false);
  const selected = launchable.find((op) => op.name === (name ?? launchable[0]?.name));

  return (
    <Modal opened={opened} onClose={onClose} title={t('runs.launch.title')} size="lg">
      <Stack>
        {operations.isError && <ErrorAlert error={operations.error} />}
        <NativeSelect
          label={t('runs.operation')}
          data={launchable.map((op) => ({ value: op.name, label: op.title }))}
          value={selected?.name ?? ''}
          onChange={(event) => setName(event.currentTarget.value)}
        />
        {selected && (
          <LaunchForm
            key={selected.name}
            projectId={projectId}
            operation={selected}
            connections={connections}
            onClose={onClose}
          />
        )}
      </Stack>
    </Modal>
  );
}
