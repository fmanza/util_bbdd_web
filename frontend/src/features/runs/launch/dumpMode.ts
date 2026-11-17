export type DumpMode = 'all' | 'list' | 'patterns';

export const DUMP_MODES: readonly DumpMode[] = ['all', 'list', 'patterns'];

/** Qué campos del filtro del volcado ve cada modo (el backend rechaza la lista exacta junto con los patrones). */
export const DUMP_MODE_PARAMS: Readonly<Record<DumpMode, readonly string[]>> = {
  all: [],
  list: ['tables'],
  patterns: ['table_include', 'table_exclude'],
};

/** Modo inicial: el que corresponde a los valores (todas, si están vacíos). */
export function dumpModeOf(values: Record<string, unknown>): DumpMode {
  const filled = (name: string) => {
    const value = values[name];
    return typeof value === 'string' && value.trim() !== '';
  };
  if (filled('tables')) return 'list';
  if (filled('table_include') || filled('table_exclude')) return 'patterns';
  return 'all';
}
