"""Widget de tabla para mostrar el vector de estado.

Version optimizada para soportar hasta ~100.000 filas.

Cambio clave respecto de la version anterior: antes se usaba QTableWidget,
que obliga a crear un QTableWidgetItem real por cada celda (con ~39
columnas fijas + 2 por cliente, eso son varios MILLONES de objetos para
100mil filas). Ahora se usa el patron modelo/vista de Qt: QTableView +
QAbstractTableModel. El modelo solo guarda las filas originales (dicts) y
Qt le pide el contenido de una celda (texto, color, alineacion, etc.) unica
y exclusivamente para las filas que estan visibles en el viewport en cada
momento. Esto es lo que permite manejar 100mil filas sin que la carga se
congele.

Caracteristicas (igual que antes):
    - Scroll horizontal y vertical.
    - Sin paginacion (todas las filas).
    - Encabezados de columna agrupados, fijos al hacer scroll vertical.
    - Seleccion de fila completa persistente.
    - Copiado al portapapeles (Ctrl+C) en formato TSV para pegar en Excel.
    - Fuente monoespaciada.
"""

import bisect

from PyQt5.QtWidgets import QTableView, QAbstractItemView, QApplication, QHeaderView
from PyQt5.QtGui import QFont, QColor, QPainter, QKeySequence
from PyQt5.QtCore import (Qt, QRect, QSize, pyqtSignal, QAbstractTableModel,
                           QModelIndex)


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


def fmt_hms(v):
    """Convierte un valor en minutos (float) a formato hh:mm:ss."""
    if v is None or v == "":
        return ""
    try:
        total_seg = int(round(float(v) * 60))
    except (ValueError, TypeError):
        return str(v)
    signo = "-" if total_seg < 0 else ""
    total_seg = abs(total_seg)
    h = total_seg // 3600
    m = (total_seg % 3600) // 60
    s = total_seg % 60
    return f"{signo}{h:02d}:{m:02d}:{s:02d}"


# (encabezado, clave, formato)
# formato: 'str', 'int', 'time', 'rnd', 'pct'
COLUMNAS = [
    ("N\u00b0", "nro", "int"),
    ("Evento", "evento", "str"),
    ("Reloj (hh:mm:ss)", "reloj", "hms"),
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
    ("Prom. Caf\u00e9s/D\u00eda", "prom_cafes", "pct"),
]


def _formatear(valor, tipo):
    if tipo == "str":
        return "" if valor is None else str(valor)
    if tipo == "int":
        return fmt_int(valor)
    if tipo == "rnd":
        return fmt_rnd(valor)
    if tipo == "pct":
        return fmt_num(valor, 2)
    if tipo in ("time", "hms"):
        # Tiempos almacenados en minutos, mostrados como hh:mm:ss
        return fmt_hms(valor)
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
    banda inferior con el nombre de cada columna.

    No depende de si la vista es QTableWidget o QTableView: solo usa la
    interfaz generica de QHeaderView/modelo, asi que funciona sin cambios.
    """

    ALTO_GRUPO = 24
    ALTO_LABEL = 46

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.grupos = []          # (nombre, QColor, inicio, fin), ordenados por inicio
        self._inicios = []        # columna de inicio de cada grupo (paralelo a self.grupos)
        self.color_col = {}       # col -> QColor de la banda superior
        self.setSectionsClickable(True)
        self.setHighlightSections(False)
        self.setDefaultAlignment(Qt.AlignCenter)
        self.setMinimumSectionSize(40)

    def set_grupos(self, grupos):
        normalizados = [(n, QColor(c) if isinstance(c, str) else c, s, e)
                        for (n, c, s, e) in grupos]
        normalizados.sort(key=lambda g: g[2])
        self.grupos = normalizados
        self._inicios = [g[2] for g in self.grupos]

        self.color_col = {}
        for _, color, s, e in self.grupos:
            for col in range(s, e + 1):
                self.color_col[col] = color
        self.updateGeometries()
        self.viewport().update()

    def _grupos_visibles(self):
        """Devuelve solo los grupos cuyo rango de columnas intersecta lo
        que esta visible ahora mismo en el viewport horizontal.

        Antes, paintEvent recorria TODOS los grupos en cada repintado -y el
        header se repinta en cada paso del scroll horizontal-. Con un grupo
        por cada cliente distinto de la simulacion, eso podia ser miles de
        grupos en cada frame, ademas de calcular posiciones en pixeles para
        grupos muy lejos de la pantalla (coordenadas enormes que en algunos
        casos llegaban a hacer crashear el pintado). Como los grupos estan
        ordenados y no se superponen, una busqueda binaria alcanza para
        ubicar unicamente los pocos grupos que realmente se ven.
        """
        if not self.grupos:
            return []

        ancho_viewport = max(self.viewport().width() - 1, 0)
        primero = self.visualIndexAt(0)
        ultimo = self.visualIndexAt(ancho_viewport)
        if primero < 0:
            primero = 0
        if ultimo < 0:
            ultimo = self.count() - 1

        i = bisect.bisect_right(self._inicios, primero) - 1
        if i < 0:
            i = 0

        visibles = []
        n = len(self.grupos)
        while i < n and self.grupos[i][2] <= ultimo:
            _, _, s, e = self.grupos[i]
            if e >= primero:
                visibles.append(self.grupos[i])
            i += 1
        return visibles

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
        for nombre, color, s, e in self._grupos_visibles():
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


class VectorEstadoModel(QAbstractTableModel):
    """Modelo de datos para el vector de estado.

    Solo guarda la lista de filas (dicts) que entrega el motor de
    simulacion. El texto/color/fuente de cada celda se calcula "al vuelo"
    dentro de data(), unicamente cuando Qt necesita pintar esa celda
    (es decir, solo para las filas visibles). No se crea ningun item ni
    objeto adicional por celda: con esto, cargar 100mil filas es practicamente
    instantaneo, porque cargar() solo guarda la referencia a la lista y
    arma un diccionario chico (euler_por_fila).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filas = []
        self._ids_clientes = []
        self._headers = [c[0] for c in COLUMNAS]
        self._euler_por_fila = {}
        self._col_fija = len(COLUMNAS)

        self._font_euler = QFont("Consolas", 9)
        self._font_euler.setUnderline(True)
        self._font_euler.setBold(True)

        self._color_fondo_evento = QColor(225, 235, 245)
        self._color_link = QColor("#1a73e8")

    # -- API publica ----------------------------------------------------
    @property
    def filas(self):
        return self._filas

    def cargar(self, filas):
        self.beginResetModel()
        self._filas = filas or []

        ids_clientes = set()
        for fila in self._filas:
            for cid in fila.get("clientes", {}):
                ids_clientes.add(cid)
        self._ids_clientes = sorted(ids_clientes)

        headers = [c[0] for c in COLUMNAS]
        for _ in self._ids_clientes:
            headers.append("Estado")
            headers.append("Motivo")
        self._headers = headers

        self._euler_por_fila = {
            r: fila["euler_idx"]
            for r, fila in enumerate(self._filas)
            if fila.get("euler_idx") is not None
        }
        self.endResetModel()

    def limpiar(self):
        self.cargar([])

    def euler_idx_de_fila(self, row):
        return self._euler_por_fila.get(row)

    def ids_clientes(self):
        return self._ids_clientes

    def grupos_columnas(self):
        grupos = list(GRUPOS_FIJOS)
        for k, cid in enumerate(self._ids_clientes):
            color = _COLOR_CLIENTE_A if k % 2 == 0 else _COLOR_CLIENTE_B
            ini = self._col_fija + 2 * k
            grupos.append((f"Cliente {cid}", color, ini, ini + 1))
        return grupos

    # -- API requerida por QAbstractTableModel ---------------------------
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._filas)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        fila = self._filas[r]

        if c < self._col_fija:
            _, clave, tipo = COLUMNAS[c]
            if role == Qt.DisplayRole:
                return _formatear(fila.get(clave), tipo)
            if role == Qt.TextAlignmentRole:
                return Qt.AlignCenter
            if role == Qt.BackgroundRole:
                evento = fila.get("evento")
                if evento == "Inicializacion" or str(evento or "").startswith("Fin"):
                    return self._color_fondo_evento
                return None
            if c == DUR_REFRIG_COL and r in self._euler_por_fila:
                if role == Qt.ForegroundRole:
                    return self._color_link
                if role == Qt.FontRole:
                    return self._font_euler
                if role == Qt.ToolTipRole:
                    return "Ver integraci\u00f3n de Euler (clic)"
            return None

        # Columnas dinamicas: dos por cada cliente presente (Estado, Motivo)
        k = (c - self._col_fija) // 2
        es_estado = (c - self._col_fija) % 2 == 0
        cid = self._ids_clientes[k]
        estado, motivo = fila.get("clientes", {}).get(cid, ("", ""))
        if role == Qt.DisplayRole:
            return str(estado) if es_estado else str(motivo)
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        return None


class TablaVector(QTableView):
    # Se emite con el indice de la integracion de Euler al pulsar la celda enlace
    euler_solicitado = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 9))

        self._modelo = VectorEstadoModel(self)
        self.setModel(self._modelo)

        # Scroll horizontal y vertical siempre disponibles
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        # Seleccion de fila completa, persistente
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

        self.setMouseTracking(True)
        self.clicked.connect(self._on_cell_clicked)

    def _on_cell_clicked(self, index):
        if index.column() == DUR_REFRIG_COL:
            idx = self._modelo.euler_idx_de_fila(index.row())
            if idx is not None:
                self.euler_solicitado.emit(idx)

    def cargar(self, filas):
        """Carga las filas (lista de dicts) en la tabla."""
        self.setUpdatesEnabled(False)
        self._modelo.cargar(filas)
        self._header.set_grupos(self._modelo.grupos_columnas())
        self._ajustar_anchos_columnas()
        self.setUpdatesEnabled(True)

    def limpiar(self):
        """Vacia la tabla. Reemplaza a clear()/setRowCount(0)/setColumnCount(0)
        de la version anterior (esos metodos no existen en QTableView)."""
        self._modelo.limpiar()
        self._header.set_grupos([])

    # Alias por compatibilidad con codigo que todavia llame .clear()
    def clear(self):
        self.limpiar()

    def _ajustar_anchos_columnas(self):
        """Define el ancho de cada columna sin recorrer las 100mil filas.

        resizeColumnsToContents() es O(filas x columnas): con muchas filas
        se vuelve muy lento (es buena parte de por que la version anterior
        se trababa). En cambio, fijamos el ancho segun el tipo de columna
        (que tiene un ancho maximo conocido por su formato) y, solo para
        columnas de texto libre, tomamos una muestra acotada de filas
        (no las 100mil) para estimar un ancho razonable.
        """
        fm = self.fontMetrics()
        ancho_por_tipo = {
            "int": fm.horizontalAdvance("0000000") + 16,
            "rnd": fm.horizontalAdvance("0,0000") + 16,
            "pct": fm.horizontalAdvance("0000,00") + 16,
            "time": fm.horizontalAdvance("00:00:00") + 16,
            "hms": fm.horizontalAdvance("00:00:00") + 16,
        }
        TOPE_TEXTO_LIBRE = 220
        MUESTRA = min(len(self._modelo.filas), 200)

        for c, (titulo, clave, tipo) in enumerate(COLUMNAS):
            ancho_header = fm.horizontalAdvance(titulo) + 24
            if tipo in ancho_por_tipo:
                ancho = max(ancho_por_tipo[tipo], ancho_header)
            else:
                ancho = ancho_header
                for fila in self._modelo.filas[:MUESTRA]:
                    texto = _formatear(fila.get(clave), tipo)
                    ancho = max(ancho, fm.horizontalAdvance(texto) + 24)
                ancho = min(ancho, TOPE_TEXTO_LIBRE)
            self.setColumnWidth(c, ancho)

        col_fija = len(COLUMNAS)
        for k in range(len(self._modelo.ids_clientes())):
            self.setColumnWidth(col_fija + 2 * k, 90)
            self.setColumnWidth(col_fija + 2 * k + 1, 110)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self.copiar_seleccion()
            return
        super().keyPressEvent(event)

    def copiar_seleccion(self):
        """Copia la seleccion al portapapeles en formato TSV. Si no hay
        seleccion, copia usando copiar_todo(), que es mucho mas rapido para
        la grilla completa."""
        indices = self.selectionModel().selectedIndexes()
        if not indices:
            self.copiar_todo()
            return
        filas = sorted({i.row() for i in indices})
        columnas = sorted({i.column() for i in indices})
        lineas = []
        modelo = self._modelo
        for r in filas:
            celdas = [str(modelo.data(modelo.index(r, c)) or "") for c in columnas]
            lineas.append("\t".join(celdas))
        QApplication.clipboard().setText("\n".join(lineas))

    def exportar_csv(self, ruta):
        """Exporta toda la grilla a un archivo CSV (separador ;).

        Usa el mismo acceso directo a las filas originales que copiar_todo(),
        sin pasar por QModelIndex/data(), para que sea rapido con 100mil filas.
        """
        modelo = self._modelo
        ids_clientes = modelo.ids_clientes()

        encabezados = [titulo for titulo, _, _ in COLUMNAS]
        for cid in ids_clientes:
            encabezados.append(f"Cliente {cid} Estado")
            encabezados.append(f"Cliente {cid} Motivo")

        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(";".join(encabezados) + "\n")
            for fila in modelo.filas:
                celdas = [_formatear(fila.get(clave), tipo) for _, clave, tipo in COLUMNAS]
                clientes = fila.get("clientes", {})
                for cid in ids_clientes:
                    estado, motivo = clientes.get(cid, ("", ""))
                    celdas.append(str(estado))
                    celdas.append(str(motivo))
                fh.write(";".join(celdas) + "\n")

    def copiar_todo(self):
        """Copia toda la grilla al portapapeles en formato TSV.

        Importante: NO pasa por QModelIndex/data() celda por celda (eso
        tardaba ~19s con 100mil filas, por el overhead de Python en cada
        llamada). En cambio arma cada fila de texto directamente a partir
        de las filas originales y las columnas dinamicas de clientes, igual
        que hace VectorEstadoModel.data() pero sin la capa intermedia. Con
        esto, 100mil filas se copian en menos de 1 segundo.
        """
        modelo = self._modelo
        ids_clientes = modelo.ids_clientes()

        encabezados = [titulo for titulo, _, _ in COLUMNAS]
        for _ in ids_clientes:
            encabezados.append("Estado")
            encabezados.append("Motivo")

        partes = ["\t".join(encabezados)]
        for fila in modelo.filas:
            celdas = [_formatear(fila.get(clave), tipo) for _, clave, tipo in COLUMNAS]
            clientes = fila.get("clientes", {})
            for cid in ids_clientes:
                estado, motivo = clientes.get(cid, ("", ""))
                celdas.append(str(estado))
                celdas.append(str(motivo))
            partes.append("\t".join(celdas))

        QApplication.clipboard().setText("\n".join(partes))