import { MantineProvider } from '@mantine/core';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import '../i18n';
import i18n from '../i18n';
import { DataTable } from './DataTable';
import { type Column, clientRows } from './tableState';

interface Row {
  id: number;
  name: string;
  size: number;
}

const ROWS: Row[] = Array.from({ length: 30 }, (_, i) => ({
  id: i + 1,
  name: `tabla ${i + 1}`,
  size: (i * 7) % 11,
}));
const COLUMNS: Column<Row>[] = [
  {
    key: 'name',
    header: 'Nombre',
    sortable: true,
    searchable: true,
    value: (r) => r.name,
    cell: (r) => r.name,
  },
  { key: 'size', header: 'Tamaño', sortable: true, value: (r) => r.size, cell: (r) => r.size },
];

i18n.addResourceBundle('es', 'translation', {
  table: { sortBy: 'Ordenar por {{column}}', range: '{{first}}-{{last}} de {{total}}' },
});

function renderTable(rows: Row[] = ROWS) {
  return render(
    <MantineProvider>
      <DataTable
        mode="client"
        label="Tablas"
        searchLabel="Buscar"
        empty="Nada"
        columns={COLUMNS}
        rowKey={(r) => r.id}
        rows={rows}
      />
    </MantineProvider>,
  );
}

const bodyRows = () =>
  within(screen.getByRole('table', { name: 'Tablas' }))
    .getAllByRole('row')
    .slice(1);

function bodyRow(index: number): HTMLElement {
  const row = bodyRows()[index];
  if (!row) throw new Error(`Sin fila ${index}`);
  return row;
}

describe('DataTable (cliente)', () => {
  it('pagina de 25 en 25 con el recuento', async () => {
    const user = userEvent.setup();
    renderTable();

    expect(bodyRows()).toHaveLength(25);
    expect(screen.getByText('1-25 de 30')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '2' }));
    expect(bodyRows()).toHaveLength(5);
    expect(screen.getByText('26-30 de 30')).toBeInTheDocument();
  });

  it('ordena por columna (asc, desc, sin orden) con aria-sort y orden natural', async () => {
    const user = userEvent.setup();
    renderTable();
    const header = () => screen.getByRole('columnheader', { name: /Nombre/ });

    expect(header()).toHaveAttribute('aria-sort', 'none');
    await user.click(screen.getByRole('button', { name: 'Ordenar por Nombre' }));
    expect(header()).toHaveAttribute('aria-sort', 'ascending');
    expect(within(bodyRow(0)).getByText('tabla 1')).toBeInTheDocument();
    expect(within(bodyRow(1)).getByText('tabla 2')).toBeInTheDocument(); // 2 antes que 10
    await user.click(screen.getByRole('button', { name: 'Ordenar por Nombre' }));
    expect(header()).toHaveAttribute('aria-sort', 'descending');
    expect(within(bodyRow(0)).getByText('tabla 30')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Ordenar por Nombre' }));
    expect(header()).toHaveAttribute('aria-sort', 'none');
  });

  it('busca en las columnas buscables y vuelve a la primera página', async () => {
    const user = userEvent.setup();
    renderTable();

    await user.click(screen.getByRole('button', { name: '2' }));
    await user.type(screen.getByRole('textbox', { name: 'Buscar' }), 'tabla 2');
    expect(bodyRows()).toHaveLength(11); // 2 y 20-29
    expect(screen.getByText('1-11 de 11')).toBeInTheDocument();
    await user.clear(screen.getByRole('textbox', { name: 'Buscar' }));
    await user.type(screen.getByRole('textbox', { name: 'Buscar' }), 'no existe');
    expect(screen.getByText('Nada')).toBeInTheDocument();
  });
});

describe('clientRows', () => {
  it('ordena de forma estable y deja los vacíos al final', () => {
    const rows = [
      { id: 1, name: 'b', size: 1 },
      { id: 2, name: '', size: 1 },
      { id: 3, name: 'a', size: 1 },
    ];
    expect(clientRows(rows, COLUMNS, '', { key: 'name', order: 'asc' }).map((r) => r.id)).toEqual([3, 1, 2]);
    expect(clientRows(rows, COLUMNS, '', { key: 'size', order: 'desc' }).map((r) => r.id)).toEqual([1, 2, 3]);
  });
});
