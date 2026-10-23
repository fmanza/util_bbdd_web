-- Origen de e2e/dump.spec.ts (sin columnas de fecha: SQLite → SQLite no las carga desde texto, GAPS G33).
DROP TABLE IF EXISTS pedidos;
DROP TABLE IF EXISTS clientes;
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE);
CREATE TABLE pedidos (
  id INTEGER PRIMARY KEY,
  cliente_id INTEGER NOT NULL REFERENCES clientes(id),
  total NUMERIC(10, 2) CHECK (total >= 0)
);
INSERT INTO clientes VALUES (1, 'ana'), (2, 'luis');
INSERT INTO pedidos VALUES (10, 1, 9.5), (11, 1, 20), (12, 2, 3.25);
