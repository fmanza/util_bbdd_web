import type { FieldError, FieldErrors, FieldValues, Resolver } from 'react-hook-form';
import type { z } from 'zod';

function setPath(target: Record<string, unknown>, path: PropertyKey[], value: FieldError) {
  let node = target;
  path.forEach((key, index) => {
    const name = String(key);
    if (index === path.length - 1) {
      node[name] ??= value;
      return;
    }
    node[name] ??= {};
    node = node[name] as Record<string, unknown>;
  });
}

/**
 * *Resolver* de React Hook Form para un esquema de Zod. Sustituye a `@hookform/resolvers` (dependencia no
 * aprobada): solo el primer error de cada campo, con la ruta anidada (`params.host`).
 */
export function zodResolver<TIn extends FieldValues, TOut extends FieldValues = TIn>(
  schema: z.ZodType<TOut, TIn>,
): Resolver<TIn, unknown, TOut> {
  return async (values) => {
    const result = await schema.safeParseAsync(values);
    if (result.success) {
      return { values: result.data, errors: {} };
    }
    const errors: Record<string, unknown> = {};
    for (const issue of result.error.issues) {
      setPath(errors, issue.path.length ? issue.path : ['root'], {
        type: issue.code,
        message: issue.message,
      });
    }
    return { values: {}, errors: errors as FieldErrors<TIn> };
  };
}
