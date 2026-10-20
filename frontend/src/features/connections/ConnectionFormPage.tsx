import {
  Accordion,
  Alert,
  Button,
  Center,
  Group,
  Loader,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useMemo } from 'react';
import { Controller, type UseFormReturn, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router';

import { isApiError } from '../../api/client';
import { ErrorAlert } from '../../components/ErrorAlert';
import { zodResolver } from '../../components/zodResolver';
import { useMe } from '../auth/useAuth';
import { type EngineDetail, type EngineParam, useEngine, useEngines } from '../engines/useEngines';
import {
  buildConnectionSchema,
  type ConnectionFormOutput,
  type ConnectionFormValues,
  editableParams,
  isPrimary,
  toFormValue,
} from './connectionSchema';
import {
  type ConnectionInfo,
  useConnection,
  useCreateConnection,
  useUpdateConnection,
} from './useConnections';

type Form = UseFormReturn<ConnectionFormValues, unknown, ConnectionFormOutput>;

function ParamField({ param, form }: { param: EngineParam; form: Form }) {
  const { t } = useTranslation();
  const name = `params.${param.name}` as const;
  const error = form.formState.errors.params?.[param.name]?.message;
  const defaultHint =
    param.default === undefined || param.default === null || param.default === ''
      ? undefined
      : t('connections.form.default', { value: String(param.default) });
  const description = [param.description, param.kind === 'path' ? t('connections.form.pathHint') : undefined]
    .filter(Boolean)
    .join(' ');
  const common = { label: param.name, description, required: param.required, error };

  return (
    <Controller
      control={form.control}
      name={name}
      render={({ field }) => {
        const value = field.value ?? '';
        if (param.type === 'boolean' || param.options) {
          const options = param.options ?? ['true', 'false'];
          return (
            <Select
              {...common}
              data={[
                { value: '', label: defaultHint ?? t('connections.form.unset') },
                ...options
                  .filter((option) => option !== '')
                  .map((option) => ({
                    value: option,
                    label:
                      param.type === 'boolean' ? t(option === 'true' ? 'common.yes' : 'common.no') : option,
                  })),
              ]}
              value={value}
              onChange={(next) => field.onChange(next ?? '')}
              onBlur={field.onBlur}
              allowDeselect={false}
            />
          );
        }
        if (param.type === 'object') {
          return (
            <Textarea
              {...common}
              autosize
              minRows={2}
              placeholder="{}"
              value={value}
              onChange={field.onChange}
              onBlur={field.onBlur}
            />
          );
        }
        return (
          <TextInput
            {...common}
            inputMode={param.type === 'integer' || param.type === 'float' ? 'numeric' : undefined}
            placeholder={defaultHint}
            autoComplete="off"
            value={value}
            onChange={field.onChange}
            onBlur={field.onBlur}
          />
        );
      }}
    />
  );
}

function defaults(engine: EngineDetail, connection: ConnectionInfo | undefined): ConnectionFormValues {
  const stored = (connection?.params ?? {}) as Record<string, unknown>;
  return {
    name: connection?.name ?? '',
    description: connection?.description ?? '',
    password: '',
    read_only: connection?.read_only ?? true,
    visibility: connection?.visibility ?? 'private',
    params: Object.fromEntries(editableParams(engine).map((p) => [p.name, toFormValue(p, stored[p.name])])),
  };
}

interface ConnectionFormProps {
  engine: EngineDetail;
  connection?: ConnectionInfo;
}

function ConnectionForm({ engine, connection }: ConnectionFormProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const create = useCreateConnection();
  const update = useUpdateConnection(connection?.id ?? 0);
  const mutation = connection ? update : create;
  const schema = useMemo(
    () => buildConnectionSchema(engine, t, { hasStoredPassword: connection?.has_password ?? false }),
    [engine, t, connection?.has_password],
  );
  const form = useForm<ConnectionFormValues, unknown, ConnectionFormOutput>({
    resolver: zodResolver(schema),
    defaultValues: defaults(engine, connection),
  });
  const params = editableParams(engine);
  const primary = params.filter(isPrimary);
  const advanced = params.filter((p) => !isPrimary(p));
  const hasPasswordParam = engine.params.some((p) => p.kind === 'secret');

  const onError = (error: unknown) => {
    if (!isApiError(error)) return;
    for (const fieldError of error.problem.errors ?? []) {
      const [, first, second] = fieldError.loc;
      if (first === 'params' && typeof second === 'string') {
        form.setError(`params.${second}`, { message: fieldError.msg });
      } else if (first === 'name' || first === 'description' || first === 'password') {
        form.setError(first, { message: fieldError.msg });
      }
    }
  };

  const onSubmit = form.handleSubmit((values) => {
    const body = {
      name: values.name,
      description: values.description,
      params: values.params,
      read_only: values.read_only,
      visibility: values.visibility,
      ...(values.password ? { password: values.password } : {}),
    };
    const onSuccess = (saved: ConnectionInfo) => void navigate(`/connections/${saved.id}`);
    if (connection) {
      update.mutate(body, { onSuccess, onError });
    } else {
      create.mutate({ ...body, db_type: engine.db_type }, { onSuccess, onError });
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate>
      <Stack maw={720}>
        {mutation.isError && <ErrorAlert error={mutation.error} />}
        <Controller
          control={form.control}
          name="name"
          render={({ field }) => (
            <TextInput
              {...field}
              label={t('connections.form.name')}
              required
              error={form.formState.errors.name?.message}
            />
          )}
        />
        <Controller
          control={form.control}
          name="description"
          render={({ field }) => (
            <Textarea
              {...field}
              label={t('connections.form.description')}
              autosize
              minRows={1}
              error={form.formState.errors.description?.message}
            />
          )}
        />
        <Title order={3} size="h4">
          {t('connections.form.params', { engine: engine.name })}
        </Title>
        {primary.map((param) => (
          <ParamField key={param.name} param={param} form={form} />
        ))}
        {hasPasswordParam && (
          <Controller
            control={form.control}
            name="password"
            render={({ field }) => (
              <PasswordInput
                {...field}
                label={t('connections.form.password')}
                description={
                  connection?.has_password
                    ? t('connections.form.passwordKeep')
                    : t('connections.form.passwordHint')
                }
                autoComplete="new-password"
                required={
                  engine.params.some((p) => p.kind === 'secret' && p.required) && !connection?.has_password
                }
                error={form.formState.errors.password?.message}
              />
            )}
          />
        )}
        {advanced.length > 0 && (
          <Accordion variant="separated">
            <Accordion.Item value="advanced">
              <Accordion.Control>
                {t('connections.form.advanced', { count: advanced.length })}
              </Accordion.Control>
              <Accordion.Panel>
                <Stack>
                  {advanced.map((param) => (
                    <ParamField key={param.name} param={param} form={form} />
                  ))}
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        )}
        <Controller
          control={form.control}
          name="read_only"
          render={({ field }) => (
            <Switch
              label={t('connections.form.readOnly')}
              description={t('connections.form.readOnlyHint')}
              checked={field.value}
              onChange={(event) => field.onChange(event.currentTarget.checked)}
            />
          )}
        />
        {me?.role === 'admin' && (
          <Controller
            control={form.control}
            name="visibility"
            render={({ field }) => (
              <Select
                label={t('connections.form.visibility')}
                description={t('connections.form.visibilityHint')}
                data={[
                  { value: 'private', label: t('connections.visibility.private') },
                  { value: 'shared', label: t('connections.visibility.shared') },
                ]}
                value={field.value}
                onChange={(next) => field.onChange(next === 'shared' ? 'shared' : 'private')}
                allowDeselect={false}
              />
            )}
          />
        )}
        <Group justify="flex-end">
          <Button
            variant="default"
            onClick={() => void navigate(connection ? `/connections/${connection.id}` : '/connections')}
          >
            {t('common.cancel')}
          </Button>
          <Button type="submit" loading={mutation.isPending}>
            {connection ? t('common.save') : t('connections.create')}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

/** Alta (`/connections/new?db_type=…`): primero se elige el motor; el formulario se genera desde su ficha. */
export function NewConnectionPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const dbType = searchParams.get('db_type');
  const engines = useEngines();
  const engine = useEngine(dbType);

  return (
    <Stack>
      <Title order={2}>{t('connections.newTitle')}</Title>
      {engines.isError && <ErrorAlert error={engines.error} />}
      <Select
        label={t('connections.form.engine')}
        placeholder={t('connections.form.enginePlaceholder')}
        data={(engines.data ?? []).map((e) => ({ value: e.db_type, label: e.name }))}
        value={dbType}
        onChange={(next) => setSearchParams(next ? { db_type: next } : {}, { replace: true })}
        maw={360}
        allowDeselect={false}
        required
      />
      {dbType && engine.isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {engine.isError && <ErrorAlert error={engine.error} />}
      {engine.data && <ConnectionForm key={engine.data.db_type} engine={engine.data} />}
      {!dbType && <Text c="dimmed">{t('connections.form.chooseEngine')}</Text>}
    </Stack>
  );
}

export function EditConnectionPage() {
  const { t } = useTranslation();
  const id = Number(useParams().connectionId);
  const connection = useConnection(id);
  const engine = useEngine(connection.data?.db_type);

  if (connection.isError) return <ErrorAlert error={connection.error} />;
  if (engine.isError) return <ErrorAlert error={engine.error} />;
  if (!connection.data || !engine.data) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (!connection.data.editable) {
    return (
      <Alert color="yellow" role="alert" title={t('common.noPermission')}>
        {t('connections.notEditable')}
      </Alert>
    );
  }
  return (
    <Stack>
      <Title order={2}>{t('connections.editTitle', { name: connection.data.name })}</Title>
      <ConnectionForm engine={engine.data} connection={connection.data} />
    </Stack>
  );
}
