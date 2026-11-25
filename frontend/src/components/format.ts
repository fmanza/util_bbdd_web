import { intlLocale } from '../i18n';

interface Formatters {
  dateTime: Intl.DateTimeFormat;
  decimal: Intl.NumberFormat;
}
const cache = new Map<string, Formatters>();

/** Formateadores del idioma activo de i18next (se crean una vez por locale). */
function formatters(): Formatters {
  const locale = intlLocale();
  let entry = cache.get(locale);
  if (!entry) {
    entry = {
      dateTime: new Intl.DateTimeFormat(locale, { dateStyle: 'short', timeStyle: 'medium' }),
      decimal: new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }),
    };
    cache.set(locale, entry);
  }
  return entry;
}

/** Fecha ISO 8601 de la API en hora local. */
export function formatDateTime(iso: string | null | undefined): string {
  return iso ? formatters().dateTime.format(new Date(iso)) : '—';
}

/** Duración en segundos como «1 h 2 min», «3 min 4 s» o «5,2 s». */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${formatters().decimal.format(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ${Math.round(seconds % 60)} s`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

/** Tamaño en bytes con unidad binaria. */
export function formatBytes(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${formatters().decimal.format(value)} ${units[unit]}`;
}
