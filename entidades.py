"""Entidades del sistema de simulacion de la relojeria.

Contiene los objetos permanentes (Ayudante, Relojero) y temporales (Cliente),
ademas de las constantes de estados y motivos.
"""

# --- Constantes de estado ---
LIBRE = "Libre"
OCUPADO = "Ocupado"
TOMANDO_REFRIGERIO = "Tomando Refrigerio"

# --- Estados del cliente ---
ESPERANDO_ATENCION = "EA"   # Esperando Atencion
SIENDO_ATENDIDO = "SA"      # Siendo Atendido

# --- Motivos de visita ---
COMPRAR = "Comprar"
ENTREGAR = "Entregar"
RETIRAR = "Retirar"

# --- Tipos de refrigerio ---
REFRESCO = "Refresco"
CAFE = "Cafe"
C_REFRESCO = 50
C_CAFE = 80


class Cliente:
    """Objeto temporal. Representa un cliente dentro del sistema."""

    def __init__(self, id_cliente, motivo):
        self.id = id_cliente
        self.motivo = motivo
        self.estado = ESPERANDO_ATENCION

    def __repr__(self):
        return f"Cliente({self.id}, {self.motivo}, {self.estado})"


class Ayudante:
    """Objeto permanente. Atiende a los clientes que llegan."""

    def __init__(self):
        self.estado = LIBRE
        self.cola = []              # clientes esperando atencion (Cliente)
        self.cliente_actual = None  # cliente siendo atendido
        self.inicio_ocupacion = None  # instante en que paso de Libre a Ocupado


class Relojero:
    """Objeto permanente. Repara relojes y eventualmente toma un refrigerio."""

    def __init__(self, listos_iniciales=3):
        self.estado = LIBRE
        self.cola_a_reparar = 0                 # relojes pendientes de reparacion
        self.cola_listos_retirar = listos_iniciales  # relojes reparados (inicial = 3)
        self.inicio_ocupacion = None            # instante Libre/Refrigerio -> Ocupado
        self.tipo_refrigerio_actual = None      # tipo del refrigerio en curso
