"""Motor de simulacion por eventos discretos de la relojeria.

La logica esta completamente separada de la interfaz grafica. La clase
``Simulacion`` recibe los parametros, ejecuta el bucle de eventos y produce:
    - ``filas``: el vector de estado, pero SOLO la ventana a mostrar
      (las ``i`` iteraciones a partir del instante ``j``) mas la fila final.
      Las iteraciones fuera de esa ventana se simulan pero no se guardan.
    - ``estadisticas``: metricas finales
    - ``euler_detalles``: historial de cada integracion de refrigerio guardada
"""

import math
import random
from dataclasses import dataclass, field

import entidades as ent
from integracion_euler import integrar_refrigerio


@dataclass
class Parametros:
    """Parametros configurables de la simulacion."""
    X: float = 1440.0          # tiempo total de simulacion (minutos)
    A: float = 13.0            # tiempo minimo entre llegadas
    B: float = 17.0            # tiempo maximo entre llegadas
    C: float = 6.0             # tiempo minimo de venta
    D: float = 10.0            # tiempo maximo de venta
    E: float = 18.0            # tiempo minimo de reparacion
    F: float = 22.0            # tiempo maximo de reparacion
    prob_comprar: float = 0.45
    prob_entregar: float = 0.25
    prob_retirar: float = 0.30
    prob_refrigerio: float = 0.10
    a: float = 1.0             # constante de apuro (Euler)
    h: float = 0.1             # paso de integracion (Euler)
    listos_iniciales: int = 3
    i: int = 100               # cantidad de filas a persistir/mostrar
    j: float = 0.0             # instante (minutos) desde el cual se persisten filas
    max_iteraciones: int = 100_000


# Nombres internos de los eventos de la FEL
EV_LLEGADA = "llegada_cliente"
EV_FIN_VENTA = "fin_venta"
EV_FIN_RETIRO = "fin_retiro"
EV_FIN_ENTREGA = "fin_entrega"
EV_FIN_REPARACION = "fin_reparacion"
EV_FIN_REFRIGERIO = "fin_refrigerio"


class Simulacion:
    def __init__(self, params: Parametros):
        self.p = params
        self.reloj = 0.0
        self.iteracion = 0

        # Objetos permanentes
        self.ayudante = ent.Ayudante()
        self.relojero = ent.Relojero(params.listos_iniciales)

        # Lista de eventos futuros (FEL): nombre -> tiempo o None
        self.fel = {
            EV_LLEGADA: None,
            EV_FIN_VENTA: None,
            EV_FIN_RETIRO: None,
            EV_FIN_ENTREGA: None,
            EV_FIN_REPARACION: None,
            EV_FIN_REFRIGERIO: None,
        }

        # Clientes activos en el sistema (objetos temporales)
        self.clientes_activos = []
        self._proximo_id_cliente = 0

        # Acumuladores estadisticos
        self.acum_total_retiros = 0
        self.acum_no_reloj = 0
        self.acum_ocup_ayudante = 0.0
        self.acum_ocup_relojero = 0.0
        self.acum_cafes = 0

        # Salidas (solo se guarda la ventana [j, j+i iteraciones) + fila final)
        self.filas = []
        self.euler_detalles = []   # lista de dicts: numero, tipo, historial
        self._guardadas = 0        # filas de la ventana ya persistidas

        # Cliente que abandona el sistema en el evento actual (para mostrar "-")
        self._cliente_saliente = None

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _nuevo_cliente(self, motivo):
        self._proximo_id_cliente += 1
        c = ent.Cliente(self._proximo_id_cliente, motivo)
        return c

    def _rnd(self):
        return random.random()

    def _determinar_motivo(self, rnd):
        p = self.p
        if rnd < p.prob_comprar:
            return ent.COMPRAR
        if rnd < p.prob_comprar + p.prob_entregar:
            return ent.ENTREGAR
        return ent.RETIRAR

    def _proximo_evento(self):
        """Devuelve (nombre, tiempo) del evento con menor tiempo en la FEL."""
        mejor_nombre = None
        mejor_tiempo = math.inf
        for nombre, t in self.fel.items():
            if t is not None and t < mejor_tiempo:
                mejor_tiempo = t
                mejor_nombre = nombre
        return mejor_nombre, mejor_tiempo

    # ------------------------------------------------------------------
    # Atencion del ayudante
    # ------------------------------------------------------------------
    def _iniciar_servicio(self, cliente, row):
        """Inicia la atencion de un cliente que tiene reloj/compra/entrega.

        No reinicia inicio_ocupacion: este se fija solo en Libre->Ocupado.
        """
        cliente.estado = ent.SIENDO_ATENDIDO
        self.ayudante.cliente_actual = cliente
        self.ayudante.estado = ent.OCUPADO

        if cliente.motivo == ent.COMPRAR:
            rnd = self._rnd()
            dur = self.p.C + rnd * (self.p.D - self.p.C)
            self.fel[EV_FIN_VENTA] = self.reloj + dur
            row["rnd_venta"] = rnd
            row["dur_venta"] = dur
        elif cliente.motivo == ent.ENTREGAR:
            self.fel[EV_FIN_ENTREGA] = self.reloj + 3.0
        elif cliente.motivo == ent.RETIRAR:
            # Siempre se atiende 3 min; el stock se verifica al fin_retiro.
            self.fel[EV_FIN_RETIRO] = self.reloj + 3.0

    def _atender_siguiente(self, row):
        """Tras finalizar una atencion, intenta atender al siguiente de la cola.

        Si la cola se vacia, el ayudante pasa a Libre y se acumula el tiempo
        ocupado.
        """
        if self.ayudante.cola:
            siguiente = self.ayudante.cola.pop(0)
            self._iniciar_servicio(siguiente, row)
            return
        # Nadie mas para atender
        self.ayudante.estado = ent.LIBRE
        self.acum_ocup_ayudante += self.reloj - self.ayudante.inicio_ocupacion
        self.ayudante.inicio_ocupacion = None
        self.ayudante.cliente_actual = None

    # ------------------------------------------------------------------
    # Flujo del relojero
    # ------------------------------------------------------------------
    def _iniciar_reparacion(self, row):
        """El relojero toma un reloj de la cola y comienza a repararlo."""
        self.relojero.cola_a_reparar -= 1
        self.relojero.estado = ent.OCUPADO
        self.relojero.inicio_ocupacion = self.reloj
        rnd = self._rnd()
        dur = self.p.E + rnd * (self.p.F - self.p.E)
        self.fel[EV_FIN_REPARACION] = self.reloj + dur
        row["rnd_reparacion"] = rnd
        row["dur_reparacion"] = dur

    # ------------------------------------------------------------------
    # Procesamiento de cada evento
    # ------------------------------------------------------------------
    def _ev_llegada(self, row):
        p = self.p
        # Programar proxima llegada
        rnd_ll = self._rnd()
        t_ll = p.A + rnd_ll * (p.B - p.A)
        self.fel[EV_LLEGADA] = self.reloj + t_ll
        row["rnd_llegada"] = rnd_ll
        row["t_llegada"] = t_ll

        # Determinar motivo
        rnd_m = self._rnd()
        motivo = self._determinar_motivo(rnd_m)
        row["rnd_motivo"] = rnd_m
        row["motivo"] = motivo

        cliente = self._nuevo_cliente(motivo)

        if self.ayudante.estado == ent.LIBRE:
            self.ayudante.inicio_ocupacion = self.reloj
            self.clientes_activos.append(cliente)
            self._iniciar_servicio(cliente, row)
        else:
            # Ayudante ocupado: el cliente espera en la cola
            self.clientes_activos.append(cliente)
            self.ayudante.cola.append(cliente)

    def _ev_fin_venta(self, row):
        self.fel[EV_FIN_VENTA] = None
        self._cliente_saliente = self.ayudante.cliente_actual
        if self._cliente_saliente in self.clientes_activos:
            self.clientes_activos.remove(self._cliente_saliente)
        self._atender_siguiente(row)

    def _ev_fin_retiro(self, row):
        self.fel[EV_FIN_RETIRO] = None
        # Se contabiliza el retiro al finalizar (consistente con la estadistica)
        self.acum_total_retiros += 1
        # Recien aqui se verifica si habia un reloj listo para retirar
        if self.relojero.cola_listos_retirar > 0:
            self.relojero.cola_listos_retirar -= 1
        else:
            # No habia reloj disponible para este retiro
            self.acum_no_reloj += 1
        self._cliente_saliente = self.ayudante.cliente_actual
        if self._cliente_saliente in self.clientes_activos:
            self.clientes_activos.remove(self._cliente_saliente)
        self._atender_siguiente(row)

    def _ev_fin_entrega(self, row):
        self.fel[EV_FIN_ENTREGA] = None
        # El reloj entregado entra a la cola de reparacion
        self.relojero.cola_a_reparar += 1
        # Si el relojero esta libre, comienza la reparacion
        if self.relojero.estado == ent.LIBRE:
            self._iniciar_reparacion(row)
        self._cliente_saliente = self.ayudante.cliente_actual
        if self._cliente_saliente in self.clientes_activos:
            self.clientes_activos.remove(self._cliente_saliente)
        self._atender_siguiente(row)

    def _ev_fin_reparacion(self, row):
        self.fel[EV_FIN_REPARACION] = None
        # El reloj reparado pasa a la cola de listos para retirar
        self.relojero.cola_listos_retirar += 1
        # Acumular tiempo ocupado (la reparacion termino)
        self.acum_ocup_relojero += self.reloj - self.relojero.inicio_ocupacion
        self.relojero.inicio_ocupacion = None

        # Determinar si toma refrigerio
        rnd_dec = self._rnd()
        row["rnd_refrig"] = rnd_dec
        if rnd_dec < self.p.prob_refrigerio:
            row["toma_refrig"] = "Toma refrigerio"
            rnd_tipo = self._rnd()
            row["rnd_tipo"] = rnd_tipo
            if rnd_tipo < 0.5:
                tipo = ent.REFRESCO
                c_act = ent.C_REFRESCO
            else:
                tipo = ent.CAFE
                c_act = ent.C_CAFE
            r = self.relojero.cola_a_reparar
            dur, historial = integrar_refrigerio(c_act, self.p.a, r, self.p.h)
            self.relojero.estado = ent.TOMANDO_REFRIGERIO
            self.relojero.tipo_refrigerio_actual = tipo
            self.fel[EV_FIN_REFRIGERIO] = self.reloj + dur
            row["tipo_refrig"] = "Refresco" if tipo == ent.REFRESCO else "Cafe"
            row["dur_refrig"] = dur
            # El detalle de Euler se registra solo si la fila llega a guardarse
            # (ver _registrar_euler), para no acumular iteraciones descartadas.
            row["_euler_pendiente"] = {
                "tipo": row["tipo_refrig"],
                "reloj": self.reloj,
                "iteracion": self.iteracion,
                "R": r,
                "c_act": c_act,
                "duracion": dur,
                "historial": historial,
            }
        else:
            row["toma_refrig"] = "No toma"
            # No toma refrigerio
            if self.relojero.cola_a_reparar > 0:
                self._iniciar_reparacion(row)
            else:
                self.relojero.estado = ent.LIBRE

    def _ev_fin_refrigerio(self, row):
        self.fel[EV_FIN_REFRIGERIO] = None
        # Contar cafes (solo tipo cafe, segun especificacion textual)
        if self.relojero.tipo_refrigerio_actual == ent.CAFE:
            self.acum_cafes += 1
        self.relojero.tipo_refrigerio_actual = None
        # Continuar reparando si hay relojes pendientes
        if self.relojero.cola_a_reparar > 0:
            self._iniciar_reparacion(row)
        else:
            self.relojero.estado = ent.LIBRE

    # ------------------------------------------------------------------
    # Construccion de filas del vector de estado
    # ------------------------------------------------------------------
    def _base_row(self, nro, evento):
        return {
            "nro": nro,
            "evento": evento,
            "reloj": self.reloj,
            "rnd_llegada": None, "t_llegada": None,
            "rnd_motivo": None, "motivo": None,
            "rnd_venta": None, "dur_venta": None,
            "rnd_reparacion": None, "dur_reparacion": None,
            "rnd_refrig": None, "toma_refrig": None,
            "rnd_tipo": None, "tipo_refrig": None, "dur_refrig": None,
            "euler_idx": None,
        }

    def _completar_row(self, row, mostrar_clientes=True):
        # Snapshot de la FEL
        row["prox_llegada"] = self.fel[EV_LLEGADA]
        row["fin_venta"] = self.fel[EV_FIN_VENTA]
        row["fin_retiro"] = self.fel[EV_FIN_RETIRO]
        row["fin_entrega"] = self.fel[EV_FIN_ENTREGA]
        row["fin_reparacion"] = self.fel[EV_FIN_REPARACION]
        row["fin_refrigerio"] = self.fel[EV_FIN_REFRIGERIO]

        # Estado del ayudante
        row["ay_estado"] = self.ayudante.estado
        row["ay_cola"] = len(self.ayudante.cola)
        row["ay_inicio"] = (self.ayudante.inicio_ocupacion
                            if self.ayudante.estado == ent.OCUPADO else None)

        # Estado del relojero
        row["rel_estado"] = self.relojero.estado
        row["rel_cola_reparar"] = self.relojero.cola_a_reparar
        row["rel_listos"] = self.relojero.cola_listos_retirar
        row["rel_inicio"] = (self.relojero.inicio_ocupacion
                             if self.relojero.estado == ent.OCUPADO else None)

        # Estadisticas
        row["acum_total_retiros"] = self.acum_total_retiros
        row["acum_no_reloj"] = self.acum_no_reloj
        row["prob_no_reloj"] = (self.acum_no_reloj / self.acum_total_retiros * 100
                                if self.acum_total_retiros > 0 else 0.0)
        row["acum_ocup_ay"] = self.acum_ocup_ayudante
        row["porc_ocup_ay"] = (self.acum_ocup_ayudante / self.reloj * 100
                               if self.reloj > 0 else 0.0)
        row["acum_ocup_rel"] = self.acum_ocup_relojero
        row["porc_ocup_rel"] = (self.acum_ocup_relojero / self.reloj * 100
                                if self.reloj > 0 else 0.0)
        row["acum_dias"] = math.ceil(self.reloj / 1440.0) if self.reloj > 0 else 0
        row["acum_cafes"] = self.acum_cafes
        row["prom_cafes"] = (self.acum_cafes / (self.reloj / 1440.0)
                             if self.reloj > 0 else 0.0)

        # Clientes (objetos temporales)
        clientes = {}
        if mostrar_clientes:
            for c in self.clientes_activos:
                # El motivo solo se arrastra mientras el cliente espera atencion (EA)
                motivo_visible = c.motivo if c.estado == ent.ESPERANDO_ATENCION else ""
                clientes[c.id] = (c.estado, motivo_visible)
            if self._cliente_saliente is not None:
                clientes[self._cliente_saliente.id] = ("-", "-")
        row["clientes"] = clientes

    # ------------------------------------------------------------------
    # Persistencia de la ventana a mostrar
    # ------------------------------------------------------------------
    def _ventana_abierta(self):
        """True si la fila actual debe guardarse: dentro de [j, j+i iteraciones)."""
        return self.reloj >= self.p.j and self._guardadas < self.p.i

    def _registrar_euler(self, row):
        """Si la fila tiene un refrigerio pendiente, lo agrega a euler_detalles."""
        pendiente = row.pop("_euler_pendiente", None)
        if pendiente is None:
            return
        pendiente["numero"] = len(self.euler_detalles) + 1
        row["euler_idx"] = len(self.euler_detalles)
        self.euler_detalles.append(pendiente)

    def _quizas_guardar(self, row):
        """Persiste la fila solo si esta dentro de la ventana a mostrar.

        Las filas fuera de la ventana se descartan (junto con su eventual
        detalle de Euler), de modo que nunca se acumulan en memoria.
        """
        if not self._ventana_abierta():
            return
        self._guardadas += 1
        self._completar_row(row)
        self._registrar_euler(row)
        self.filas.append(row)

    # ------------------------------------------------------------------
    # Bucle principal
    # ------------------------------------------------------------------
    def ejecutar(self):
        # Fila 0: Inicializacion
        self.reloj = 0.0
        rnd_ll = self._rnd()
        t_ll = self.p.A + rnd_ll * (self.p.B - self.p.A)
        self.fel[EV_LLEGADA] = t_ll

        row0 = self._base_row(0, "Inicializacion")
        row0["rnd_llegada"] = rnd_ll
        row0["t_llegada"] = t_ll
        self._quizas_guardar(row0)

        self.iteracion = 0
        while self.iteracion < self.p.max_iteraciones:
            nombre, tiempo = self._proximo_evento()
            if nombre is None or tiempo > self.p.X:
                break

            self.reloj = tiempo
            self.iteracion += 1
            self._cliente_saliente = None

            row = self._base_row(self.iteracion, nombre)

            if nombre == EV_LLEGADA:
                self._ev_llegada(row)
            elif nombre == EV_FIN_VENTA:
                self._ev_fin_venta(row)
            elif nombre == EV_FIN_RETIRO:
                self._ev_fin_retiro(row)
            elif nombre == EV_FIN_ENTREGA:
                self._ev_fin_entrega(row)
            elif nombre == EV_FIN_REPARACION:
                self._ev_fin_reparacion(row)
            elif nombre == EV_FIN_REFRIGERIO:
                self._ev_fin_refrigerio(row)

            # Solo se guarda la ventana a mostrar; el resto se simula y descarta.
            self._quizas_guardar(row)

        # Fila final en el instante X (estado del sistema, sin objetos temporales)
        self._fila_final()

        return self.filas

    def _fila_final(self):
        self.reloj = self.p.X
        self._cliente_saliente = None

        # Cerrar ocupaciones en curso para estadisticas finales correctas
        if self.ayudante.estado == ent.OCUPADO and self.ayudante.inicio_ocupacion is not None:
            self.acum_ocup_ayudante += self.p.X - self.ayudante.inicio_ocupacion
            self.ayudante.inicio_ocupacion = None
        if self.relojero.estado == ent.OCUPADO and self.relojero.inicio_ocupacion is not None:
            self.acum_ocup_relojero += self.p.X - self.relojero.inicio_ocupacion
            self.relojero.inicio_ocupacion = None

        row = self._base_row(self.iteracion + 1, "Fin simulacion (X)")
        self._completar_row(row, mostrar_clientes=False)
        self.filas.append(row)

    # ------------------------------------------------------------------
    # Estadisticas finales
    # ------------------------------------------------------------------
    def estadisticas(self):
        x = self.p.X
        prob_no_reloj = (self.acum_no_reloj / self.acum_total_retiros * 100
                         if self.acum_total_retiros > 0 else 0.0)
        porc_ay = self.acum_ocup_ayudante / x * 100 if x > 0 else 0.0
        porc_rel = self.acum_ocup_relojero / x * 100 if x > 0 else 0.0
        prom_cafes = self.acum_cafes / (x / 1440.0) if x > 0 else 0.0
        return {
            "prob_retiro_sin_reloj": prob_no_reloj,
            "porc_ocup_ayudante": porc_ay,
            "porc_ocup_relojero": porc_rel,
            "prom_cafes_dia": prom_cafes,
            "total_retiros": self.acum_total_retiros,
            "total_no_reloj": self.acum_no_reloj,
            "total_cafes": self.acum_cafes,
            "iteraciones": self.iteracion,
        }
