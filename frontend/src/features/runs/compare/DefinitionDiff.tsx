import { Loader, ScrollArea, Table, Text } from '@mantine/core';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { type DiffRow, type Side, toRows } from './diffRows';

const MONO = {
  fontFamily: 'var(--mantine-font-family-monospace)',
  fontSize: 12,
  whiteSpace: 'pre-wrap',
} as const;

function Cell({ side, marker, color }: { side: Side; marker: string; color: string }) {
  if (side === null) return <Table.Td style={MONO} />;
  return (
    <Table.Td
      style={{ ...MONO, background: side.changed ? `var(--mantine-color-${color}-light)` : undefined }}
    >
      <span aria-hidden="true">{side.changed ? marker : ' '} </span>
      {side.text}
    </Table.Td>
  );
}

/**
 * Definición de una vista o rutina en origen y destino, lado a lado. `diff` (jsdiff) se carga bajo demanda. Las líneas
 * cambiadas llevan color y un marcador (−/+), no solo color.
 */
export function DefinitionDiff({ source, target }: { source: string; target: string }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<DiffRow[] | null>(null);
  useEffect(() => {
    let alive = true;
    void import('diff').then(({ diffLines }) => {
      if (alive) setRows(toRows(diffLines(source, target)));
    });
    return () => {
      alive = false;
    };
  }, [source, target]);

  if (rows === null) return <Loader size="sm" aria-label={t('common.loading')} />;
  if (!source && !target) return <Text c="dimmed">{t('diff.noDefinition')}</Text>;
  const changed = rows.filter((row) => row.source?.changed || row.target?.changed).length;
  return (
    <ScrollArea.Autosize mah={420}>
      <Table withColumnBorders layout="fixed" aria-label={t('diff.definitionTable', { count: changed })}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('diff.source')}</Table.Th>
            <Table.Th>{t('diff.target')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row, index) => (
            <Table.Tr key={index}>
              <Cell side={row.source} marker="−" color="red" />
              <Cell side={row.target} marker="+" color="green" />
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </ScrollArea.Autosize>
  );
}
