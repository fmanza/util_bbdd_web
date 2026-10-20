import createClient, { type Middleware } from 'openapi-fetch';

import type { paths } from './schema';

export const CSRF_COOKIE = 'ubw_csrf';
export const CSRF_HEADER = 'X-CSRF-Token';
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

/** Valor de una cookie legible por JavaScript (solo `ubw_csrf`; la de sesión es `HttpOnly`). */
export function readCookie(name: string): string | undefined {
  const prefix = `${name}=`;
  const entry = document.cookie.split('; ').find((part) => part.startsWith(prefix));
  return entry === undefined ? undefined : decodeURIComponent(entry.slice(prefix.length));
}

// Doble envío CSRF (ADR-003): copia la cookie `ubw_csrf` en la cabecera de todo método no seguro, salvo que la
// llamada ya la traiga (el login la toma de `GET /auth/csrf`).
const csrfMiddleware: Middleware = {
  onRequest({ request }) {
    if (UNSAFE_METHODS.has(request.method) && !request.headers.has(CSRF_HEADER)) {
      const token = readCookie(CSRF_COOKIE);
      if (token) {
        request.headers.set(CSRF_HEADER, token);
      }
    }
    return request;
  },
};

// Cliente tipado generado desde openapi/openapi.json (npm run gen:api). Mismo origen: la cookie de sesión viaja
// sola y no hace falta CORS.
// `fetch` se resuelve en cada llamada (no al crear el cliente) para que los tests puedan sustituirlo.
export const api = createClient<paths>({
  baseUrl: globalThis.location.origin,
  credentials: 'same-origin',
  fetch: (request) => globalThis.fetch(request),
});
api.use(csrfMiddleware);

export interface ProblemFieldError {
  loc: (string | number)[];
  msg: string;
  type?: string;
}

export interface Problem {
  title: string;
  status: number;
  detail?: string;
  /** Errores por campo (422): `loc` como en FastAPI, p. ej. `["body", "params", "host"]`. */
  errors?: ProblemFieldError[];
}

export class ApiError extends Error {
  readonly problem: Problem;

  constructor(problem: Problem) {
    super(problem.detail ?? problem.title);
    this.name = 'ApiError';
    this.problem = problem;
  }

  get status(): number {
    return this.problem.status;
  }
}

/** Devuelve `data` o lanza `ApiError` con el *problem details* de la API (RFC 9457). */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) {
    return result.data;
  }
  const problem = (result.error as Problem | undefined) ?? {
    title: result.response.statusText || 'Error',
    status: result.response.status,
  };
  throw new ApiError(problem);
}

/** Como `unwrap`, para respuestas sin cuerpo (`204`). */
export function ensureOk(result: { error?: unknown; response: Response }): void {
  if (!result.response.ok) {
    unwrap(result);
  }
}

export function isApiError(error: unknown, status?: number): error is ApiError {
  return error instanceof ApiError && (status === undefined || error.status === status);
}
