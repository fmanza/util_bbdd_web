#!/bin/sh
# Envoltorio de Graphviz `dot` (GAPS G39). util_bbdd dibuja siempre con `splines=ortho`, y el enrutado ortogonal de
# Graphviz 2.43 aborta en algunos grafos (`newtrap: Trapezoid-table overflow`, SIGABRT). Con el grafo por la entrada
# estándar (como lo pasa util_bbdd), si `dot` muere por una señal se repite una vez ese grafo con aristas poligonales:
# `-Gsplines=polyline` prevalece sobre el atributo del grafo. Con un fichero como argumento, `dot` sin más.
set -u
REAL_DOT="${UBW_REAL_DOT:-/usr/bin/dot}"
for arg in "$@"; do
  case "$arg" in
    -*) ;;
    *) exec "$REAL_DOT" "$@" ;;
  esac
done
in=$(mktemp) && out=$(mktemp) && err=$(mktemp) || exec "$REAL_DOT" "$@"
trap 'rm -f "$in" "$out" "$err"' EXIT
cat > "$in"
"$REAL_DOT" "$@" < "$in" > "$out" 2> "$err"
rc=$?
if [ "$rc" -gt 128 ]; then
  "$REAL_DOT" "$@" -Gsplines=polyline < "$in" > "$out" 2> "$err"
  rc=$?
fi
cat "$err" >&2
cat "$out"
exit "$rc"
