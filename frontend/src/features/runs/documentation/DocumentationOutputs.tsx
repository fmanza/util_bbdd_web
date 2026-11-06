import { Alert, Badge, Button, Card, Group, List, Stack, Text, Title } from '@mantine/core';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { ErrorAlert } from '../../../components/ErrorAlert';
import { formatBytes } from '../../../components/format';
import { MarkdownPreview } from '../ArtifactBrowser';
import {
  type Artifact,
  type DocumentationFormat,
  MARKDOWN_DOC_ROOT,
  type RunDetail,
  archiveUrl,
  downloadUrl,
  isActive,
  useArtifactText,
} from '../useRuns';

/** Orden de las tarjetas y valor por defecto de cada casilla del formulario (`DocumentationParams`). */
const FORMATS: readonly { format: DocumentationFormat; byDefault: boolean }[] = [
  { format: 'word', byDefault: true },
  { format: 'excel', byDefault: true },
  { format: 'html', byDefault: true },
  { format: 'markdown', byDefault: false },
];
const MARKDOWN_INDEX = `${MARKDOWN_DOC_ROOT}docs/index.md`;

function fileName(artifact: Artifact): string {
  return artifact.path.split('/').at(-1) ?? artifact.path;
}

/** Formatos de la tarjeta: los pedidos (`params`) y, en ejecuciones antiguas o fallidas, los que dejaron ficheros. */
function documentationFormats(run: RunDetail): DocumentationFormat[] {
  return FORMATS.filter(({ format, byDefault }) => {
    const requested = (run.params[format] as boolean | undefined) ?? byDefault;
    const produced = run.artifacts.some((a) => a.kind === format);
    // Una ejecución que no terminó bien solo enseña lo que llegó a generar.
    return produced || (requested && run.status === 'succeeded');
  }).map(({ format }) => format);
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
          {fileName(artifact)} ({formatBytes(artifact.size_bytes)})
        </Button>
      ))}
    </Group>
  );
}

interface FormatCardProps {
  run: RunDetail;
  format: DocumentationFormat;
  files: Artifact[];
  actions?: ReactNode;
  children?: ReactNode;
}

/** Estructura común de las tarjetas: título, descripción, recuento, plantilla, avisos, ZIP y contenido propio. */
function FormatCard({ run, format, files, actions, children }: FormatCardProps) {
  const { t } = useTranslation();
  const warnings = run.warnings_by_format?.[format] ?? [];
  const template = run.templates_applied?.[format];
  const size = files.reduce((total, a) => total + a.size_bytes, 0);
  const titleId = `run-output-${format}`;
  return (
    <Card withBorder component="section" aria-labelledby={titleId}>
      <Stack gap="sm">
        <Group justify="space-between" wrap="wrap">
          <Group gap="xs">
            <Title order={3} id={titleId}>
              {t(`runs.outputs.formats.${format}.title`)}
            </Title>
            {template === true && <Badge variant="light">{t('runs.outputs.withTemplate')}</Badge>}
          </Group>
          <Group gap="xs">
            {actions}
            {files.length > 0 && (
              <Button
                component="a"
                href={archiveUrl(run.id, format)}
                size="xs"
                variant="default"
                aria-label={t('runs.outputs.zipLabel', { format: t(`runs.outputs.formats.${format}.title`) })}
              >
                {t('runs.outputs.zip')}
              </Button>
            )}
          </Group>
        </Group>
        <Text size="sm">{t(`runs.outputs.formats.${format}.description`)}</Text>
        <Text size="xs" c="dimmed">
          {files.length > 0
            ? t('runs.outputs.filesSummary', { count: files.length, size: formatBytes(size) })
            : t('runs.outputs.noFiles')}
        </Text>
        {warnings.length > 0 && (
          <Alert color="yellow" title={t('runs.outputs.formatWarnings')}>
            <List size="sm">
              {warnings.map((warning) => (
                <List.Item key={warning}>{warning}</List.Item>
              ))}
            </List>
          </Alert>
        )}
        {children}
      </Stack>
    </Card>
  );
}

function HtmlCard({ run, files }: { run: RunDetail; files: Artifact[] }) {
  const { t } = useTranslation();
  // El sitio de util_bbdd necesita sus scripts (navegación y resaltado SQL): el iframe permite scripts pero **no**
  // `allow-same-origin`, así que su origen es opaco y no puede leer la SPA, la cookie ni llamar a la API. Se carga desde
  // una URL firmada y temporal (`site_url`, ADR-007) porque ese origen no envía la cookie de sesión.
  return (
    <FormatCard
      run={run}
      format="html"
      files={files}
      actions={
        run.site_url && (
          <Button component="a" href={run.site_url} target="_blank" rel="noopener noreferrer" size="xs">
            {t('runs.outputs.openSite')}
          </Button>
        )
      }
    >
      {run.site_url && (
        <iframe
          title={t('runs.outputs.siteTitle')}
          src={run.site_url}
          sandbox="allow-scripts allow-popups allow-downloads"
          referrerPolicy="no-referrer"
          style={{ width: '100%', height: 640, border: '1px solid var(--mantine-color-default-border)' }}
        />
      )}
    </FormatCard>
  );
}

function MarkdownIndex({ run, index }: { run: RunDetail; index: Artifact }) {
  const { t } = useTranslation();
  const text = useArtifactText(run.id, index);
  if (text.isPending) return <Text size="sm">{t('common.loading')}</Text>;
  if (text.isError) return <ErrorAlert error={text.error} />;
  return <MarkdownPreview title={t('runs.outputs.markdownPage', { path: 'index.md' })} source={text.data} />;
}

function MarkdownCard({ run, files }: { run: RunDetail; files: Artifact[] }) {
  const { t } = useTranslation();
  const pages = files.filter((a) => a.previewable && a.path.startsWith(MARKDOWN_DOC_ROOT));
  // Ficheros auxiliares (catálogo, ficheros para IA, configuración del sitio): solo descarga.
  const auxiliary = files.filter((a) => !a.previewable && !a.path.includes('/assets/'));
  const index = pages.find((a) => a.path === MARKDOWN_INDEX);
  return (
    <FormatCard run={run} format="markdown" files={files}>
      {pages.length > 0 && (
        <Text size="xs" c="dimmed">
          {t('runs.outputs.markdownPages', { count: pages.length })}
        </Text>
      )}
      {auxiliary.length > 0 && (
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            {t('runs.outputs.auxiliaryFiles')}
          </Text>
          <DownloadButtons runId={run.id} artifacts={auxiliary} />
        </Stack>
      )}
      {index && <MarkdownIndex run={run} index={index} />}
    </FormatCard>
  );
}

/**
 * Resultados de una documentación: una tarjeta por formato pedido (Word, Excel, HTML y Markdown), cada una con su
 * descripción, sus ficheros, sus avisos y su ZIP (`GET /runs/{id}/archive?format=`).
 */
export function DocumentationOutputs({ run }: { run: RunDetail }) {
  if (isActive(run.status)) return null;
  const formats = documentationFormats(run);
  if (formats.length === 0) return null;
  const files = (format: DocumentationFormat) => run.artifacts.filter((a) => a.kind === format);
  return (
    <Stack>
      {formats.map((format) => {
        if (format === 'html') return <HtmlCard key={format} run={run} files={files(format)} />;
        if (format === 'markdown') return <MarkdownCard key={format} run={run} files={files(format)} />;
        return (
          <FormatCard key={format} run={run} format={format} files={files(format)}>
            {files(format).length > 0 && <DownloadButtons runId={run.id} artifacts={files(format)} />}
          </FormatCard>
        );
      })}
    </Stack>
  );
}
