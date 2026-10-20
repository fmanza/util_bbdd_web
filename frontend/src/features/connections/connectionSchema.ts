import type { TFunction } from 'i18next';
import { z } from 'zod';

import type { EngineDetail, EngineParam } from '../engines/useEngines';

/** Valores del formulario: los parámetros se editan como texto y Zod los convierte al tipo del catálogo. */
export interface ConnectionFormValues {
  name: string;
  description: string;
  password: string;
  read_only: boolean;
  visibility: 'private' | 'shared';
  params: Record<string, string>;
}

export interface ConnectionFormOutput {
  name: string;
  description: string;
  password: string | undefined;
  read_only: boolean;
  visibility: 'private' | 'shared';
  params: Record<string, unknown>;
}

/** Parámetros que se editan en el formulario (los secretos van en `password`; los bloqueados no se ofrecen). */
export function editableParams(engine: EngineDetail): EngineParam[] {
  return engine.params.filter((param) => param.kind !== 'secret' && param.kind !== 'blocked');
}

// Se muestran siempre; el resto va en «Opciones avanzadas».
const PRIMARY = new Set([
  'host',
  'port',
  'database',
  'service_name',
  'sid',
  'dsn',
  'user',
  'schema',
  'jdbc_url',
  'jdbc_jar',
  'sslmode',
]);

export function isPrimary(param: EngineParam): boolean {
  return param.required || PRIMARY.has(param.name);
}

/** Valor inicial (texto) de un parámetro: el guardado o vacío. Los valores por defecto se muestran como ayuda. */
export function toFormValue(param: EngineParam, value: unknown): string {
  if (value === undefined || value === null) return '';
  if (param.type === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function paramSchema(param: EngineParam, t: TFunction) {
  const label = param.name;
  return z.string().transform((raw, ctx): unknown => {
    const value = raw.trim();
    if (value === '') {
      if (param.required) {
        ctx.addIssue({ code: 'custom', message: t('connections.form.required', { name: label }) });
        return z.NEVER;
      }
      return undefined;
    }
    switch (param.type) {
      case 'integer':
        if (!/^-?\d+$/.test(value)) {
          ctx.addIssue({ code: 'custom', message: t('connections.form.integer') });
          return z.NEVER;
        }
        return Number(value);
      case 'float':
        if (Number.isNaN(Number(value))) {
          ctx.addIssue({ code: 'custom', message: t('connections.form.number') });
          return z.NEVER;
        }
        return Number(value);
      case 'boolean':
        return value === 'true';
      case 'object':
        try {
          const parsed: unknown = JSON.parse(value);
          if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed))
            throw new Error('no es objeto');
          return parsed;
        } catch {
          ctx.addIssue({ code: 'custom', message: t('connections.form.json') });
          return z.NEVER;
        }
      default:
        if (param.options && !param.options.includes(value)) {
          ctx.addIssue({ code: 'custom', message: t('connections.form.option') });
          return z.NEVER;
        }
        return value;
    }
  });
}

/**
 * Esquema Zod generado desde los `connection_params` del motor (catálogo de util_bbdd).
 *
 * @param hasStoredPassword En edición, si ya hay contraseña guardada (dejarla vacía la conserva).
 */
export function buildConnectionSchema(
  engine: EngineDetail,
  t: TFunction,
  { hasStoredPassword }: { hasStoredPassword: boolean },
): z.ZodType<ConnectionFormOutput, ConnectionFormValues> {
  const passwordRequired = engine.params.some((p) => p.kind === 'secret' && p.required) && !hasStoredPassword;
  const shape: Record<string, ReturnType<typeof paramSchema>> = {};
  for (const param of editableParams(engine)) {
    shape[param.name] = paramSchema(param, t);
  }
  return z.object({
    name: z
      .string()
      .trim()
      .min(1, t('connections.form.nameRequired'))
      .max(100, t('connections.form.tooLong', { max: 100 })),
    description: z
      .string()
      .trim()
      .max(500, t('connections.form.tooLong', { max: 500 })),
    password: z
      .string()
      .max(512, t('connections.form.tooLong', { max: 512 }))
      .refine((value) => !passwordRequired || value.length > 0, t('connections.form.passwordRequired'))
      .transform((value) => (value === '' ? undefined : value)),
    read_only: z.boolean(),
    visibility: z.enum(['private', 'shared']),
    params: z
      .object(shape)
      .transform((params) =>
        Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined)),
      ),
  });
}
