import {
  Anchor,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Modal,
  Pagination,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';
import { z } from 'zod';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { zodResolver } from '../../components/zodResolver';
import { PAGE_SIZE, useCreateProject, useProjects } from './useProjects';

interface ProjectForm {
  name: string;
  description: string;
}

function CreateProjectModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const create = useCreateProject();
  const form = useForm<ProjectForm>({
    resolver: zodResolver(
      z.object({
        name: z.string().trim().min(1, t('auth.required')).max(100),
        description: z.string().trim().max(500),
      }),
    ),
    defaultValues: { name: '', description: '' },
  });
  const onSubmit = form.handleSubmit((values) =>
    create.mutate(values, { onSuccess: (project) => void navigate(`/projects/${project.id}`) }),
  );

  return (
    <Modal opened={opened} onClose={onClose} title={t('projects.createTitle')}>
      <form onSubmit={onSubmit} noValidate>
        <Stack>
          {create.isError && <ErrorAlert error={create.error} />}
          <Controller
            control={form.control}
            name="name"
            render={({ field }) => (
              <TextInput
                {...field}
                label={t('projects.name')}
                required
                error={form.formState.errors.name?.message}
                data-autofocus
              />
            )}
          />
          <Controller
            control={form.control}
            name="description"
            render={({ field }) => (
              <Textarea {...field} label={t('projects.description')} autosize minRows={2} />
            )}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={create.isPending}>
              {t('projects.create')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

export function ProjectsPage() {
  const { t } = useTranslation();
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const { data, isPending, isError, error } = useProjects(q.trim(), page);

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('projects.title')}</Title>
        <Button onClick={() => setCreating(true)}>{t('projects.new')}</Button>
      </Group>
      <TextInput
        label={t('projects.search')}
        value={q}
        onChange={(event) => {
          setQ(event.currentTarget.value);
          setPage(1);
        }}
        maw={320}
      />
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && data.items.length === 0 && <Text c="dimmed">{t('projects.empty')}</Text>}
      {data && data.items.length > 0 && (
        <Table.ScrollContainer minWidth={640}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('projects.name')}</Table.Th>
                <Table.Th>{t('projects.description')}</Table.Th>
                <Table.Th>{t('projects.myRole')}</Table.Th>
                <Table.Th>{t('projects.updatedAt')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.items.map((project) => (
                <Table.Tr key={project.id}>
                  <Table.Th scope="row">
                    <Anchor component={Link} to={`/projects/${project.id}`}>
                      {project.name}
                    </Anchor>
                  </Table.Th>
                  <Table.Td>
                    <Text size="sm" lineClamp={1}>
                      {project.description || '—'}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light">{t(`projects.roles.${project.my_role}`)}</Badge>
                  </Table.Td>
                  <Table.Td>{formatDateTime(project.updated_at)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {data && data.total > PAGE_SIZE && (
        <Pagination total={Math.ceil(data.total / PAGE_SIZE)} value={page} onChange={setPage} />
      )}
      {creating && <CreateProjectModal opened onClose={() => setCreating(false)} />}
    </Stack>
  );
}
