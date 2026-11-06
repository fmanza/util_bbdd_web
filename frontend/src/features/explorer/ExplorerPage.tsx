import {
  Anchor,
  Button,
  Card,
  Center,
  Box,
  Checkbox,
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
import { useMediaQuery } from '@mantine/hooks';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatDateTime } from '../../components/format';
import { useConnection } from '../connections/useConnections';
import { NamedQueriesPanel } from './NamedQueriesPanel';
import { ObjectDetail, type SelectedObject } from './ObjectDetail';
import { useRefreshSchema, useSchemas, useSchemaTree } from './useExplorer';

/** Alto mínimo de la vista en escritorio y margen inferior (el `padding` del `AppShell`). */
const MIN_HEIGHT = 480;
const BOTTOM = 16;
/** Breakpoint `md` de Mantine: por encima, árbol y ficha en dos columnas con el alto de la ventana. */
const DESKTOP = '(min-width: 62em)';
const MOBILE_TREE = 360;

/** Alto disponible desde el contenedor hasta el final de la ventana (en escritorio); se recalcula al redimensionar. */
function useFillHeight(enabled: boolean) {
  const ref = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number>(MIN_HEIGHT);
  useEffect(() => {
    if (!enabled) return undefined;
    const update = () => {
      const top = (ref.current?.getBoundingClientRect().top ?? 0) + window.scrollY;
      setHeight(Math.max(MIN_HEIGHT, Math.floor(window.innerHeight - top - BOTTOM)));
    };
    const frame = requestAnimationFrame(update);
    window.addEventListener('resize', update);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', update);
    };
  }, [enabled]);
  return [ref, height] as const;
}

function MetadataPanel({ connectionId }: { connectionId: number }) {
  const { t } = useTranslation();
  const desktop = useMediaQuery(DESKTOP) ?? false;
  const [layoutRef, layoutHeight] = useFillHeight(desktop);
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
    <Box
      ref={layoutRef}
      data-testid="explorer-layout"
      style={
        desktop
          ? {
              display: 'grid',
              gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 2fr)',
              gap: 'var(--mantine-spacing-md)',
              height: layoutHeight,
            }
          : { display: 'flex', flexDirection: 'column', gap: 'var(--mantine-spacing-md)' }
      }
    >
      <Stack gap="xs" style={{ minHeight: 0 }}>
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
          <ScrollArea
            h={desktop ? undefined : MOBILE_TREE}
            style={desktop ? { flex: 1, minHeight: 0 } : undefined}
            type="auto"
          >
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
      <Card
        withBorder
        style={{
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          height: desktop ? undefined : '70dvh',
        }}
      >
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
    </Box>
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
