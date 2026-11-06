import {
  Anchor,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Modal,
  Stack,
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

import { DataTable } from '../../components/DataTable';
import type { Column } from '../../components/tableState';
import { useListState } from '../../components/useListState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { zodResolver } from '../../components/zodResolver';
import { type Project, useCreateProject, useProjects } from './useProjects';

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
  const list = useListState();
  const [creating, setCreating] = useState(false);
  const { data, isPending, isError, error } = useProjects(list.state);
  const columns: Column<Project>[] = [
    {
      key: 'name',
      header: t('projects.name'),
      sortable: true,
      rowHeader: true,
      cell: (p) => (
        <Anchor component={Link} to={`/projects/${p.id}`}>
          {p.name}
        </Anchor>
      ),
    },
    {
      key: 'description',
      header: t('projects.description'),
      cell: (p) => (
        <Text size="sm" lineClamp={1}>
          {p.description || '—'}
        </Text>
      ),
    },
    {
      key: 'role',
      header: t('projects.myRole'),
      sortable: true,
      cell: (p) => <Badge variant="light">{t(`projects.roles.${p.my_role}`)}</Badge>,
    },
    {
      key: 'updated_at',
      header: t('projects.updatedAt'),
      sortable: true,
      cell: (p) => formatDateTime(p.updated_at),
    },
  ];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{t('projects.title')}</Title>
        <Button onClick={() => setCreating(true)}>{t('projects.new')}</Button>
      </Group>
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && (
        <DataTable
          mode="server"
          label={t('projects.title')}
          searchLabel={t('projects.search')}
          empty={t('projects.empty')}
          columns={columns}
          rowKey={(p) => p.id}
          rows={data.items}
          total={data.total}
          {...list.table}
        />
      )}
      {creating && <CreateProjectModal opened onClose={() => setCreating(false)} />}
    </Stack>
  );
}
