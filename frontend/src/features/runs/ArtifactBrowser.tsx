import {
  Button,
  Card,
  Code,
  Group,
  Loader,
  NavLink,
  ScrollArea,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../components/ErrorAlert';
import { formatBytes } from '../../components/format';
import { type Artifact, downloadUrl, previewUrl, useArtifactText } from './useRuns';

// HTML y SVG se muestran en un iframe aislado: sin `allow-scripts` ni `allow-same-origin` (origen opaco); la API
// añade además una CSP `sandbox`.
const SANDBOXED = new Set(['html', 'graphs']);
const KIND_ORDER = ['html', 'markdown', 'sql', 'graphs', 'word', 'excel', 'log', 'manifest', 'other'];

function Preview({ runId, artifact }: { runId: string; artifact: Artifact }) {
  const { t } = useTranslation();
  const sandboxed = SANDBOXED.has(artifact.kind);
  const text = useArtifactText(runId, artifact.previewable && !sandboxed ? artifact : null);

  if (!artifact.previewable) {
    return <Text c="dimmed">{t('runs.artifactsBrowser.noPreview')}</Text>;
  }
  if (sandboxed) {
    return (
      <iframe
        title={t('runs.artifactsBrowser.previewOf', { path: artifact.path })}
        src={previewUrl(runId, artifact.id)}
        sandbox=""
        referrerPolicy="no-referrer"
        style={{ width: '100%', height: 420, border: '1px solid var(--mantine-color-default-border)' }}
      />
    );
  }
  if (text.isPending) return <Loader size="sm" aria-label={t('common.loading')} />;
  if (text.isError) return <ErrorAlert error={text.error} />;
  return (
    <ScrollArea h={420}>
      <Code block>{text.data}</Code>
    </ScrollArea>
  );
}

/** Navegador de artefactos de una ejecución: lista por tipo y vista previa. */
export function ArtifactBrowser({ runId, artifacts }: { runId: string; artifacts: Artifact[] }) {
  const { t } = useTranslation();
  const sorted = [...artifacts].sort(
    (a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind) || a.path.localeCompare(b.path),
  );
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = sorted.find((a) => a.id === selectedId) ?? sorted.find((a) => a.previewable) ?? sorted[0];

  if (artifacts.length === 0) {
    return <Text c="dimmed">{t('runs.artifactsBrowser.empty')}</Text>;
  }
  return (
    <SimpleGrid cols={{ base: 1, md: 3 }}>
      <Stack gap={2} aria-label={t('runs.artifactsBrowser.list')} role="list">
        {sorted.map((artifact) => (
          <div role="listitem" key={artifact.id}>
            <NavLink
              active={artifact.id === selected?.id}
              label={artifact.path.split('/').at(-1)}
              description={`${t(`runs.kinds.${artifact.kind}`, { defaultValue: artifact.kind })} · ${formatBytes(artifact.size_bytes)}`}
              onClick={() => setSelectedId(artifact.id)}
              aria-current={artifact.id === selected?.id ? 'true' : undefined}
            />
          </div>
        ))}
      </Stack>
      {selected && (
        <Card withBorder style={{ gridColumn: 'span 2' }}>
          <Stack>
            <Group justify="space-between">
              <Title order={4}>
                <Code>{selected.path}</Code>
              </Title>
              <Button
                component="a"
                href={downloadUrl(runId, selected.id)}
                size="xs"
                variant="light"
                aria-label={t('runs.artifactsBrowser.downloadLabel', { path: selected.path })}
              >
                {t('runs.artifactsBrowser.download')}
              </Button>
            </Group>
            <Preview runId={runId} artifact={selected} />
            <Text size="xs" c="dimmed">
              SHA-256 {selected.sha256.slice(0, 16)}…
            </Text>
          </Stack>
        </Card>
      )}
    </SimpleGrid>
  );
}
