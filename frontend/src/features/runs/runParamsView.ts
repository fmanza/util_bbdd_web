import type { Operation, OperationParam } from './useRuns';
import { DUMP_MODE_PARAMS, dumpModeOf } from './launch/dumpMode';
import {
  DISABLED_WITHOUT,
  ENGINE_GROUPS,
  itemParams,
  type ResolvedCard,
  resolveCards,
  SHOWN_WHEN,
} from './launch/launchLayout';

/**
 * Configuración de una ejecución en el detalle (solo lectura): las mismas tarjetas que «Lanzar ejecución»
 * (`launchLayout`) con los valores guardados en `run.params`. Lógica pura, sin React.
 */

export interface ParamEntry {
  param: OperationParam;
  value: unknown;
  /** Distinto del valor por defecto actual del catálogo (sin catálogo, siempre `true`). */
  changed: boolean;
  /** Su interruptor principal está apagado: util_bbdd lo ignoró (`DISABLED_WITHOUT`). */
  inactive: boolean;
}

export interface ParamCard {
  id: string;
  /** Clave i18n del título. */
  title: string;
  span?: 1 | 'full' | undefined;
  cols: number;
  /** Interruptores, pintados como chips. */
  flags: ParamEntry[];
  /** El resto, como pares etiqueta → valor. */
  fields: ParamEntry[];
}

export interface ParamsView {
  cards: ParamCard[];
  /** Parámetros mostrados y cuántos difieren del valor por defecto. */
  total: number;
  changed: number;
}

const blank = (value: unknown) => value === null || value === undefined || value === '';

/** Igualdad de valores guardados: `null`, `undefined` y `''` cuentan como «sin valor»; números y textos se comparan por texto. */
export function sameValue(a: unknown, b: unknown): boolean {
  if (blank(a) || blank(b)) return blank(a) && blank(b);
  if (typeof a === 'object' || typeof b === 'object') return JSON.stringify(a) === JSON.stringify(b);
  return String(a) === String(b);
}

/** Parámetro sintético para una clave guardada que el catálogo no conoce (ejecución antigua o sin catálogo). */
function syntheticParam(name: string, value: unknown): OperationParam {
  const type: OperationParam['type'] =
    typeof value === 'boolean' ? 'boolean' : typeof value === 'number' ? 'float' : 'string';
  return { name, type, required: false, default: null, description: '', minimum: null, maximum: null };
}

/**
 * Tarjetas de solo lectura de una ejecución. Con `operation` usa el diseño del formulario y oculta lo que el
 * formulario no habría enviado (`requires` apagado, otro motor destino, otro modo de selección del volcado…); las
 * claves guardadas que el catálogo no tiene van a una tarjeta final. Sin catálogo (`undefined`), una sola tarjeta
 * con todas las claves.
 */
export function buildParamsView(
  operationName: string,
  operation: Operation | undefined,
  params: Readonly<Record<string, unknown>>,
  onlyChanged = false,
): ParamsView {
  const known = new Set(operation?.params.map((p) => p.name) ?? []);
  const unknown = Object.keys(params)
    .filter((name) => !known.has(name))
    .map((name) => syntheticParam(name, params[name]));
  const synthetic = new Set(unknown.map((p) => p.name));

  const shownWhen = SHOWN_WHEN[operationName] ?? {};
  const disabledWithout = DISABLED_WITHOUT[operationName] ?? {};
  const dumpMode = dumpModeOf(params);
  const dumpManaged = new Set(Object.values(DUMP_MODE_PARAMS).flat());
  const targetEngine = params['target_engine'];

  const visible = (param: OperationParam): boolean => {
    if (synthetic.has(param.name)) return true;
    if (!(param.name in params)) return false;
    if (param.requires && params[param.requires] !== true) return false;
    if (param.type === 'template' && !param.requires && param.template_kind) {
      if (params[param.template_kind] !== true) return false;
    }
    const condition = shownWhen[param.name];
    if (condition && params[condition.param] !== condition.value) return false;
    if (
      operationName === 'dump_preview' &&
      dumpManaged.has(param.name) &&
      !DUMP_MODE_PARAMS[dumpMode].includes(param.name)
    ) {
      return false;
    }
    return true;
  };
  const groupVisible = (group: string) =>
    !ENGINE_GROUPS[group] ||
    (typeof targetEngine === 'string' && ENGINE_GROUPS[group].includes(targetEngine));

  const entry = (param: OperationParam): ParamEntry => {
    const value = params[param.name];
    const master = disabledWithout[param.name];
    return {
      param,
      value,
      changed: synthetic.has(param.name) || !sameValue(value, param.default),
      inactive: master !== undefined && params[master] === false,
    };
  };

  const toCard = (card: ResolvedCard): ParamCard => {
    const entries = card.items
      .filter((item) => item.kind !== 'group' || groupVisible(item.group))
      .flatMap(itemParams)
      .filter(visible)
      .map(entry);
    return {
      id: card.id,
      title: card.title,
      span: card.span,
      cols: card.cols ?? 1,
      flags: entries.filter((e) => e.param.type === 'boolean'),
      fields: entries.filter((e) => e.param.type !== 'boolean'),
    };
  };

  const cards = operation ? resolveCards(operation).map(toCard) : [];
  if (unknown.length > 0) {
    const entries = unknown.map(entry);
    cards.push({
      id: 'saved',
      title: operation ? 'runs.detail.savedParams' : 'runs.cards.params',
      span: 'full',
      cols: 3,
      flags: entries.filter((e) => e.param.type === 'boolean'),
      fields: entries.filter((e) => e.param.type !== 'boolean'),
    });
  }

  const all = cards.flatMap((c) => [...c.flags, ...c.fields]);
  const keep = (e: ParamEntry) => !onlyChanged || e.changed;
  return {
    cards: cards
      .map((c) => ({ ...c, flags: c.flags.filter(keep), fields: c.fields.filter(keep) }))
      .filter((c) => c.flags.length + c.fields.length > 0),
    total: all.length,
    changed: all.filter((e) => e.changed).length,
  };
}
