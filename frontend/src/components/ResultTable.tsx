import { Alert, Group, ScrollArea, Table, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import type { components } from '../api/schema';

type QueryResult = components['schemas']['QueryResultOut'];

/** Resultado de una consulta: cabeceras, filas (NULL atenuado) y aviso si se recortó al límite. */
export function ResultTable({ result }: { result: QueryResult }) {
  const { t } = useTranslation();
  return (
    <div aria-live="polite">
      <Group justify="space-between" mb="xs">
        <Text size="sm">
          {t('explorer.result.rows', { count: result.row_count, ms: result.duration_ms })}
        </Text>
      </Group>
      {result.truncated && (
        <Alert color="yellow" mb="xs">
          {t('explorer.result.truncated', { count: result.row_count })}
        </Alert>
      )}
      {result.columns.length === 0 ? (
        <Text c="dimmed">{t('explorer.result.noColumns')}</Text>
      ) : (
        <ScrollArea type="auto" mah={480}>
          <Table striped withTableBorder withColumnBorders fz="sm">
            <Table.Thead>
              <Table.Tr>
                {result.columns.map((column, index) => (
                  <Table.Th key={`${column}-${index}`}>{column}</Table.Th>
                ))}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {result.rows.map((row, rowIndex) => (
                <Table.Tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <Table.Td key={cellIndex} ff="monospace">
                      {cell === null ? (
                        <Text span c="dimmed" fs="italic">
                          NULL
                        </Text>
                      ) : (
                        String(cell)
                      )}
                    </Table.Td>
                  ))}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea>
      )}
    </div>
  );
}
