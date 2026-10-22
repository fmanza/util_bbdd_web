import { Anchor, Button, Card, Group, Image, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { formatBytes } from '../../components/format';
import { type Artifact, type RunDetail, downloadUrl, previewUrl } from './useRuns';

/** Máximo de imágenes de la galería; el resto sigue en el navegador de artefactos. */
const GALLERY_LIMIT = 12;

function fileName(artifact: Artifact): string {
  return artifact.path.split('/').at(-1) ?? artifact.path;
}

function DownloadButtons({ runId, artifacts }: { runId: string; artifacts: Artifact[] }) {
  const { t } = useTranslation();
  return (
    <Group gap="xs">
      {artifacts.map((artifact) => (
        <Button
          key={artifact.id}
          component="a"
          href={downloadUrl(runId, artifact.id)}
          variant="light"
          size="xs"
          aria-label={t('runs.outputs.downloadLabel', { name: fileName(artifact) })}
        >
          {t(`runs.kinds.${artifact.kind}`)} · {fileName(artifact)} ({formatBytes(artifact.size_bytes)})
        </Button>
      ))}
    </Group>
  );
}

/**
 * Resultados destacados de la documentación y los grafos (Fase 5).
 *
 * El sitio HTML de util_bbdd necesita sus scripts (navegación y resaltado SQL): el iframe permite scripts pero **no**
 * `allow-same-origin`, así que su origen es opaco y no puede leer la SPA, la cookie ni llamar a la API. Se carga desde
 * una URL firmada y temporal (`site_url`, ADR-007) porque ese origen no envía la cookie de sesión.
 */
export function RunOutputs({ run }: { run: RunDetail }) {
  const { t } = useTranslation();
  const documents = run.artifacts.filter((a) => a.kind === 'word' || a.kind === 'excel');
  const graphs = run.artifacts.filter((a) => a.kind === 'graphs' && /\.(svg|png)$/i.test(a.path));

  if (
    !run.site_url &&
    documents.length === 0 &&
    (run.operation !== 'relationship_graph' || graphs.length === 0)
  ) {
    return null;
  }
  return (
    <Stack>
      {(run.site_url || documents.length > 0) && (
        <Card withBorder>
          <Stack>
            <Group justify="space-between">
              <Title order={3}>{t('runs.outputs.documentation')}</Title>
              {run.site_url && (
                <Button component="a" href={run.site_url} target="_blank" rel="noopener noreferrer" size="xs">
                  {t('runs.outputs.openSite')}
                </Button>
              )}
            </Group>
            {documents.length > 0 && <DownloadButtons runId={run.id} artifacts={documents} />}
            {run.site_url && (
              <iframe
                title={t('runs.outputs.siteTitle')}
                src={run.site_url}
                sandbox="allow-scripts allow-popups allow-downloads"
                referrerPolicy="no-referrer"
                style={{
                  width: '100%',
                  height: 640,
                  border: '1px solid var(--mantine-color-default-border)',
                }}
              />
            )}
          </Stack>
        </Card>
      )}
      {run.operation === 'relationship_graph' && graphs.length > 0 && (
        <Card withBorder>
          <Stack>
            <Title order={3}>{t('runs.outputs.graphs', { count: graphs.length })}</Title>
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
              {graphs.slice(0, GALLERY_LIMIT).map((artifact) => (
                <Stack key={artifact.id} gap={4}>
                  <Anchor href={downloadUrl(run.id, artifact.id)} size="sm">
                    {fileName(artifact)}
                  </Anchor>
                  <Image
                    src={previewUrl(run.id, artifact.id)}
                    alt={t('runs.outputs.graphAlt', { name: fileName(artifact) })}
                    fit="contain"
                    h={240}
                    bd="1px solid var(--mantine-color-default-border)"
                  />
                </Stack>
              ))}
            </SimpleGrid>
            {graphs.length > GALLERY_LIMIT && (
              <Text size="sm" c="dimmed">
                {t('runs.outputs.moreGraphs', { count: graphs.length - GALLERY_LIMIT })}
              </Text>
            )}
          </Stack>
        </Card>
      )}
    </Stack>
  );
}
