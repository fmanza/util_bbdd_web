"""Lo que la web comprueba de una plantilla Excel al subirla (ADR-011, GAPS G40).

Desde util_bbdd 4.1.0 la plantilla la aplica util_bbdd (``imprimir["plantilla_excel"]`` y ``table_style_excel``): tema,
colores de la paleta fija → colores del tema, fuentes del tema, encabezado, pie y página de su primera hoja. Aquí solo
quedan los estilos de tabla que se pueden elegir y la comprobación del tema, para rechazar la plantilla al subirla en
lugar de al usarla.
"""

from __future__ import annotations

import re
from typing import Final

#: Estilos de tabla predefinidos de Excel (los únicos que se pueden elegir: G40).
TABLE_STYLES: Final[tuple[str, ...]] = (
    *(f"TableStyleLight{i}" for i in range(1, 22)),
    *(f"TableStyleMedium{i}" for i in range(1, 29)),
    *(f"TableStyleDark{i}" for i in range(1, 12)),
)
DEFAULT_TABLE_STYLE: Final = "TableStyleMedium2"

_THEME_RELS = re.compile(rb"\br:(?:embed|link|id)\s*=")


def theme_is_safe(theme: bytes | None) -> bool:
    """Si el tema se puede copiar tal cual: openpyxl no copia sus ``.rels`` (imágenes), y Excel lo daría por dañado.

    util_bbdd 4.1.0 rechaza esos temas al usar la plantilla; la web lo comprueba antes, al subirla.
    """
    return theme is None or _THEME_RELS.search(theme) is None
