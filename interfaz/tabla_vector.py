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
                             QApplication)
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt


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
    ("Reloj", "reloj", "time"),
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
    return "" if valor is None else str(valor)


class TablaVector(QTableWidget):
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

        # Encabezados fijos (el header horizontal no se desplaza verticalmente)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(False)

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
            headers.append(f"Cli {cid} Estado")
            headers.append(f"Cli {cid} Motivo")

        self.setColumnCount(len(headers))
        self.setRowCount(len(filas))
        self.setHorizontalHeaderLabels(headers)

        col_fija = len(COLUMNAS)
        for r, fila in enumerate(filas):
            for c, (_, clave, tipo) in enumerate(COLUMNAS):
                texto = _formatear(fila.get(clave), tipo)
                item = QTableWidgetItem(texto)
                item.setTextAlignment(Qt.AlignCenter)
                if fila.get("evento") == "Inicializacion" or \
                        str(fila.get("evento", "")).startswith("Fin"):
                    item.setBackground(QColor(225, 235, 245))
                self.setItem(r, c, item)

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
