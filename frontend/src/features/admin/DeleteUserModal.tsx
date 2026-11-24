import { Alert, Button, Center, Group, List, Loader, Modal, Stack, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { TransferUserModal } from './TransferUserModal';
import { type User, type UserDeletionCheck, useDeleteUser, useDeletionCheck } from './useAdmin';

interface DeleteUserModalProps {
  user: User;
  onClose: () => void;
}

/** Lo que impide el borrado. Los proyectos y conexiones van como texto: un admin no ve los ajenos (404). */
function Blockers({ check }: { check: UserDeletionCheck }) {
  const { t } = useTranslation();
  return (
    <Stack gap="sm">
      <List size="sm">
        {check.reasons.map((reason) => (
          <List.Item key={reason}>{t(`admin.users.reasons.${reason}`)}</List.Item>
        ))}
      </List>
      {check.projects.length > 0 && (
        <Stack gap={4}>
          <Title order={4}>{t('admin.users.memberOf')}</Title>
          <List size="sm">
            {check.projects.map((p) => (
              <List.Item key={p.id}>
                {p.name} ({p.role ? t(`projects.roles.${p.role}`) : '—'})
              </List.Item>
            ))}
          </List>
        </Stack>
      )}
      {check.created_projects.length > 0 && (
        <Stack gap={4}>
          <Title order={4}>{t('admin.users.createdProjects')}</Title>
          <List size="sm">
            {check.created_projects.map((p) => (
              <List.Item key={p.id}>{p.name}</List.Item>
            ))}
          </List>
        </Stack>
      )}
      {check.connections.length > 0 && (
        <Stack gap={4}>
          <Title order={4}>{t('admin.users.blockingConnections')}</Title>
          <List size="sm">
            {check.connections.map((c) => (
              <List.Item key={c.id}>
                {c.name} ({t(`admin.users.${c.visibility}`)})
              </List.Item>
            ))}
          </List>
        </Stack>
      )}
    </Stack>
  );
}

/** Confirmación de borrado: primero consulta qué lo impide; si algo lo impide, lo muestra y no deja confirmar. */
export function DeleteUserModal({ user, onClose }: DeleteUserModalProps) {
  const { t } = useTranslation();
  const check = useDeletionCheck(user.id);
  const remove = useDeleteUser();
  const blocked = check.data && !check.data.can_delete;
  const [transferring, setTransferring] = useState(false);
  // Transferir resuelve todo salvo «es tu cuenta» y «último admin».
  const transferable =
    blocked && !check.data?.reasons.some((reason) => reason === 'self' || reason === 'last_admin');

  if (transferring) {
    return (
      <TransferUserModal
        user={user}
        onClose={() => setTransferring(false)}
        onDone={() => {
          setTransferring(false);
          void check.refetch();
        }}
      />
    );
  }

  return (
    <Modal opened onClose={onClose} title={t('admin.users.deleteTitle', { username: user.username })}>
      <Stack aria-live="polite">
        {check.isPending && (
          <Center>
            <Loader aria-label={t('admin.users.deleteChecking')} />
          </Center>
        )}
        {check.isError && <ErrorAlert error={check.error} />}
        {blocked && (
          <Alert color="orange" title={t('admin.users.deleteBlocked', { username: user.username })}>
            <Stack gap="sm">
              <Blockers check={check.data} />
              <Text size="sm">{t('admin.users.deleteBlockedHint')}</Text>
            </Stack>
          </Alert>
        )}
        {check.data?.can_delete && <Text>{t('admin.users.deleteConfirm', { username: user.username })}</Text>}
        {remove.isError && <ErrorAlert error={remove.error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          {transferable && (
            <Button variant="light" onClick={() => setTransferring(true)}>
              {t('admin.users.transfer.open')}
            </Button>
          )}
          {check.data?.can_delete && (
            <Button
              color="red"
              loading={remove.isPending}
              onClick={() =>
                // Si algo cambió desde la comprobación (409), se vuelve a consultar para mostrar el motivo.
                remove.mutate(user.id, { onSuccess: onClose, onError: () => void check.refetch() })
              }
            >
              {t('admin.users.delete')}
            </Button>
          )}
        </Group>
      </Stack>
    </Modal>
  );
}
