const dateTime = new Intl.DateTimeFormat('es-ES', { dateStyle: 'short', timeStyle: 'medium' });
const decimal = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 });

/** Fecha ISO 8601 de la API en hora local. */
export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : '—';
}

/** Duración en segundos como «1 h 2 min», «3 min 4 s» o «5,2 s». */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${decimal.format(seconds)} s`;
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
  return `${decimal.format(value)} ${units[unit]}`;
}
