import { Alert, Anchor, Button, Group, List, Modal, Stack, Text, TextInput } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { ErrorAlert } from '../../../components/ErrorAlert';
import { useMe } from '../../auth/useAuth';
import { useProjectConnections } from '../../projects/useProjects';
import { isActive, type RunDetail, useLaunchRun } from '../useRuns';
import { useDumpConstraints } from './useDump';

/**
 * Constraints que un volcado interrumpido dejó desactivadas en el destino y la acción «Restaurar constraints» (G31):
 * mismos controles que el volcado (permiso `can_write_data` + owner, destino no `read_only`, alias escrito a mano).
 */
export function PendingConstraints({ run }: { run: RunDetail }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const connections = useProjectConnections(run.project_id);
  const launch = useLaunchRun(run.project_id);
  const pending = useDumpConstraints(run.id, !isActive(run.status) && run.status !== 'purged');
  const [opened, setOpened] = useState(false);
  const [typed, setTyped] = useState('');

  const data = pending.data;
  if (!data?.pending) return null;
  const alias = data.target_connection ?? '';
  const target = (connections.data ?? []).find((c) => c.alias === alias);
  const allowed = Boolean(me?.can_write_data) && run.my_role === 'owner';
  const reason = !allowed
    ? me?.can_write_data
      ? t('dump.restore.ownerOnly')
      : t('dump.restore.noPermission')
    : target?.read_only
      ? t('dump.apply.readOnly', { alias })
      : null;
  const objects = [
    ...(data.tables ?? []),
    ...(data.constraints ?? []).map((c) => `${c.table}.${c.constraint}`),
  ];
  const close = () => {
    setOpened(false);
    setTyped('');
    launch.reset();
  };

  return (
    <Alert color="red" title={t('dump.restore.title')}>
      <Stack gap="xs">
        <Text size="sm">{t('dump.restore.body', { alias, count: objects.length })}</Text>
        {objects.length > 0 && (
          <List size="sm">
            {objects.map((name) => (
              <List.Item key={name}>{name}</List.Item>
            ))}
          </List>
        )}
        {data.restore_run ? (
          <Anchor component={Link} to={`/runs/${data.restore_run}`} size="sm">
            {t('dump.restore.running')}
          </Anchor>
        ) : reason ? (
          <Text size="sm" c="dimmed">
            {reason}
          </Text>
        ) : (
          <Group>
            <Button color="red" variant="light" onClick={() => setOpened(true)}>
              {t('dump.restore.open')}
            </Button>
          </Group>
        )}
      </Stack>
      <Modal opened={opened} onClose={close} title={t('dump.restore.confirmTitle')}>
        <Stack>
          {launch.isError && <ErrorAlert error={launch.error} />}
          <Text size="sm">{t('dump.restore.confirmBody', { alias })}</Text>
          <TextInput
            label={t('dump.apply.typeAlias', { alias })}
            value={typed}
            onChange={(event) => setTyped(event.currentTarget.value)}
            autoComplete="off"
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={close}>
              {t('common.cancel')}
            </Button>
            <Button
              color="red"
              disabled={typed !== alias}
              loading={launch.isPending}
              onClick={() =>
                launch.mutate(
                  { operation: 'dump_restore', params: { dump_run: run.id, confirm: typed } },
                  { onSuccess: (created) => void navigate(`/runs/${created.id}`) },
                )
              }
            >
              {t('dump.restore.submit')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Alert>
  );
}
