import {
  Button,
  Code,
  Group,
  Loader,
  Modal,
  NativeSelect,
  Pagination,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  VisuallyHidden,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { useMe } from '../auth/useAuth';
import { useConnections } from '../connections/useConnections';
import { LaunchRunModal } from '../runs/LaunchRunModal';
import { RunsTable } from '../runs/RunsTable';
import { PAGE_SIZE, type RunStatus, useProjectRuns } from '../runs/useRuns';
import {
  canRole,
  type Project,
  type ProjectRole,
  useAddMember,
  useAddProjectConnection,
  useDeleteProject,
  useMembers,
  useProjectConnections,
  useRemoveMember,
  useRemoveProjectConnection,
  useUpdateMember,
  useUpdateProject,
} from './useProjects';

const STATUSES: RunStatus[] = ['queued', 'running', 'succeeded', 'failed', 'cancelled', 'purged'];
const ROLES: ProjectRole[] = ['owner', 'editor', 'viewer'];

export function RunsTab({ project }: { project: Project }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [launching, setLaunching] = useState(false);
  const runs = useProjectRuns(project.id, { status, q: q.trim() }, page);
  const connections = useProjectConnections(project.id);

  return (
    <Stack>
      <Group justify="space-between" align="flex-end">
        <Group align="flex-end">
          <Select
            label={t('runs.statusLabel')}
            placeholder={t('runs.allStatuses')}
            data={STATUSES.map((s) => ({ value: s, label: t(`runs.status.${s}`) }))}
            value={status}
            onChange={(next) => {
              setStatus(next as RunStatus | null);
              setPage(1);
            }}
            clearable
            w={200}
          />
          <TextInput
            label={t('runs.search')}
            value={q}
            onChange={(event) => {
              setQ(event.currentTarget.value);
              setPage(1);
            }}
            w={260}
          />
        </Group>
        {canRole(project.my_role, 'editor') && (
          <Button onClick={() => setLaunching(true)}>{t('runs.launch.open')}</Button>
        )}
      </Group>
      {runs.isPending && <Loader aria-label={t('common.loading')} />}
      {runs.isError && <ErrorAlert error={runs.error} />}
      {runs.data && runs.data.items.length === 0 && <Text c="dimmed">{t('runs.emptyProject')}</Text>}
      {runs.data && runs.data.items.length > 0 && <RunsTable runs={runs.data.items} />}
      {runs.data && runs.data.total > PAGE_SIZE && (
        <Pagination total={Math.ceil(runs.data.total / PAGE_SIZE)} value={page} onChange={setPage} />
      )}
      {launching && (
        <LaunchRunModal
          projectId={project.id}
          connections={connections.data ?? []}
          opened
          onClose={() => setLaunching(false)}
        />
      )}
    </Stack>
  );
}

export function ConnectionsTab({ project }: { project: Project }) {
  const { t } = useTranslation();
  const links = useProjectConnections(project.id);
  const available = useConnections('', 1);
  const add = useAddProjectConnection(project.id);
  const remove = useRemoveProjectConnection(project.id);
  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [alias, setAlias] = useState('');
  const editor = canRole(project.my_role, 'editor');

  const onAdd = () => {
    if (!connectionId || !alias.trim()) return;
    add.mutate(
      { connection_id: Number(connectionId), alias: alias.trim().toLowerCase() },
      {
        onSuccess: () => {
          setConnectionId(null);
          setAlias('');
        },
      },
    );
  };

  return (
    <Stack>
      <Text c="dimmed">{t('projects.connectionsIntro')}</Text>
      {editor && (
        <Group align="flex-end">
          <NativeSelect
            label={t('projects.connection')}
            data={[
              { value: '', label: t('projects.chooseConnection') },
              ...(available.data?.items ?? []).map((c) => ({
                value: String(c.id),
                label: `${c.name} (${c.db_type})`,
              })),
            ]}
            value={connectionId ?? ''}
            onChange={(event) => setConnectionId(event.currentTarget.value || null)}
            w={300}
          />
          <TextInput
            label={t('projects.alias')}
            description={t('projects.aliasHint')}
            value={alias}
            onChange={(event) => setAlias(event.currentTarget.value)}
            w={220}
          />
          <Button onClick={onAdd} loading={add.isPending} disabled={!connectionId || !alias.trim()}>
            {t('projects.addConnection')}
          </Button>
        </Group>
      )}
      {add.isError && <ErrorAlert error={add.error} />}
      {remove.isError && <ErrorAlert error={remove.error} />}
      {links.isPending && <Loader aria-label={t('common.loading')} />}
      {links.isError && <ErrorAlert error={links.error} />}
      {links.data && links.data.length === 0 && <Text c="dimmed">{t('projects.noConnections')}</Text>}
      {links.data && links.data.length > 0 && (
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('projects.alias')}</Table.Th>
              <Table.Th>{t('projects.connection')}</Table.Th>
              <Table.Th>{t('connections.engine')}</Table.Th>
              <Table.Th>{t('connections.access')}</Table.Th>
              {editor && (
                <Table.Th>
                  <VisuallyHidden>{t('common.actions')}</VisuallyHidden>
                </Table.Th>
              )}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {links.data.map((link) => (
              <Table.Tr key={link.id}>
                <Table.Td>
                  <Code>{link.alias}</Code>
                </Table.Td>
                <Table.Td>{link.connection_name}</Table.Td>
                <Table.Td>{link.db_type}</Table.Td>
                <Table.Td>{link.read_only ? t('connections.readOnly') : t('projects.readWrite')}</Table.Td>
                {editor && (
                  <Table.Td>
                    <Button
                      size="xs"
                      color="red"
                      variant="light"
                      onClick={() => remove.mutate(link.alias)}
                      aria-label={t('projects.removeConnectionLabel', { alias: link.alias })}
                    >
                      {t('admin.allowlist.remove')}
                    </Button>
                  </Table.Td>
                )}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}

export function MembersTab({ project }: { project: Project }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const members = useMembers(project.id);
  const add = useAddMember(project.id);
  const update = useUpdateMember(project.id);
  const remove = useRemoveMember(project.id);
  const [username, setUsername] = useState('');
  const [role, setRole] = useState<ProjectRole>('viewer');
  const owner = canRole(project.my_role, 'owner');
  const roleOptions = ROLES.map((r) => ({ value: r, label: t(`projects.roles.${r}`) }));

  return (
    <Stack>
      {owner && (
        <Group align="flex-end">
          <TextInput
            label={t('auth.username')}
            value={username}
            onChange={(event) => setUsername(event.currentTarget.value)}
            w={240}
          />
          <Select
            label={t('projects.role')}
            data={roleOptions}
            value={role}
            onChange={(next) => setRole((next as ProjectRole | null) ?? 'viewer')}
            allowDeselect={false}
            w={180}
          />
          <Button
            disabled={!username.trim()}
            loading={add.isPending}
            onClick={() =>
              add.mutate({ username: username.trim(), role }, { onSuccess: () => setUsername('') })
            }
          >
            {t('projects.addMember')}
          </Button>
        </Group>
      )}
      {[add, update, remove].map((m, i) => (m.isError ? <ErrorAlert key={i} error={m.error} /> : null))}
      {members.isPending && <Loader aria-label={t('common.loading')} />}
      {members.isError && <ErrorAlert error={members.error} />}
      {members.data && (
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('auth.username')}</Table.Th>
              <Table.Th>{t('admin.users.displayName')}</Table.Th>
              <Table.Th>{t('projects.role')}</Table.Th>
              <Table.Th>
                <VisuallyHidden>{t('common.actions')}</VisuallyHidden>
              </Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {members.data.map((member) => {
              const self = member.user_id === me?.id;
              return (
                <Table.Tr key={member.user_id}>
                  <Table.Td>{member.username}</Table.Td>
                  <Table.Td>{member.display_name}</Table.Td>
                  <Table.Td>
                    {owner ? (
                      <Select
                        aria-label={t('projects.roleOf', { username: member.username })}
                        data={roleOptions}
                        value={member.role}
                        onChange={(next) =>
                          next && update.mutate({ userId: member.user_id, role: next as ProjectRole })
                        }
                        allowDeselect={false}
                        w={160}
                      />
                    ) : (
                      t(`projects.roles.${member.role}`)
                    )}
                  </Table.Td>
                  <Table.Td>
                    {(owner || self) && (
                      <Button
                        size="xs"
                        color="red"
                        variant="light"
                        aria-label={
                          self
                            ? t('projects.leave')
                            : t('projects.removeMemberLabel', { username: member.username })
                        }
                        onClick={() =>
                          remove.mutate(member.user_id, {
                            onSuccess: () => (self ? void navigate('/projects') : undefined),
                          })
                        }
                      >
                        {self ? t('projects.leave') : t('admin.allowlist.remove')}
                      </Button>
                    )}
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}

export function SettingsTab({ project }: { project: Project }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const update = useUpdateProject(project.id);
  const remove = useDeleteProject(project.id);
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description);
  const [confirm, setConfirm] = useState(false);

  return (
    <Stack maw={560}>
      {update.isError && <ErrorAlert error={update.error} />}
      <TextInput
        label={t('projects.name')}
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        required
      />
      <Textarea
        label={t('projects.description')}
        value={description}
        onChange={(e) => setDescription(e.currentTarget.value)}
        autosize
        minRows={2}
      />
      <Group>
        <Button
          loading={update.isPending}
          disabled={!name.trim()}
          onClick={() => update.mutate({ name: name.trim(), description: description.trim() })}
        >
          {t('common.save')}
        </Button>
        <Button color="red" variant="light" onClick={() => setConfirm(true)}>
          {t('projects.delete')}
        </Button>
      </Group>
      <Modal opened={confirm} onClose={() => setConfirm(false)} title={t('projects.deleteTitle')}>
        <Stack>
          <Text>{t('projects.deleteBody', { name: project.name })}</Text>
          {remove.isError && <ErrorAlert error={remove.error} />}
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirm(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              color="red"
              loading={remove.isPending}
              onClick={() => remove.mutate(undefined, { onSuccess: () => void navigate('/projects') })}
            >
              {t('common.delete')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
