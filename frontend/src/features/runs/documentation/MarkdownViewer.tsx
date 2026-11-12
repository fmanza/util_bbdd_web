import {
  ActionIcon,
  Alert,
  Anchor,
  Box,
  Button,
  Code,
  Grid,
  Group,
  Loader,
  Modal,
  NativeSelect,
  NavLink,
  ScrollArea,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import type { TFunction } from 'i18next';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { ErrorAlert } from '../../../components/ErrorAlert';
import { stripFrontMatter } from '../markdown';
import { renderMermaidBlocks } from '../mermaid';
import { type Artifact, downloadUrl, useArtifactText } from '../useRuns';
import { buildFrameDocument, navHref, sanitizeMarkdownHtml } from './markdownFrame';
import {
  type Page,
  SECTIONS,
  type Section,
  formatLocation,
  initialOf,
  objectName,
  parseLocation,
  resolveLink,
} from './markdownNav';

/** Parámetro de la URL con la página abierta (`?md=tables/pedidos.md#col-id`): enlace compartible. */
const PARAM = 'md';
/** Con más páginas de objeto que esto, la sección se pagina por letra (sin virtualización ni dependencias nuevas). */
const LETTER_THRESHOLD = 40;
const MAX_RESULTS = 100;
/** Alto del iframe y del árbol (1.15.0): casi toda la ventana, nunca menos de 640 px. */
const FRAME_HEIGHT = 'max(640px, calc(100vh - 220px))';
const TREE_HEIGHT = 'max(520px, calc(100vh - 340px))';

type Notice = { kind: 'missing'; href: string } | { kind: 'download'; artifact: Artifact } | null;

interface FrameProps {
  runId: string;
  page: Page;
  hash: string;
  onLink: (href: string) => void;
}

/** Página en el iframe aislado (`sandbox="allow-scripts"`, origen opaco, puente por hash; ver `markdownFrame.ts`). */
function MarkdownFrame({ runId, page, hash, onLink }: FrameProps) {
  const { t } = useTranslation();
  const text = useArtifactText(runId, page.artifact);
  const frame = useRef<HTMLIFrameElement>(null);
  const [safeHtml, setSafeHtml] = useState<{ source: string; html: string } | null>(null);

  useEffect(() => {
    const source = text.data;
    if (source === undefined) return undefined;
    let alive = true;
    void import('marked').then(async ({ marked }) => {
      const html = await renderMermaidBlocks(await marked.parse(stripFrontMatter(source), { gfm: true }));
      if (alive) setSafeHtml({ source, html: sanitizeMarkdownHtml(html) });
    });
    return () => {
      alive = false;
    };
  }, [text.data]);

  useEffect(() => {
    const listener = (event: MessageEvent) => {
      // Origen opaco: `event.origin` es "null"; lo que identifica al iframe es su ventana (AUDIT_PLAN T5).
      if (!frame.current || event.source !== frame.current.contentWindow) return;
      const href = navHref(event.data);
      if (href !== null) onLink(href);
    };
    window.addEventListener('message', listener);
    return () => window.removeEventListener('message', listener);
  }, [onLink]);

  const ready = safeHtml !== null && safeHtml.source === text.data;
  const srcDoc = useMemo(
    () => (ready ? buildFrameDocument(safeHtml.html, hash, window.location.origin) : null),
    [ready, safeHtml, hash],
  );

  if (text.isError) return <ErrorAlert error={text.error} />;
  if (srcDoc === null) return <Loader size="sm" aria-label={t('common.loading')} />;
  return (
    <iframe
      ref={frame}
      title={t('runs.outputs.markdownPage', { path: page.path })}
      sandbox="allow-scripts"
      referrerPolicy="no-referrer"
      srcDoc={srcDoc}
      style={{ width: '100%', height: FRAME_HEIGHT, border: '1px solid var(--mantine-color-default-border)' }}
    />
  );
}

function pageLabel(page: Page, t: TFunction): string {
  if (page.title) return objectName(page);
  if (page.role === 'index') return t('runs.markdownViewer.sectionIndex');
  if (page.role === 'letter')
    return t('runs.markdownViewer.letterIndex', { letter: page.stem.slice(6).toUpperCase() });
  return page.stem;
}

interface TreeProps {
  pages: Page[];
  current: Page;
  onOpen: (page: Page) => void;
}

/** Árbol: buscador por nombre, sección y, en las secciones grandes, letra inicial. */
function PageTree({ pages, current, onOpen }: TreeProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [section, setSection] = useState<Section>(current.section);
  const [letter, setLetter] = useState<string | null>(null);
  // Al llegar a otra página (enlace, atrás/adelante), el árbol se coloca en su sección y su letra.
  const [shown, setShown] = useState(current.path);
  if (shown !== current.path) {
    setShown(current.path);
    setSection(current.section);
    setLetter(current.role === 'object' ? initialOf(current) : null);
  }
  const sections = SECTIONS.filter((s) => pages.some((p) => p.section === s));
  const inSection = pages.filter((p) => p.section === section);
  const objects = inSection.filter((p) => p.role === 'object');
  const letters = [...new Set(objects.map(initialOf))].sort((a, b) => a.localeCompare(b));
  const paged = section !== 'root' && objects.length > LETTER_THRESHOLD;
  const activeLetter = paged
    ? letter !== null && letters.includes(letter)
      ? letter
      : (letters[0] ?? null)
    : null;

  const needle = query.trim().toLowerCase();
  const results = needle
    ? pages.filter(
        (p) => p.path.toLowerCase().includes(needle) || (p.title ?? '').toLowerCase().includes(needle),
      )
    : [];
  const listed = needle
    ? results.slice(0, MAX_RESULTS)
    : [
        ...inSection.filter((p) => p.role === 'index'),
        ...objects.filter((p) => activeLetter === null || initialOf(p) === activeLetter),
      ];

  return (
    <Stack gap="xs" component="nav" aria-label={t('runs.markdownViewer.tree')}>
      <TextInput
        label={t('runs.markdownViewer.search')}
        placeholder={t('runs.markdownViewer.searchPlaceholder')}
        value={query}
        onChange={(event) => setQuery(event.currentTarget.value)}
      />
      {!needle && (
        <NativeSelect
          label={t('runs.markdownViewer.section')}
          value={section}
          onChange={(event) => {
            setSection(event.currentTarget.value as Section);
            setLetter(null);
          }}
          data={sections.map((s) => ({
            value: s,
            label: `${t(`runs.markdownViewer.sections.${s}`)} (${pages.filter((p) => p.section === s).length})`,
          }))}
        />
      )}
      {!needle && paged && (
        <Group gap={4} role="group" aria-label={t('runs.markdownViewer.letters')}>
          {letters.map((l) => (
            <Button
              key={l}
              size="compact-xs"
              variant={l === activeLetter ? 'filled' : 'default'}
              aria-pressed={l === activeLetter}
              onClick={() => setLetter(l)}
            >
              {l}
            </Button>
          ))}
        </Group>
      )}
      {needle && (
        <Text size="xs" c="dimmed" aria-live="polite">
          {results.length > MAX_RESULTS
            ? t('runs.markdownViewer.resultsCapped', { shown: MAX_RESULTS, count: results.length })
            : t('runs.markdownViewer.results', { count: results.length })}
        </Text>
      )}
      <ScrollArea h={TREE_HEIGHT} type="auto">
        <Box role="list" aria-label={t('runs.markdownViewer.pages')}>
          {listed.map((page) => (
            <div role="listitem" key={page.path}>
              <NavLink
                component="button"
                label={pageLabel(page, t)}
                description={needle ? page.path : undefined}
                active={page.path === current.path}
                aria-current={page.path === current.path ? 'page' : undefined}
                onClick={() => onOpen(page)}
              />
            </div>
          ))}
        </Box>
      </ScrollArea>
    </Stack>
  );
}

/**
 * Visor de la documentación Markdown (M2): árbol con buscador y paginación por letra, página en un iframe aislado con
 * puente de navegación (enlaces entre páginas y anclas), historial propio, URL compartible (`?md=`) y enlaces externos
 * con confirmación (D4).
 */
export function MarkdownViewer({
  runId,
  artifacts,
  pages,
}: {
  runId: string;
  artifacts: Artifact[];
  pages: Page[];
}) {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const byPath = useMemo(() => new Map(pages.map((p) => [p.path, p])), [pages]);
  const fallback = byPath.get('index.md') ?? pages[0];
  const requested = parseLocation(searchParams.get(PARAM));
  const current = (requested && byPath.get(requested.path)) ?? fallback;
  const hash = requested && current && requested.path === current.path ? requested.hash : '';
  const here = current ? formatLocation(current.path, hash) : '';

  const [history, setHistory] = useState<{ stack: string[]; at: number }>({ stack: [here], at: 0 });
  const [notice, setNotice] = useState<Notice>(null);
  const [external, setExternal] = useState<string | null>(null);

  const show = useCallback(
    (location: string) => {
      setSearchParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          next.set(PARAM, location);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const open = useCallback(
    (path: string, anchor: string) => {
      const location = formatLocation(path, anchor);
      setNotice(null);
      setHistory(({ stack, at }) =>
        stack[at] === location ? { stack, at } : { stack: [...stack.slice(0, at + 1), location], at: at + 1 },
      );
      show(location);
    },
    [show],
  );

  const onLink = useCallback(
    (href: string) => {
      if (!current) return;
      const target = resolveLink(current.path, href, artifacts);
      if (target.type === 'page') open(target.path, target.hash);
      else if (target.type === 'external') setExternal(target.url);
      else if (target.type === 'download') setNotice({ kind: 'download', artifact: target.artifact });
      else if (target.type === 'missing') setNotice({ kind: 'missing', href: target.href });
    },
    [artifacts, current, open],
  );

  const move = (step: -1 | 1) => {
    const at = history.at + step;
    const location = history.stack[at];
    if (location === undefined) return;
    setNotice(null);
    setHistory({ stack: history.stack, at });
    show(location);
  };

  if (!current) return null;
  return (
    <>
      {/* El árbol, estrecho; la página, el resto del ancho (1.15.0: antes, un tercio y dos tercios). */}
      <Grid>
        <Grid.Col span={{ base: 12, md: 3, xl: 2 }}>
          <PageTree pages={pages} current={current} onOpen={(page) => open(page.path, '')} />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 9, xl: 10 }}>
          <Stack gap="xs">
            <Group justify="space-between" wrap="nowrap">
              <Group gap={4} wrap="nowrap">
                <ActionIcon
                  variant="default"
                  aria-label={t('runs.markdownViewer.back')}
                  disabled={history.at === 0}
                  onClick={() => move(-1)}
                >
                  ‹
                </ActionIcon>
                <ActionIcon
                  variant="default"
                  aria-label={t('runs.markdownViewer.forward')}
                  disabled={history.at >= history.stack.length - 1}
                  onClick={() => move(1)}
                >
                  ›
                </ActionIcon>
                <Code>{here}</Code>
              </Group>
              <Anchor
                href={downloadUrl(runId, current.artifact.id)}
                size="sm"
                aria-label={t('runs.markdownViewer.downloadPage', { path: current.path })}
              >
                {t('runs.markdownViewer.download')}
              </Anchor>
            </Group>
            {notice?.kind === 'missing' && (
              <Alert
                color="yellow"
                withCloseButton
                onClose={() => setNotice(null)}
                title={t('runs.markdownViewer.missing')}
              >
                <Code>{notice.href}</Code>
              </Alert>
            )}
            {notice?.kind === 'download' && (
              <Alert
                color="blue"
                withCloseButton
                onClose={() => setNotice(null)}
                title={t('runs.markdownViewer.notAPage')}
              >
                <Anchor href={downloadUrl(runId, notice.artifact.id)}>
                  {t('runs.outputs.downloadLabel', { name: notice.artifact.path.split('/').at(-1) })}
                </Anchor>
              </Alert>
            )}
            <MarkdownFrame runId={runId} page={current} hash={hash} onLink={onLink} />
          </Stack>
        </Grid.Col>
      </Grid>
      <Modal
        opened={external !== null}
        onClose={() => setExternal(null)}
        title={t('runs.markdownViewer.externalTitle')}
      >
        <Stack>
          <Text size="sm">{t('runs.markdownViewer.externalBody')}</Text>
          <Code block style={{ wordBreak: 'break-all' }}>
            {external}
          </Code>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setExternal(null)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={() => {
                if (external) window.open(external, '_blank', 'noopener,noreferrer');
                setExternal(null);
              }}
            >
              {t('runs.markdownViewer.externalOpen')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
