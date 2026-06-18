"""Widget de tabla para mostrar el vector de estado.

Caracteristicas:
    - Scroll horizontal y vertical.
    - Sin paginacion (todas las filas).
    - Encabezados de columna fijos al hacer scroll (comportamiento nativo).
    - Seleccion de fila completa persistente.
    - Copiado al portapapeles (Ctrl+C) en formato TSV para pegar en Excel.
    - Fuente monoespaciada.
"""

from PyQt5.QtWidgets import (QTableWidget, QTableWidgetItem, QAbstractItemView,
                             QApplication, QHeaderView)
from PyQt5.QtGui import QFont, QColor, QPainter
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal


def fmt_num(v, dec=2):
    if v is None or v == "":
        return ""
    try:
        return f"{float(v):.{dec}f}".replace(".", ",")
    except (ValueError, TypeError):
        return str(v)


def fmt_rnd(v):
    return fmt_num(v, 4)


def fmt_int(v):
    if v is None or v == "":
        return ""
    return str(int(v))


# (encabezado, clave, formato)
# formato: 'str', 'int', 'time', 'rnd', 'pct'
COLUMNAS = [
    ("N\u00b0", "nro", "int"),
    ("Evento", "evento", "str"),
    ("Reloj (h)", "reloj", "hours"),
    ("RND Llegada", "rnd_llegada", "rnd"),
    ("Tiempo Llegada", "t_llegada", "time"),
    ("Pr\u00f3x. Llegada", "prox_llegada", "time"),
    ("RND Motivo", "rnd_motivo", "rnd"),
    ("Motivo", "motivo", "str"),
    ("fin_entrega", "fin_entrega", "time"),
    ("fin_retiro", "fin_retiro", "time"),
    ("RND Venta", "rnd_venta", "rnd"),
    ("Duraci\u00f3n Venta", "dur_venta", "time"),
    ("fin_venta", "fin_venta", "time"),
    ("RND Reparaci\u00f3n", "rnd_reparacion", "rnd"),
    ("Duraci\u00f3n Reparaci\u00f3n", "dur_reparacion", "time"),
    ("fin_reparaci\u00f3n", "fin_reparacion", "time"),
    ("RND Refrigerio", "rnd_refrig", "rnd"),
    ("\u00bfToma refrigerio?", "toma_refrig", "str"),
    ("RND Tipo", "rnd_tipo", "rnd"),
    ("Refresco \u00f3 Caf\u00e9", "tipo_refrig", "str"),
    ("Duraci\u00f3n Refrigerio", "dur_refrig", "time"),
    ("fin_refrigerio", "fin_refrigerio", "time"),
    ("Ayud. Estado", "ay_estado", "str"),
    ("Ayud. Cola", "ay_cola", "int"),
    ("Ayud. Inicio Ocup.", "ay_inicio", "time"),
    ("Reloj. Estado", "rel_estado", "str"),
    ("Cola A Reparar", "rel_cola_reparar", "int"),
    ("Cola Listos Retirar", "rel_listos", "int"),
    ("Reloj. Inicio Ocup.", "rel_inicio", "time"),
    ("Acum. Retiros Total", "acum_total_retiros", "int"),
    ("Acum. Sin Reloj", "acum_no_reloj", "int"),
    ("Prob. Sin Reloj (%)", "prob_no_reloj", "pct"),
    ("Acum. Ocup. Ayud.", "acum_ocup_ay", "time"),
    ("% Ocup. Ayud.", "porc_ocup_ay", "pct"),
    ("Acum. Ocup. Reloj.", "acum_ocup_rel", "time"),
    ("% Ocup. Reloj.", "porc_ocup_rel", "pct"),
    ("Acum. D\u00edas", "acum_dias", "int"),
    ("Acum. Caf\u00e9s", "acum_cafes", "int"),
    ("Prom. Caf\u00e9s/D\u00eda", "prom_cafes", "time"),
]


def _formatear(valor, tipo):
    if tipo == "str":
        return "" if valor is None else str(valor)
    if tipo == "int":
        return fmt_int(valor)
    if tipo == "rnd":
        return fmt_rnd(valor)
    if tipo in ("time", "pct"):
        return fmt_num(valor, 2)
    if tipo == "hours":
        # El reloj se muestra en horas (minutos / 60)
        if valor is None or valor == "":
            return ""
        return fmt_num(float(valor) / 60.0, 2)
    return "" if valor is None else str(valor)


# Indice de la columna "Duraci\u00f3n Refrigerio" (hipervinculo a la planilla Euler)
DUR_REFRIG_COL = next(i for i, c in enumerate(COLUMNAS) if c[1] == "dur_refrig")

# Grupos de columnas fijas: (nombre, color, col_inicio, col_fin_inclusive)
GRUPOS_FIJOS = [
    ("", "#E8E8E8", 0, 2),
    ("llegada_cliente", "#FFF2B2", 3, 7),
    ("fin_entrega", "#C6E7B0", 8, 8),
    ("fin_retiro", "#B7E1CD", 9, 9),
    ("fin_venta", "#FAD7A0", 10, 12),
    ("fin_reparaci\u00f3n", "#F5B7C4", 13, 15),
    ("fin_refrigerio", "#E8D3A2", 16, 21),
    ("Ayudante", "#AEE3E3", 22, 24),
    ("Relojero", "#BFE3D8", 25, 28),
    ("Prob. retiro sin reloj", "#D4EFDF", 29, 31),
    ("% Ocupaci\u00f3n ayudante y relojero", "#D5F5E3", 32, 35),
    ("Caf\u00e9s promedio por d\u00eda", "#FCF3CF", 36, 38),
]

_COLOR_CLIENTE_A = "#CFE2F3"
_COLOR_CLIENTE_B = "#A9CCE3"


class GroupedHeaderView(QHeaderView):
    """Encabezado de dos niveles: banda superior agrupadora (con color) y
    banda inferior con el nombre de cada columna."""

    ALTO_GRUPO = 24
    ALTO_LABEL = 46

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.grupos = []          # (nombre, QColor, inicio, fin)
        self.color_col = {}       # col -> QColor de la banda superior
        self.setSectionsClickable(True)
        self.setHighlightSections(False)
        self.setDefaultAlignment(Qt.AlignCenter)
        self.setMinimumSectionSize(40)

    def set_grupos(self, grupos):
        self.grupos = [(n, QColor(c) if isinstance(c, str) else c, s, e)
                       for (n, c, s, e) in grupos]
        self.color_col = {}
        for _, color, s, e in self.grupos:
            for col in range(s, e + 1):
                self.color_col[col] = color
        self.updateGeometries()
        self.viewport().update()

    def sizeHint(self):
        base = super().sizeHint()
        return QSize(base.width(), self.ALTO_GRUPO + self.ALTO_LABEL)

    def paintSection(self, painter, rect, idx):
        painter.save()
        painter.setClipRect(rect)
        top = QRect(rect.left(), rect.top(), rect.width(), self.ALTO_GRUPO)
        bottom = QRect(rect.left(), rect.top() + self.ALTO_GRUPO,
                       rect.width(), rect.height() - self.ALTO_GRUPO)

        color = self.color_col.get(idx, QColor("#E8E8E8"))
        painter.fillRect(top, color)
        painter.fillRect(bottom, QColor("#F5F5F5"))

        painter.setPen(QColor("#9AA0A6"))
        painter.drawRect(bottom.adjusted(0, 0, -1, -1))
        painter.drawLine(top.topLeft(), top.bottomLeft())
        painter.drawLine(top.topRight(), top.bottomRight())

        texto = self.model().headerData(idx, Qt.Horizontal)
        painter.setPen(Qt.black)
        f = painter.font()
        f.setBold(False)
        painter.setFont(f)
        painter.drawText(bottom.adjusted(2, 1, -2, -1),
                         Qt.AlignCenter | Qt.TextWordWrap, str(texto or ""))
        painter.restore()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        f = painter.font()
        f.setBold(True)
        painter.setFont(f)
        for nombre, color, s, e in self.grupos:
            x = self.sectionViewportPosition(s)
            derecha = self.sectionViewportPosition(e) + self.sectionSize(e)
            ancho = derecha - x
            rect = QRect(x, 0, ancho, self.ALTO_GRUPO)
            painter.fillRect(rect, color)
            painter.setPen(QColor("#7A7F85"))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            if nombre:
                painter.setPen(Qt.black)
                painter.drawText(rect.adjusted(2, 1, -2, -1),
                                 Qt.AlignCenter | Qt.TextWordWrap, nombre)
        painter.end()


class TablaVector(QTableWidget):
    # Se emite con el indice de la integracion de Euler al pulsar la celda enlace
    euler_solicitado = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 9))

        # Scroll horizontal y vertical siempre disponibles
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        # Seleccion de fila completa, persistente, sin parpadeo
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)

        # Encabezado agrupado de dos niveles (fijo al hacer scroll vertical)
        self._header = GroupedHeaderView(self)
        self.setHorizontalHeader(self._header)
        self.verticalHeader().setVisible(False)
        self._header.setStretchLastSection(False)

        # Mapa fila_visible -> indice de integracion de Euler (celda enlace)
        self._euler_por_fila = {}
        self.cellClicked.connect(self._on_cell_clicked)
        self.setMouseTracking(True)

    def _on_cell_clicked(self, row, col):
        if col == DUR_REFRIG_COL and row in self._euler_por_fila:
            self.euler_solicitado.emit(self._euler_por_fila[row])

    def cargar(self, filas):
        """Carga las filas (lista de dicts) en la tabla."""
        self.setUpdatesEnabled(False)
        self.clear()

        # Determinar clientes presentes para crear columnas dinamicas
        ids_clientes = set()
        for fila in filas:
            for cid in fila.get("clientes", {}):
                ids_clientes.add(cid)
        ids_clientes = sorted(ids_clientes)

        # Construir cabeceras
        headers = [c[0] for c in COLUMNAS]
        for cid in ids_clientes:
            headers.append("Estado")
            headers.append("Motivo")

        self.setColumnCount(len(headers))
        self.setRowCount(len(filas))
        self.setHorizontalHeaderLabels(headers)

        # Grupos: fijos + un grupo por cliente
        col_fija = len(COLUMNAS)
        grupos = list(GRUPOS_FIJOS)
        for k, cid in enumerate(ids_clientes):
            color = _COLOR_CLIENTE_A if k % 2 == 0 else _COLOR_CLIENTE_B
            ini = col_fija + 2 * k
            grupos.append((f"Cliente {cid}", color, ini, ini + 1))
        self._header.set_grupos(grupos)

        self._euler_por_fila = {}
        for r, fila in enumerate(filas):
            for c, (_, clave, tipo) in enumerate(COLUMNAS):
                texto = _formatear(fila.get(clave), tipo)
                item = QTableWidgetItem(texto)
                item.setTextAlignment(Qt.AlignCenter)
                if fila.get("evento") == "Inicializacion" or \
                        str(fila.get("evento", "")).startswith("Fin"):
                    item.setBackground(QColor(225, 235, 245))
                self.setItem(r, c, item)

            # Celda enlace a la planilla de Euler
            euler_idx = fila.get("euler_idx")
            if euler_idx is not None:
                self._euler_por_fila[r] = euler_idx
                item = self.item(r, DUR_REFRIG_COL)
                if item is not None:
                    f = item.font()
                    f.setUnderline(True)
                    f.setBold(True)
                    item.setFont(f)
                    item.setForeground(QColor("#1a73e8"))
                    item.setToolTip("Ver integraci\u00f3n de Euler (clic)")

            clientes = fila.get("clientes", {})
            for k, cid in enumerate(ids_clientes):
                estado, motivo = clientes.get(cid, ("", ""))
                it_estado = QTableWidgetItem(str(estado))
                it_motivo = QTableWidgetItem(str(motivo))
                it_estado.setTextAlignment(Qt.AlignCenter)
                it_motivo.setTextAlignment(Qt.AlignCenter)
                self.setItem(r, col_fija + 2 * k, it_estado)
                self.setItem(r, col_fija + 2 * k + 1, it_motivo)

        self.resizeColumnsToContents()
        self.setUpdatesEnabled(True)

    def keyPressEvent(self, event):
        if event.matches(self._copy_sequence()):
            self.copiar_seleccion()
            return
        super().keyPressEvent(event)

    @staticmethod
    def _copy_sequence():
        from PyQt5.QtGui import QKeySequence
        return QKeySequence.Copy

    def copiar_seleccion(self):
        """Copia la seleccion (o toda la grilla) al portapapeles en formato TSV."""
        rangos = self.selectedRanges()
        if not rangos:
            return
        # Si no hay seleccion real, copiar todo
        filas_txt = []
        # Tomar el rango maximo cubierto por la seleccion
        seleccionadas = sorted({idx.row() for idx in self.selectedIndexes()})
        columnas = sorted({idx.column() for idx in self.selectedIndexes()})
        if not seleccionadas:
            seleccionadas = range(self.rowCount())
            columnas = range(self.columnCount())

        for r in seleccionadas:
            celdas = []
            for c in columnas:
                item = self.item(r, c)
                celdas.append(item.text() if item else "")
            filas_txt.append("\t".join(celdas))

        QApplication.clipboard().setText("\n".join(filas_txt))

    def copiar_todo(self):
        filas_txt = []
        encabezados = [self.horizontalHeaderItem(c).text()
                       for c in range(self.columnCount())]
        filas_txt.append("\t".join(encabezados))
        for r in range(self.rowCount()):
            celdas = []
            for c in range(self.columnCount()):
                item = self.item(r, c)
                celdas.append(item.text() if item else "")
            filas_txt.append("\t".join(celdas))
        QApplication.clipboard().setText("\n".join(filas_txt))
