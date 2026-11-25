import { vi } from 'vitest';

export interface StubResponse {
  status?: number;
  body?: unknown;
  /** Respuesta de texto plano (vistas previas) en lugar de JSON. */
  text?: string;
}

type Handler = StubResponse | ((request: Request) => StubResponse | Promise<StubResponse>);

/** Catálogo de permisos (ADR-014), en el orden de la API. */
export const ALL_PERMISSIONS = [
  'users.manage',
  'roles.manage',
  'sessions.manage',
  'audit.read',
  'templates.manage',
  'queries.manage',
  'allowlist.manage',
  'storage.manage',
  'runs.admin',
  'connections.share',
  'sql.run',
  'ddl.apply',
  'data.write',
] as const;
export type TestPermission = (typeof ALL_PERMISSIONS)[number];
export const PERMISSION_CATALOG = ALL_PERMISSIONS.map((name) => ({
  name,
  group: ['connections.share', 'sql.run', 'ddl.apply', 'data.write'].includes(name) ? 'databases' : 'admin',
}));
export const ADMIN_ROLE = { id: 1, name: 'Administrador', builtin: 'admin' } as const;
export const USER_ROLE = { id: 2, name: 'Usuario', builtin: 'user' } as const;

export const ADMIN = {
  id: 1,
  username: 'admin',
  display_name: 'Admin',
  role: ADMIN_ROLE,
  permissions: [...ALL_PERMISSIONS] as TestPermission[],
  color_scheme: 'auto',
  language: 'es',
} as const;
export const USER = {
  id: 2,
  username: 'ana',
  display_name: 'Ana',
  role: USER_ROLE,
  permissions: [] as TestPermission[],
  color_scheme: 'auto',
  language: 'es',
} as const;

/** `me` sin algunos permisos (p. ej. un admin de pruebas sin «Escribir datos»). */
export function without<T extends { permissions: readonly TestPermission[] }>(
  me: T,
  ...removed: TestPermission[]
): T {
  return { ...me, permissions: me.permissions.filter((p) => !removed.includes(p)) };
}

/**
 * Sustituye `fetch` por un enrutador `"MÉTODO /ruta" → respuesta`. Las rutas sin handler responden 404 con
 * *problem details*. Devuelve el mock para inspeccionar las peticiones.
 */
export function stubApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (request: Request) => {
    const key = `${request.method} ${new URL(request.url).pathname}`;
    const handler = routes[key];
    const {
      status = 200,
      body,
      text,
    } = handler
      ? typeof handler === 'function'
        ? await handler(request)
        : handler
      : { status: 404, body: { title: 'Not Found', status: 404 } };
    if (status === 204) {
      return new Response(null, { status });
    }
    if (text !== undefined) {
      return new Response(text, { status, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
    }
    return new Response(JSON.stringify(body ?? {}), {
      status,
      headers: { 'Content-Type': status < 400 ? 'application/json' : 'application/problem+json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

export const HEALTH = {
  'GET /api/health': {
    body: { status: 'ok', version: '1.0.0', util_bbdd_version: '4.0.0', database: 'ok' },
  },
};

/** Rutas base con sesión iniciada como `me` (o sin sesión con `null`). */
export function session(me: object | null): Record<string, Handler> {
  return {
    ...HEALTH,
    'GET /api/v1/auth/me': me
      ? { body: me }
      : { status: 401, body: { title: 'No autenticado', status: 401 } },
  };
}

/** Peticiones hechas a `METHOD /ruta`. */
export function callsTo(fetchMock: ReturnType<typeof stubApi>, method: string, path: string): Request[] {
  return fetchMock.mock.calls
    .map(([request]) => request)
    .filter((request) => request.method === method && new URL(request.url).pathname === path);
}
