import {
  Alert,
  Anchor,
  Button,
  Checkbox,
  Group,
  Modal,
  NativeSelect,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { ErrorAlert } from '../../../components/ErrorAlert';
import { formatDateTime } from '../../../components/format';
import { useMe } from '../../auth/useAuth';
import { useProjectConnections } from '../../projects/useProjects';
import { RunStatusBadge } from '../RunStatusBadge';
import { type RunDetail, useLaunchRun } from '../useRuns';
import { type MigrationPlan, usableDryRun, usePlanApplications } from './useMigrate';

function ConfirmApply({
  alias,
  opened,
  pending,
  error,
  onClose,
  onConfirm,
}: {
  alias: string;
  opened: boolean;
  pending: boolean;
  error: unknown;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const { t } = useTranslation();
  const [understood, setUnderstood] = useState(false);
  const [typed, setTyped] = useState('');
  const ready = understood && typed === alias;
  return (
    <Modal opened={opened} onClose={onClose} title={t('migrate.apply.confirmTitle')}>
      <Stack>
        {error !== null && <ErrorAlert error={error} />}
        <Alert color="red" title={t('migrate.apply.notAtomicTitle')}>
          {t('migrate.apply.notAtomic', { alias })}
        </Alert>
        <Checkbox
          label={t('migrate.apply.understand')}
          checked={understood}
          onChange={(event) => setUnderstood(event.currentTarget.checked)}
        />
        <TextInput
          label={t('migrate.apply.typeAlias', { alias })}
          value={typed}
          onChange={(event) => setTyped(event.currentTarget.value)}
          autoComplete="off"
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button color="red" disabled={!ready} loading={pending} onClick={onConfirm}>
            {t('migrate.apply.submit')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

/**
 * Aplicar un plan en una conexión destino (ADR-008): permiso `can_apply_ddl` + owner, destino no `read_only` del motor
 * del plan, modo seco previo (menos de 60 min) y doble confirmación. La API vuelve a comprobarlo todo.
 */
export function ApplyPanel({ run, plan }: { run: RunDetail; plan: MigrationPlan }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const connections = useProjectConnections(run.project_id);
  const applications = usePlanApplications(run.project_id, run.id);
  const launch = useLaunchRun(run.project_id);
  const [target, setTarget] = useState('');
  const [confirming, setConfirming] = useState(false);

  const allowed = Boolean(me?.can_apply_ddl) && run.my_role === 'owner';
  const blocked = plan.error_count > 0 || Boolean(plan.fk_blocking);
  const eligible = (connections.data ?? []).filter((c) => c.db_type === plan.target_engine && !c.read_only);
  // Referencia de «ahora»: la última consulta del historial (se refresca sola; la API comprueba la hora real).
  const now = applications.dataUpdatedAt;
  const dryRun = (applications.data ?? []).find((a) => target && usableDryRun(a, target, now));

  const submit = (mode: 'dry_run' | 'apply') =>
    launch.mutate(
      {
        operation: 'migrate_apply',
        params: {
          plan_run: run.id,
          target_connection: target,
          mode,
          ...(mode === 'apply' ? { dry_run_run: dryRun?.id ?? null, confirm: target } : {}),
        },
      },
      { onSuccess: (created) => void navigate(`/runs/${created.id}`) },
    );

  return (
    <Stack>
      <Title order={4}>{t('migrate.apply.title')}</Title>
      {!allowed ? (
        <Text size="sm" c="dimmed">
          {me?.can_apply_ddl ? t('migrate.apply.ownerOnly') : t('migrate.apply.noPermission')}
        </Text>
      ) : blocked ? (
        <Text size="sm" c="dimmed">
          {t('migrate.apply.planBlocked')}
        </Text>
      ) : eligible.length === 0 ? (
        <Text size="sm" c="dimmed">
          {t('migrate.apply.noTargets', { engine: plan.target_engine })}
        </Text>
      ) : (
        <Stack>
          {launch.isError && !confirming && <ErrorAlert error={launch.error} />}
          <NativeSelect
            label={t('migrate.apply.target')}
            value={target}
            onChange={(event) => setTarget(event.currentTarget.value)}
            data={[
              { value: '', label: t('migrate.apply.chooseTarget') },
              ...eligible.map((c) => ({ value: c.alias, label: `${c.alias} · ${c.connection_name}` })),
            ]}
          />
          <Text size="sm" c="dimmed">
            {t('migrate.apply.steps')}
          </Text>
          <Group>
            <Button
              variant="light"
              disabled={!target}
              loading={launch.isPending}
              onClick={() => submit('dry_run')}
            >
              {t('migrate.apply.dryRun')}
            </Button>
            <Button color="red" disabled={!dryRun} onClick={() => setConfirming(true)}>
              {t('migrate.apply.open')}
            </Button>
          </Group>
          {target && !dryRun && (
            <Text size="xs" c="dimmed">
              {t('migrate.apply.needsDryRun')}
            </Text>
          )}
          <ConfirmApply
            key={target}
            alias={target}
            opened={confirming}
            pending={launch.isPending}
            error={confirming && launch.isError ? launch.error : null}
            onClose={() => {
              setConfirming(false);
              launch.reset();
            }}
            onConfirm={() => submit('apply')}
          />
        </Stack>
      )}
      {(applications.data ?? []).length > 0 && (
        <Table striped withTableBorder aria-label={t('migrate.apply.history')}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('migrate.apply.mode')}</Table.Th>
              <Table.Th>{t('migrate.apply.target')}</Table.Th>
              <Table.Th>{t('runs.createdAt')}</Table.Th>
              <Table.Th>{t('runs.statusLabel')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {(applications.data ?? []).map((a) => (
              <Table.Tr key={a.id}>
                <Table.Td>
                  <Anchor component={Link} to={`/runs/${a.id}`}>
                    {t(`migrate.apply.modes.${String(a.params['mode'])}`)}
                  </Anchor>
                </Table.Td>
                <Table.Td>{String(a.params['target_connection'])}</Table.Td>
                <Table.Td>{formatDateTime(a.created_at)}</Table.Td>
                <Table.Td>
                  <RunStatusBadge status={a.status} />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
