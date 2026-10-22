import { Button, Group, Modal, Select, Stack, Switch, Text, TextInput } from '@mantine/core';
import type { TFunction } from 'i18next';
import { useMemo, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { z } from 'zod';

import { isApiError } from '../../api/client';
import { ErrorAlert } from '../../components/ErrorAlert';
import { zodResolver } from '../../components/zodResolver';
import type { ProjectConnection } from '../projects/useProjects';
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
      return param.type === 'connection' ? null : undefined;
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

  const onSubmit = form.handleSubmit((values) => {
    const params = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined));
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

  return (
    <form onSubmit={onSubmit} noValidate>
      <Stack>
        <Text size="sm" c="dimmed">
          {operation.description}
        </Text>
        {launch.isError && <ErrorAlert error={launch.error} />}
        {operation.params.map((param) => (
          <Controller
            key={param.name}
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
                  <Select
                    label={label}
                    description={param.description}
                    placeholder={t('runs.launch.noConnection')}
                    data={connections.map((c) => ({
                      value: c.alias,
                      label: `${c.alias} · ${c.connection_name}`,
                    }))}
                    value={typeof field.value === 'string' && field.value ? field.value : null}
                    onChange={(next) => field.onChange(next ?? '')}
                    clearable
                    error={error}
                  />
                );
              }
              return (
                <TextInput
                  label={label}
                  description={param.description}
                  inputMode="numeric"
                  required={param.required}
                  value={typeof field.value === 'string' ? field.value : ''}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  error={error}
                />
              );
            }}
          />
        ))}
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
  const selected = operations.data?.find((op) => op.name === (name ?? operations.data[0]?.name));

  return (
    <Modal opened={opened} onClose={onClose} title={t('runs.launch.title')} size="lg">
      <Stack>
        {operations.isError && <ErrorAlert error={operations.error} />}
        <Select
          label={t('runs.operation')}
          data={(operations.data ?? []).map((op) => ({ value: op.name, label: op.title }))}
          value={selected?.name ?? null}
          onChange={setName}
          allowDeselect={false}
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
