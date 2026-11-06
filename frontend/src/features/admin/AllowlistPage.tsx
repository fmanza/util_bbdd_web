import { Button, Center, Code, Group, Loader, Modal, Stack, Text, TextInput, Title } from '@mantine/core';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

import { DataTable } from '../../components/DataTable';
import type { Column } from '../../components/tableState';
import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { zodResolver } from '../../components/zodResolver';
import {
  type AllowlistEntry,
  useAddAllowlistEntry,
  useAllowlist,
  useDeleteAllowlistEntry,
} from '../connections/useConnections';

interface EntryForm {
  pattern: string;
  description: string;
}

export function AllowlistPage() {
  const { t } = useTranslation();
  const { data, isPending, isError, error } = useAllowlist();
  const add = useAddAllowlistEntry();
  const remove = useDeleteAllowlistEntry();
  const [deleting, setDeleting] = useState<AllowlistEntry | null>(null);
  const form = useForm<EntryForm>({
    resolver: zodResolver(
      z.object({
        pattern: z.string().trim().min(1, t('auth.required')).max(255),
        description: z.string().trim().max(255),
      }),
    ),
    defaultValues: { pattern: '', description: '' },
  });

  const onSubmit = form.handleSubmit((values) =>
    add.mutate(values, { onSuccess: () => form.reset({ pattern: '', description: '' }) }),
  );
  const closeDelete = () => {
    setDeleting(null);
    remove.reset();
  };

  const columns: Column<AllowlistEntry>[] = [
    {
      key: 'pattern',
      header: t('admin.allowlist.pattern'),
      sortable: true,
      searchable: true,
      value: (e) => e.pattern,
      cell: (e) => <Code>{e.pattern}</Code>,
    },
    {
      key: 'description',
      header: t('admin.allowlist.description'),
      sortable: true,
      searchable: true,
      value: (e) => e.description,
      cell: (e) => e.description || '—',
    },
    {
      key: 'created_at',
      header: t('admin.allowlist.createdAt'),
      sortable: true,
      value: (e) => e.created_at,
      cell: (e) => formatDateTime(e.created_at),
    },
    {
      key: 'actions',
      header: t('common.actions'),
      hiddenHeader: true,
      cell: (entry) => (
        <Button
          size="xs"
          color="red"
          variant="light"
          onClick={() => setDeleting(entry)}
          aria-label={t('admin.allowlist.removeLabel', { pattern: entry.pattern })}
        >
          {t('admin.allowlist.remove')}
        </Button>
      ),
    },
  ];

  return (
    <Stack maw={900}>
      <Title order={2}>{t('admin.allowlist.title')}</Title>
      <Text c="dimmed">{t('admin.allowlist.intro')}</Text>
      <form onSubmit={onSubmit} noValidate aria-label={t('admin.allowlist.add')}>
        <Group align="flex-start">
          <Controller
            control={form.control}
            name="pattern"
            render={({ field }) => (
              <TextInput
                {...field}
                label={t('admin.allowlist.pattern')}
                description={t('admin.allowlist.patternHint')}
                required
                error={form.formState.errors.pattern?.message}
                w={300}
              />
            )}
          />
          <Controller
            control={form.control}
            name="description"
            render={({ field }) => <TextInput {...field} label={t('admin.allowlist.description')} w={260} />}
          />
          <Button type="submit" mt={50} loading={add.isPending}>
            {t('admin.allowlist.add')}
          </Button>
        </Group>
      </form>
      {add.isError && <ErrorAlert error={add.error} />}
      {isPending && (
        <Center>
          <Loader aria-label={t('common.loading')} />
        </Center>
      )}
      {isError && <ErrorAlert error={error} />}
      {data && data.length === 0 && (
        <Text c="orange" fw={500}>
          {t('admin.allowlist.empty')}
        </Text>
      )}
      {data && data.length > 0 && (
        <DataTable
          mode="client"
          label={t('admin.allowlist.title')}
          searchLabel={t('admin.allowlist.search')}
          empty={t('table.noMatches')}
          columns={columns}
          rowKey={(entry) => entry.id}
          rows={data}
          initialSort={{ key: 'pattern', order: 'asc' }}
        />
      )}
      <Modal opened={deleting !== null} onClose={closeDelete} title={t('admin.allowlist.removeTitle')}>
        {deleting && (
          <Stack>
            <Text>{t('admin.allowlist.removeBody', { pattern: deleting.pattern })}</Text>
            {remove.isError && <ErrorAlert error={remove.error} />}
            <Group justify="flex-end">
              <Button variant="default" onClick={closeDelete}>
                {t('common.cancel')}
              </Button>
              <Button
                color="red"
                loading={remove.isPending}
                onClick={() => remove.mutate(deleting, { onSuccess: closeDelete })}
              >
                {t('admin.allowlist.remove')}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
