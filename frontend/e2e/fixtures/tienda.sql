-- BD SQLite de ejemplo para e2e/explorer.spec.ts (ver la cabecera del spec).
DROP VIEW IF EXISTS v_pedidos;
DROP TABLE IF EXISTS pedidos;
DROP TABLE IF EXISTS clientes;
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE, alta DATE);
CREATE TABLE pedidos (
  id INTEGER PRIMARY KEY,
  cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
  total NUMERIC(10, 2) CHECK (total >= 0)
);
CREATE INDEX ix_pedidos_cliente ON pedidos(cliente_id);
CREATE VIEW v_pedidos AS SELECT p.id, c.nombre FROM pedidos p JOIN clientes c ON c.id = p.cliente_id;
INSERT INTO clientes VALUES (1, 'ana', '2026-01-01'), (2, 'luis', NULL);
INSERT INTO pedidos VALUES (10, 1, 9.5), (11, 1, 20), (12, 2, 3.25);
