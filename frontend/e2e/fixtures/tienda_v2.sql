-- Segunda versión de tienda.sql para e2e/compare.spec.ts: sin el índice de pedidos, con `clientes.email`, una tabla
-- `facturas` nueva y la vista con otra definición.
DROP VIEW IF EXISTS v_pedidos;
DROP TABLE IF EXISTS facturas;
DROP TABLE IF EXISTS pedidos;
DROP TABLE IF EXISTS clientes;
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE, alta DATE, email TEXT);
CREATE TABLE pedidos (
  id INTEGER PRIMARY KEY,
  cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
  total NUMERIC(10, 2) CHECK (total >= 0)
);
CREATE TABLE facturas (id INTEGER PRIMARY KEY, pedido_id INTEGER REFERENCES pedidos(id));
CREATE VIEW v_pedidos AS SELECT p.id, c.nombre, p.total FROM pedidos p JOIN clientes c ON c.id = p.cliente_id;
