import { Badge, Center, Group, Loader, Stack, Tabs, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useParams, useSearchParams } from 'react-router';

import { ErrorAlert } from '../../components/ErrorAlert';
import { BulkTab } from '../bulk/BulkTab';
import { SqlConsole } from '../explorer/SqlConsole';
import { TemplatesPanel } from '../templates/TemplatesPanel';
import { ConnectionsTab, MembersTab, RunsTab, SettingsTab } from './ProjectTabs';
import { canRole, useProject } from './useProjects';

const TABS = ['runs', 'connections', 'members', 'templates', 'sql', 'bulk', 'settings'] as const;
type Tab = (typeof TABS)[number];

export function ProjectDetailPage() {
  const { t } = useTranslation();
  const id = Number(useParams().projectId);
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: project, isPending, isError, error } = useProject(id);

  if (isPending) {
    return (
      <Center>
        <Loader aria-label={t('common.loading')} />
      </Center>
    );
  }
  if (isError) {
    return <ErrorAlert error={error} />;
  }

  const owner = canRole(project.my_role, 'owner');
  const editor = canRole(project.my_role, 'editor');
  const requested = searchParams.get('tab') as Tab | null;
  const tab: Tab =
    requested &&
    TABS.includes(requested) &&
    (requested !== 'settings' || owner) &&
    ((requested !== 'sql' && requested !== 'bulk') || editor)
      ? requested
      : 'runs';

  return (
    <Stack>
      <Stack gap={4}>
        <Group gap="xs">
          <Title order={2}>{project.name}</Title>
          <Badge variant="light">{t(`projects.roles.${project.my_role}`)}</Badge>
        </Group>
        {project.description && <Text c="dimmed">{project.description}</Text>}
      </Stack>
      <Tabs
        value={tab}
        onChange={(next) => setSearchParams(next && next !== 'runs' ? { tab: next } : {}, { replace: true })}
      >
        <Tabs.List>
          <Tabs.Tab value="runs">{t('projects.tabs.runs')}</Tabs.Tab>
          <Tabs.Tab value="connections">{t('projects.tabs.connections')}</Tabs.Tab>
          <Tabs.Tab value="members">{t('projects.tabs.members')}</Tabs.Tab>
          <Tabs.Tab value="templates">{t('projects.tabs.templates')}</Tabs.Tab>
          {editor && <Tabs.Tab value="sql">{t('projects.tabs.sql')}</Tabs.Tab>}
          {editor && <Tabs.Tab value="bulk">{t('projects.tabs.bulk')}</Tabs.Tab>}
          {owner && <Tabs.Tab value="settings">{t('projects.tabs.settings')}</Tabs.Tab>}
        </Tabs.List>
        <Tabs.Panel value="runs" pt="md">
          <RunsTab project={project} />
        </Tabs.Panel>
        <Tabs.Panel value="connections" pt="md">
          <ConnectionsTab project={project} />
        </Tabs.Panel>
        <Tabs.Panel value="members" pt="md">
          <MembersTab project={project} />
        </Tabs.Panel>
        <Tabs.Panel value="templates" pt="md">
          {/* Solo al abrir la pestaña: evita pedir las plantillas en cada visita al proyecto. */}
          {tab === 'templates' && (
            <TemplatesPanel scope={{ kind: 'project', projectId: project.id }} canEdit={editor} />
          )}
        </Tabs.Panel>
        {editor && (
          <Tabs.Panel value="sql" pt="md">
            <SqlConsole projectId={project.id} />
          </Tabs.Panel>
        )}
        {editor && (
          <Tabs.Panel value="bulk" pt="md">
            <BulkTab project={project} />
          </Tabs.Panel>
        )}
        {owner && (
          <Tabs.Panel value="settings" pt="md">
            <SettingsTab project={project} />
          </Tabs.Panel>
        )}
      </Tabs>
    </Stack>
  );
}
