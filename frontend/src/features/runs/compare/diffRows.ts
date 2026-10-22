export type Side = { text: string; changed: boolean } | null;
export interface DiffRow {
  source: Side;
  target: Side;
}
interface Change {
  value: string;
  added?: boolean;
  removed?: boolean;
}

function lines(value: string): string[] {
  const parts = value.split('\n');
  if (parts.at(-1) === '') parts.pop();
  return parts;
}

/** Filas alineadas a partir de `diffLines(origen, destino)`: un bloque eliminado seguido de uno añadido se empareja. */
export function toRows(changes: Change[]): DiffRow[] {
  const rows: DiffRow[] = [];
  for (let i = 0; i < changes.length; i++) {
    const change = changes[i];
    if (!change) continue;
    if (!change.added && !change.removed) {
      for (const text of lines(change.value))
        rows.push({ source: { text, changed: false }, target: { text, changed: false } });
      continue;
    }
    const next = changes[i + 1];
    const removed = change.removed ? lines(change.value) : [];
    const added = change.added ? lines(change.value) : change.removed && next?.added ? lines(next.value) : [];
    if (change.removed && next?.added) i++;
    for (let j = 0; j < Math.max(removed.length, added.length); j++) {
      const left = removed[j];
      const right = added[j];
      rows.push({
        source: left === undefined ? null : { text: left, changed: true },
        target: right === undefined ? null : { text: right, changed: true },
      });
    }
  }
  return rows;
}
