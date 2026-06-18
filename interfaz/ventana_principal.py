"""Ventana principal de la aplicacion (PyQt5).

Contiene el formulario de parametros, los botones de control, el panel de
resultados estadisticos y las pestanas con el vector de estado y el detalle
de las integraciones de Euler. Toda la logica de simulacion vive en el modulo
``simulacion`` (separacion modelo / interfaz).
"""

import os
import sys

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QDoubleSpinBox, QSpinBox,
    QGridLayout, QVBoxLayout, QHBoxLayout, QGroupBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QComboBox, QFormLayout, QMessageBox, QScrollArea,
    QFileDialog, QSizePolicy
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

# Permitir ejecutar tanto como paquete como script suelto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulacion import Simulacion, Parametros
from interfaz.tabla_vector import TablaVector, fmt_num


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulacion de Colas - Relojeria")
        self.resize(1400, 850)

        self.sim = None
        self._construir_ui()

    # ------------------------------------------------------------------
    # Construccion de la interfaz
    # ------------------------------------------------------------------
    def _spin(self, valor, minimo, maximo, paso, decimales=2):
        sb = QDoubleSpinBox()
        sb.setRange(minimo, maximo)
        sb.setSingleStep(paso)
        sb.setDecimals(decimales)
        sb.setValue(valor)
        sb.setMinimumWidth(90)
        return sb

    def _ispin(self, valor, minimo, maximo):
        sb = QSpinBox()
        sb.setRange(minimo, maximo)
        sb.setValue(valor)
        sb.setMinimumWidth(90)
        return sb

    def _construir_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # ---- Panel izquierdo: parametros + controles + resultados ----
        panel_izq = QVBoxLayout()
        panel_izq.addWidget(self._grupo_parametros())
        panel_izq.addWidget(self._grupo_controles())
        panel_izq.addWidget(self._grupo_resultados())
        panel_izq.addStretch(1)

        cont_izq = QWidget()
        cont_izq.setLayout(panel_izq)
        cont_izq.setMaximumWidth(380)

        scroll_izq = QScrollArea()
        scroll_izq.setWidgetResizable(True)
        scroll_izq.setWidget(cont_izq)
        scroll_izq.setMaximumWidth(400)

        layout.addWidget(scroll_izq)

        # ---- Panel derecho: pestanas ----
        self.tabs = QTabWidget()
        self.tabla = TablaVector()
        self.tabs.addTab(self.tabla, "Vector de Estado")
        self.tabs.addTab(self._tab_euler(), "Integraci\u00f3n Euler")
        layout.addWidget(self.tabs, 1)

    def _grupo_parametros(self):
        grupo = QGroupBox("Par\u00e1metros")
        form = QFormLayout(grupo)

        self.in_X = self._spin(1440, 1, 1_000_000, 10, 2)
        self.in_i = self._ispin(100, 1, 1_000_000)
        self.in_j = self._spin(0, 0, 1_000_000, 10, 2)
        self.in_A = self._spin(13, 0, 10_000, 1, 2)
        self.in_B = self._spin(17, 0, 10_000, 1, 2)
        self.in_C = self._spin(6, 0, 10_000, 1, 2)
        self.in_D = self._spin(10, 0, 10_000, 1, 2)
        self.in_E = self._spin(18, 0, 10_000, 1, 2)
        self.in_F = self._spin(22, 0, 10_000, 1, 2)
        self.in_pc = self._spin(0.45, 0, 1, 0.01, 4)
        self.in_pe = self._spin(0.25, 0, 1, 0.01, 4)
        self.in_pr = self._spin(0.30, 0, 1, 0.01, 4)
        self.in_pref = self._spin(0.10, 0, 1, 0.01, 4)
        self.in_a = self._spin(1.0, -10_000, 10_000, 0.1, 4)
        self.in_h = self._spin(0.1, 0.0001, 100, 0.01, 4)

        form.addRow("X - Tiempo total (min):", self.in_X)
        form.addRow("i - Iteraciones a mostrar:", self.in_i)
        form.addRow("j - Inicio intervalo (min):", self.in_j)
        form.addRow("A - Llegada min:", self.in_A)
        form.addRow("B - Llegada max:", self.in_B)
        form.addRow("C - Venta min:", self.in_C)
        form.addRow("D - Venta max:", self.in_D)
        form.addRow("E - Reparaci\u00f3n min:", self.in_E)
        form.addRow("F - Reparaci\u00f3n max:", self.in_F)
        form.addRow("Prob. Comprar:", self.in_pc)
        form.addRow("Prob. Entregar:", self.in_pe)
        form.addRow("Prob. Retirar:", self.in_pr)
        form.addRow("Prob. Refrigerio:", self.in_pref)
        form.addRow("a - Constante de apuro:", self.in_a)
        form.addRow("h - Paso de Euler:", self.in_h)
        return grupo

    def _grupo_controles(self):
        grupo = QGroupBox("Controles")
        lay = QVBoxLayout(grupo)

        self.btn_simular = QPushButton("Simular")
        self.btn_simular.clicked.connect(self.simular)
        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.clicked.connect(self.limpiar)
        self.btn_copiar = QPushButton("Copiar grilla completa")
        self.btn_copiar.clicked.connect(lambda: self.tabla.copiar_todo())

        lay.addWidget(self.btn_simular)
        lay.addWidget(self.btn_limpiar)
        lay.addWidget(self.btn_copiar)
        return grupo

    def _grupo_resultados(self):
        grupo = QGroupBox("Resultados estad\u00edsticos")
        form = QFormLayout(grupo)
        self.lbl_prob = QLabel("-")
        self.lbl_ocup_ay = QLabel("-")
        self.lbl_ocup_rel = QLabel("-")
        self.lbl_cafes = QLabel("-")
        for lbl in (self.lbl_prob, self.lbl_ocup_ay, self.lbl_ocup_rel, self.lbl_cafes):
            lbl.setFont(QFont("Consolas", 10, QFont.Bold))
        form.addRow("Prob. retiro sin reloj (%):", self.lbl_prob)
        form.addRow("% Ocupaci\u00f3n ayudante:", self.lbl_ocup_ay)
        form.addRow("% Ocupaci\u00f3n relojero:", self.lbl_ocup_rel)
        form.addRow("Caf\u00e9s promedio / d\u00eda:", self.lbl_cafes)
        return grupo

    def _tab_euler(self):
        cont = QWidget()
        lay = QVBoxLayout(cont)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("Refrigerio:"))
        self.combo_euler = QComboBox()
        self.combo_euler.currentIndexChanged.connect(self._mostrar_euler)
        fila.addWidget(self.combo_euler, 1)
        self.btn_export_euler = QPushButton("Exportar a CSV")
        self.btn_export_euler.clicked.connect(self._exportar_euler)
        fila.addWidget(self.btn_export_euler)
        lay.addLayout(fila)

        self.lbl_euler_info = QLabel("-")
        lay.addWidget(self.lbl_euler_info)

        self.tabla_euler = QTableWidget()
        self.tabla_euler.setColumnCount(3)
        self.tabla_euler.setHorizontalHeaderLabels(["t_local", "D", "dD/dt"])
        self.tabla_euler.setFont(QFont("Consolas", 9))
        lay.addWidget(self.tabla_euler)
        return cont

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _leer_parametros(self):
        return Parametros(
            X=self.in_X.value(),
            A=self.in_A.value(), B=self.in_B.value(),
            C=self.in_C.value(), D=self.in_D.value(),
            E=self.in_E.value(), F=self.in_F.value(),
            prob_comprar=self.in_pc.value(),
            prob_entregar=self.in_pe.value(),
            prob_retirar=self.in_pr.value(),
            prob_refrigerio=self.in_pref.value(),
            a=self.in_a.value(),
            h=self.in_h.value(),
        )

    def simular(self):
        p = self._leer_parametros()

        # Validaciones basicas
        if p.A > p.B or p.C > p.D or p.E > p.F:
            QMessageBox.warning(self, "Par\u00e1metros inv\u00e1lidos",
                                "Verifique que A<=B, C<=D y E<=F.")
            return
        suma = p.prob_comprar + p.prob_entregar + p.prob_retirar
        if abs(suma - 1.0) > 1e-6:
            QMessageBox.warning(self, "Probabilidades inv\u00e1lidas",
                                f"Las probabilidades de motivo deben sumar 1 "
                                f"(actual: {suma:.4f}).")
            return

        self.btn_simular.setEnabled(False)
        QWidget.setCursor(self, Qt.WaitCursor)
        try:
            self.sim = Simulacion(p)
            self.sim.ejecutar()
        finally:
            QWidget.unsetCursor(self)
            self.btn_simular.setEnabled(True)

        # Filtrado de filas a mostrar: reloj >= j, hasta i filas + ultima fila
        j = self.in_j.value()
        i = self.in_i.value()
        filas = self.sim.filas
        filtradas = [f for f in filas if f["reloj"] >= j]
        mostradas = filtradas[:i]
        ultima = filas[-1]
        if ultima not in mostradas:
            mostradas = mostradas + [ultima]

        self.tabla.cargar(mostradas)
        self._mostrar_resultados()
        self._cargar_euler()

    def _mostrar_resultados(self):
        est = self.sim.estadisticas()
        self.lbl_prob.setText(fmt_num(est["prob_retiro_sin_reloj"], 2) + " %")
        self.lbl_ocup_ay.setText(fmt_num(est["porc_ocup_ayudante"], 2) + " %")
        self.lbl_ocup_rel.setText(fmt_num(est["porc_ocup_relojero"], 2) + " %")
        self.lbl_cafes.setText(fmt_num(est["prom_cafes_dia"], 4))

    def _cargar_euler(self):
        self.combo_euler.blockSignals(True)
        self.combo_euler.clear()
        for d in self.sim.euler_detalles:
            self.combo_euler.addItem(
                f"#{d['numero']} - {d['tipo']} @ reloj {d['reloj']:.2f} "
                f"(R={d['R']}, dur={d['duracion']:.2f})"
            )
        self.combo_euler.blockSignals(False)
        if self.sim.euler_detalles:
            self.combo_euler.setCurrentIndex(0)
            self._mostrar_euler(0)
        else:
            self.tabla_euler.setRowCount(0)
            self.lbl_euler_info.setText("No se registraron refrigerios.")

    def _mostrar_euler(self, idx):
        if self.sim is None or idx < 0 or idx >= len(self.sim.euler_detalles):
            return
        d = self.sim.euler_detalles[idx]
        self.lbl_euler_info.setText(
            f"Refrigerio #{d['numero']} - {d['tipo']} | C_act={d['c_act']} | "
            f"R={d['R']} | Duraci\u00f3n={d['duracion']:.4f} min | "
            f"pasos={len(d['historial']) - 1}"
        )
        hist = d["historial"]
        self.tabla_euler.setRowCount(len(hist))
        for r, fila in enumerate(hist):
            t_it = QTableWidgetItem(fmt_num(fila["t"], 4))
            d_it = QTableWidgetItem(fmt_num(fila["D"], 4))
            dd_it = QTableWidgetItem(fmt_num(fila["dD"], 4) if fila["dD"] is not None else "")
            for it in (t_it, d_it, dd_it):
                it.setTextAlignment(Qt.AlignCenter)
            self.tabla_euler.setItem(r, 0, t_it)
            self.tabla_euler.setItem(r, 1, d_it)
            self.tabla_euler.setItem(r, 2, dd_it)
        self.tabla_euler.resizeColumnsToContents()

    def _exportar_euler(self):
        if self.sim is None or not self.sim.euler_detalles:
            QMessageBox.information(self, "Exportar", "No hay datos de Euler.")
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar integraciones de Euler", "euler.csv",
            "CSV (*.csv)")
        if not ruta:
            return
        with open(ruta, "w", encoding="utf-8") as fh:
            for d in self.sim.euler_detalles:
                fh.write(f"Refrigerio #{d['numero']};{d['tipo']};"
                         f"C_act={d['c_act']};R={d['R']};duracion={d['duracion']:.4f}\n")
                fh.write("t_local;D;dD/dt\n")
                for fila in d["historial"]:
                    dd = "" if fila["dD"] is None else f"{fila['dD']:.6f}"
                    fh.write(f"{fila['t']:.6f};{fila['D']:.6f};{dd}\n")
                fh.write("\n")
        QMessageBox.information(self, "Exportar", f"Guardado en:\n{ruta}")

    def limpiar(self):
        self.tabla.clear()
        self.tabla.setRowCount(0)
        self.tabla.setColumnCount(0)
        self.tabla_euler.setRowCount(0)
        self.combo_euler.clear()
        self.lbl_euler_info.setText("-")
        self.lbl_prob.setText("-")
        self.lbl_ocup_ay.setText("-")
        self.lbl_ocup_rel.setText("-")
        self.lbl_cafes.setText("-")
        self.sim = None
