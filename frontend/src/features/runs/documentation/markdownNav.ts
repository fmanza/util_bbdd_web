// Navegación del visor Markdown (M2): árbol de páginas y resolución de los enlaces que pulsa el usuario dentro del
// iframe aislado. Funciones puras: el texto de los enlaces viene de la BD documentada (comentarios, mapa de
// trazabilidad), así que nunca se usa para construir una URL de la API sin pasar por `resolveLink`, que solo devuelve
// artefactos registrados de la documentación (AUDIT_PLAN T6).

import { type Artifact, MARKDOWN_DOC_ROOT } from '../useRuns';

/** Raíz de las páginas: las rutas del visor (y de `?md=`) son relativas a esta carpeta. */
export const DOCS_ROOT = `${MARKDOWN_DOC_ROOT}docs/`;
/** Longitud máxima de un enlace que se acepta del iframe. */
export const MAX_HREF = 2048;

/**
 * Secciones del árbol, en orden. Dependen de la estructura de carpetas de util_bbdd 5.3.0 (`docs/tables/…`); el test de
 * contrato del backend (`test_documentation_archive_by_format_preview_rules_and_page_layout`) avisa si cambia (G51).
 */
export const SECTIONS = ['root', 'tables', 'views', 'routines', 'database', 'other'] as const;
export type Section = (typeof SECTIONS)[number];

export interface Page {
  /** Ruta relativa a `docs/` (`tables/pedidos.md`). */
  path: string;
  section: Section;
  /** Nombre sin `.md` (`pedidos`, `index-a`). */
  stem: string;
  /** `index` (índice de la sección), `letter` (`index-<letra>`) u `object` (una página por objeto). */
  role: 'index' | 'letter' | 'object';
  artifact: Artifact;
}

const KNOWN: ReadonlySet<string> = new Set(['tables', 'views', 'routines', 'database']);
/** Páginas de la raíz que van primero, en este orden; el resto de la raíz, después por nombre. */
const ROOT_ORDER = ['index.md', 'traceability.md', 'changes.md'];

function roleOf(stem: string): Page['role'] {
  if (stem === 'index') return 'index';
  return /^index-[^/]+$/.test(stem) ? 'letter' : 'object';
}

function rootRank(path: string): number {
  const rank = ROOT_ORDER.indexOf(path);
  return rank === -1 ? ROOT_ORDER.length : rank;
}

const ROLE_RANK: Record<Page['role'], number> = { index: 0, letter: 1, object: 2 };

/** Páginas `.md` con vista previa de la documentación, ordenadas por sección, tipo y nombre. */
export function buildPages(artifacts: readonly Artifact[]): Page[] {
  const pages: Page[] = [];
  for (const artifact of artifacts) {
    if (!artifact.previewable || !artifact.path.startsWith(DOCS_ROOT) || !artifact.path.endsWith('.md')) {
      continue;
    }
    const path = artifact.path.slice(DOCS_ROOT.length);
    const parts = path.split('/');
    const folder = parts.length === 1 ? 'root' : (parts[0] ?? '');
    const section: Section = folder === 'root' ? 'root' : KNOWN.has(folder) ? (folder as Section) : 'other';
    const stem = (parts.at(-1) ?? path).replace(/\.md$/, '');
    pages.push({ path, section, stem, role: section === 'root' ? 'object' : roleOf(stem), artifact });
  }
  return pages.sort(
    (a, b) =>
      SECTIONS.indexOf(a.section) - SECTIONS.indexOf(b.section) ||
      (a.section === 'root' ? rootRank(a.path) - rootRank(b.path) : ROLE_RANK[a.role] - ROLE_RANK[b.role]) ||
      a.path.localeCompare(b.path),
  );
}

/** Letra inicial (mayúscula) de una página de objeto; `#` si no empieza por una letra o un número. */
export function initialOf(page: Page): string {
  const first = page.stem.charAt(0).toUpperCase();
  return /[\p{L}\p{N}]/u.test(first) ? first : '#';
}

export type LinkTarget =
  | { type: 'page'; path: string; hash: string }
  | { type: 'download'; artifact: Artifact }
  | { type: 'external'; url: string }
  | { type: 'missing'; href: string }
  | { type: 'ignored' };

const SCHEME = /^[a-z][a-z0-9+.-]*:/i;

/** Normaliza `segments` (sin `.` ni `..`); `null` si sale de la raíz. */
function normalize(segments: readonly string[]): string[] | null {
  const out: string[] = [];
  for (const segment of segments) {
    if (segment === '' || segment === '.') continue;
    if (segment === '..') {
      if (out.length === 0) return null;
      out.pop();
      continue;
    }
    out.push(segment);
  }
  return out;
}

function decode(text: string): string | null {
  try {
    return decodeURIComponent(text);
  } catch {
    return null;
  }
}

/**
 * Destino de un enlace pulsado en la página `current` (ruta relativa a `docs/`).
 *
 * - `http:`/`https:` absolutos: `external` (el visor pide confirmación antes de abrirlos, D4).
 * - Otros esquemas (`javascript:`, `data:`, `file:`…), rutas absolutas y protocol-relative (`//host`): `ignored`.
 * - Relativos: se resuelven contra la carpeta de `current`, sin salir de `docs/`, y solo se aceptan artefactos
 *   registrados: una página `.md` con vista previa es `page`; cualquier otro fichero, `download`; si no, `missing`.
 */
export function resolveLink(current: string, href: string, artifacts: readonly Artifact[]): LinkTarget {
  const text = href.trim();
  if (text === '' || text.length > MAX_HREF) return { type: 'ignored' };
  if (SCHEME.test(text)) {
    try {
      const url = new URL(text);
      return url.protocol === 'http:' || url.protocol === 'https:'
        ? { type: 'external', url: url.href }
        : { type: 'ignored' };
    } catch {
      return { type: 'ignored' };
    }
  }
  if (text.startsWith('/') || text.startsWith('\\')) return { type: 'ignored' };

  const hashAt = text.indexOf('#');
  const beforeHash = hashAt === -1 ? text : text.slice(0, hashAt);
  const rawHash = hashAt === -1 ? '' : text.slice(hashAt + 1);
  const rawPath = beforeHash.split('?')[0] ?? '';
  const path = decode(rawPath);
  const hash = decode(rawHash);
  if (path === null || hash === null || path.includes('\\') || path.includes('\0')) {
    return { type: 'missing', href: text };
  }
  if (path === '') return { type: 'page', path: current, hash };

  const base = current.split('/').slice(0, -1);
  const segments = normalize([...base, ...path.split('/')]);
  if (segments === null || segments.length === 0) return { type: 'missing', href: text };
  const target = DOCS_ROOT + segments.join('/');
  const artifact = artifacts.find((a) => a.path === target);
  if (!artifact) return { type: 'missing', href: text };
  if (artifact.previewable && target.endsWith('.md')) {
    return { type: 'page', path: target.slice(DOCS_ROOT.length), hash };
  }
  return { type: 'download', artifact };
}

/** `?md=` → página y ancla (`tables/pedidos.md#col-id`). */
export function parseLocation(value: string | null): { path: string; hash: string } | null {
  if (!value) return null;
  const at = value.indexOf('#');
  return at === -1 ? { path: value, hash: '' } : { path: value.slice(0, at), hash: value.slice(at + 1) };
}

export function formatLocation(path: string, hash: string): string {
  return hash ? `${path}#${hash}` : path;
}
