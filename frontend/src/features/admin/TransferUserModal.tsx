import {
  Alert,
  Button,
  Center,
  Group,
  List,
  Loader,
  Modal,
  Select,
  Stack,
  Switch,
  Text,
  Title,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import {
  type TransferItem,
  type User,
  type UserTransfer,
  useActiveUserOptions,
  useTransferPreview,
  useTransferUser,
} from './useAdmin';

interface TransferUserModalProps {
  user: User;
  /** Se cierra sin transferir. */
  onClose: () => void;
  /** Transferencia hecha. */
  onDone: () => void;
}

function Items({
  title,
  items,
  render,
}: {
  title: string;
  items: TransferItem[];
  render: (i: TransferItem) => string;
}) {
  if (items.length === 0) return null;
  return (
    <Stack gap={4}>
      <Title order={4}>{title}</Title>
      <List size="sm">
        {items.map((item) => (
          <List.Item key={item.id}>{render(item)}</List.Item>
        ))}
      </List>
    </Stack>
  );
}

function Preview({ preview, removeMemberships }: { preview: UserTransfer; removeMemberships: boolean }) {
  const { t } = useTranslation();
  const renamed = (i: TransferItem) =>
    i.new_name ? t('admin.users.transfer.renamed', { name: i.name, newName: i.new_name }) : i.name;
  const nothing =
    preview.created_projects.length +
      preview.owned_projects.length +
      preview.connections.length +
      (removeMemberships ? preview.other_memberships.length : 0) ===
    0;
  return (
    <Stack gap="sm">
      {preview.reasons.length > 0 && (
        <Alert color="orange" title={t('admin.users.transfer.blocked')}>
          <List size="sm">
            {preview.reasons.map((reason) => (
              <List.Item key={reason}>{t(`admin.users.transfer.reasons.${reason}`)}</List.Item>
            ))}
          </List>
          {preview.busy_projects.length > 0 && (
            <Text size="sm" mt="xs">
              {preview.busy_projects.map((p) => p.name).join(', ')}
            </Text>
          )}
        </Alert>
      )}
      {nothing && <Text size="sm">{t('admin.users.transfer.nothing')}</Text>}
      <Items title={t('admin.users.transfer.created')} items={preview.created_projects} render={renamed} />
      <Items title={t('admin.users.transfer.owned')} items={preview.owned_projects} render={(i) => i.name} />
      <Items
        title={t('admin.users.transfer.connections')}
        items={preview.connections}
        render={(i) => `${renamed(i)} (${t(`admin.users.${i.visibility ?? 'private'}`)})`}
      />
      {removeMemberships && (
        <Items
          title={t('admin.users.transfer.removed')}
          items={preview.other_memberships}
          render={(i) => `${i.name} (${t(`projects.roles.${i.role ?? 'viewer'}`)})`}
        />
      )}
    </Stack>
  );
}

/** Ceder a otro usuario activo los proyectos y conexiones que impiden borrar `user` (ADR-013). */
export function TransferUserModal({ user, onClose, onDone }: TransferUserModalProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [typed] = useDebouncedValue(search, 300);
  const [target, setTarget] = useState<{ value: string; label: string } | null>(null);
  const targetId = target === null ? null : Number(target.value);
  const [removeMemberships, setRemoveMemberships] = useState(true);
  // Al elegir, Mantine pone la etiqueta como texto de búsqueda: no se busca por ella.
  const options = useActiveUserOptions(typed === target?.label ? '' : typed);
  const preview = useTransferPreview(user.id, targetId);
  const transfer = useTransferUser();
  const found = (options.data?.items ?? [])
    .filter((u) => u.id !== user.id)
    .map((u) => ({ value: String(u.id), label: `${u.username} · ${u.display_name}` }));
  // El elegido sigue en la lista aunque la búsqueda ya no lo devuelva.
  const data = target && !found.some((o) => o.value === target.value) ? [target, ...found] : found;

  return (
    <Modal
      opened
      onClose={onClose}
      title={t('admin.users.transfer.title', { username: user.username })}
      size="lg"
    >
      <Stack>
        <Text size="sm">{t('admin.users.transfer.intro')}</Text>
        <Select
          label={t('admin.users.transfer.target')}
          description={t('admin.users.transfer.targetHint')}
          searchable
          data={data}
          // El servidor ya filtra por usuario o nombre: no volver a filtrar.
          filter={({ options: all }) => all}
          searchValue={search}
          onSearchChange={setSearch}
          value={target?.value ?? null}
          onChange={(value, option) => setTarget(value ? { value, label: option.label } : null)}
          nothingFoundMessage={t('admin.users.empty')}
          rightSection={options.isFetching ? <Loader size="xs" aria-label={t('common.loading')} /> : null}
        />
        <Switch
          label={t('admin.users.transfer.removeMemberships')}
          description={t('admin.users.transfer.removeMembershipsHint')}
          checked={removeMemberships}
          onChange={(event) => setRemoveMemberships(event.currentTarget.checked)}
        />
        <Stack aria-live="polite">
          {preview.isFetching && !preview.data && (
            <Center>
              <Loader aria-label={t('admin.users.transfer.checking')} />
            </Center>
          )}
          {preview.isError && <ErrorAlert error={preview.error} />}
          {preview.data && <Preview preview={preview.data} removeMemberships={removeMemberships} />}
        </Stack>
        {transfer.isError && <ErrorAlert error={transfer.error} />}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            disabled={!preview.data?.can_transfer || targetId === null}
            loading={transfer.isPending}
            onClick={() =>
              targetId !== null &&
              transfer.mutate(
                { id: user.id, targetId, removeMemberships },
                // Si algo cambió desde la vista previa (409), se vuelve a consultar para enseñar el motivo.
                { onSuccess: onDone, onError: () => void preview.refetch() },
              )
            }
          >
            {t('admin.users.transfer.submit')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
