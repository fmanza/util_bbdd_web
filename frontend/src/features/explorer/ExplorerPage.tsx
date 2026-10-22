import {
  Anchor,
  Button,
  Card,
  Center,
  Checkbox,
  Grid,
  Group,
  Loader,
  NativeSelect,
  NavLink,
  ScrollArea,
  Stack,
  Tabs,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { useConnection } from '../connections/useConnections';
import { NamedQueriesPanel } from './NamedQueriesPanel';
import { ObjectDetail, type SelectedObject } from './ObjectDetail';
import { useRefreshSchema, useSchemas, useSchemaTree } from './useExplorer';

function MetadataPanel({ connectionId }: { connectionId: number }) {
  const { t } = useTranslation();
  const schemas = useSchemas(connectionId);
  const [showSystem, setShowSystem] = useState(false);
  const [chosen, setChosen] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [selected, setSelected] = useState<SelectedObject | null>(null);
  const schema = chosen ?? schemas.data?.default ?? schemas.data?.schemas[0]?.name ?? null;
  const tree = useSchemaTree(connectionId, schema);
  const refresh = useRefreshSchema(connectionId);

  const visibleSchemas = (schemas.data?.schemas ?? []).filter(
    (s) => showSystem || !s.system || s.name === schema,
  );
  const groups = useMemo(() => {
    const term = filter.trim().toLowerCase();
    const match = (name: string) => !term || name.toLowerCase().includes(term);
    return {
      table: (tree.data?.tables ?? []).filter((o) => match(o.name)),
      view: (tree.data?.views ?? []).filter((o) => match(o.name)),
      routine: (tree.data?.routines ?? []).filter((o) => match(o.name)),
    };
  }, [tree.data, filter]);

  if (schemas.isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (schemas.isError) return <ErrorAlert error={schemas.error} />;

  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 4 }}>
        <Stack gap="xs">
          <NativeSelect
            label={t('explorer.schema')}
            data={visibleSchemas.map((s) => ({
              value: s.name,
              label: s.system ? `${s.name} (${t('explorer.system')})` : s.name,
            }))}
            value={schema ?? ''}
            onChange={(event) => {
              setChosen(event.currentTarget.value);
              setSelected(null);
            }}
          />
          <Checkbox
            label={t('explorer.showSystem')}
            checked={showSystem}
            onChange={(event) => setShowSystem(event.currentTarget.checked)}
          />
          <TextInput
            label={t('explorer.filter')}
            value={filter}
            onChange={(event) => setFilter(event.currentTarget.value)}
          />
          <Group justify="space-between">
            <Text size="xs" c="dimmed">
              {tree.data ? t('explorer.fetchedAt', { date: formatDateTime(tree.data.fetched_at) }) : ''}
            </Text>
            <Button
              size="xs"
              variant="light"
              loading={refresh.isPending || tree.isFetching}
              disabled={!schema}
              onClick={() => schema && refresh.mutate(schema)}
            >
              {t('explorer.refresh')}
            </Button>
          </Group>
          {tree.isPending && schema && <Loader size="sm" aria-label={t('common.loading')} />}
          {tree.isError && <ErrorAlert error={tree.error} />}
          {tree.data && (
            <ScrollArea h={520} type="auto">
              <nav aria-label={t('explorer.objects')}>
                {(['table', 'view', 'routine'] as const).map((kind) => (
                  <NavLink
                    key={kind}
                    label={t(`explorer.groups.${kind}`, { count: groups[kind].length })}
                    defaultOpened={kind === 'table'}
                    childrenOffset={12}
                  >
                    {groups[kind].map((item) => (
                      <NavLink
                        key={`${kind}-${item.name}`}
                        label={item.name}
                        active={selected?.kind === kind && selected.name === item.name}
                        onClick={() => setSelected({ kind, name: item.name })}
                      />
                    ))}
                  </NavLink>
                ))}
              </nav>
            </ScrollArea>
          )}
        </Stack>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 8 }}>
        <Card withBorder mih={300}>
          {selected && schema ? (
            <ObjectDetail
              connectionId={connectionId}
              schema={schema}
              object={selected}
              onOpenTable={(table) => setSelected({ kind: 'table', name: table })}
            />
          ) : (
            <Text c="dimmed">{t('explorer.chooseObject')}</Text>
          )}
        </Card>
      </Grid.Col>
    </Grid>
  );
}

export function ExplorerPage() {
  const { t } = useTranslation();
  const connectionId = Number(useParams().connectionId);
  const connection = useConnection(connectionId);
  const [tab, setTab] = useState<string | null>('metadata');

  if (connection.isError) return <ErrorAlert error={connection.error} />;

  return (
    <Stack>
      <Stack gap={2}>
        <Title order={2}>{t('explorer.title', { name: connection.data?.name ?? '…' })}</Title>
        <Anchor component={Link} to={`/connections/${connectionId}`} size="sm">
          {t('explorer.backToConnection')}
        </Anchor>
      </Stack>
      <Tabs value={tab} onChange={setTab} keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="metadata">{t('explorer.tabs.metadata')}</Tabs.Tab>
          <Tabs.Tab value="queries">{t('explorer.tabs.queries')}</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="metadata" pt="md">
          <MetadataPanel connectionId={connectionId} />
        </Tabs.Panel>
        <Tabs.Panel value="queries" pt="md">
          <NamedQueriesPanel connectionId={connectionId} />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
