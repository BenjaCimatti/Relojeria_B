"""Valida el motor de simulacion contra la fila de ejemplo del enunciado.

Inyecta la secuencia exacta de RND del ejemplo y verifica eventos, tiempos,
colas y estadisticas clave de las filas 0..12.
"""

import random

import simulacion as S
from simulacion import Simulacion, Parametros

# Secuencia de RND consumida en el orden del ejemplo.
SEQ = [0.3, 0.72, 0.51, 0.87, 0.5, 0.7, 0.02, 0.4,
       0.82, 0.69, 0.01, 0.45, 0.3, 0.6, 0.06, 0.7]


def main():
    it = iter(SEQ)
    random.random = lambda: next(it)

    p = Parametros(X=70.0, a=1.0, h=0.1)
    sim = Simulacion(p)
    sim.ejecutar()

    # Imprimir filas relevantes
    cols = ["nro", "evento", "reloj", "motivo", "fin_entrega", "fin_retiro",
            "fin_venta", "fin_reparacion", "fin_refrigerio", "dur_refrig",
            "tipo_refrig", "ay_estado", "rel_estado", "rel_cola_reparar",
            "rel_listos", "acum_total_retiros", "acum_no_reloj",
            "acum_ocup_ay", "acum_ocup_rel", "acum_cafes"]

    def g(f, k):
        v = f.get(k)
        if isinstance(v, float):
            return round(v, 2)
        return v

    for f in sim.filas:
        print(f["nro"], f["evento"], "reloj=", g(f, "reloj"),
              "motivo=", f.get("motivo"),
              "ay=", f.get("ay_estado"), "rel=", f.get("rel_estado"),
              "colaRep=", f.get("rel_cola_reparar"), "listos=", f.get("rel_listos"),
              "durRef=", g(f, "dur_refrig"), f.get("tipo_refrig"),
              "totRet=", f.get("acum_total_retiros"),
              "ocupAy=", g(f, "acum_ocup_ay"), "ocupRel=", g(f, "acum_ocup_rel"),
              "cafes=", f.get("acum_cafes"))

    # Asserts contra el ejemplo (filas 0..12, antes de la fila final X)
    filas = sim.filas
    esperado = {
        0: dict(evento="Inicializacion", reloj=0, rel_listos=3),
        1: dict(evento="llegada_cliente", reloj=14.2, motivo="Entregar"),
        2: dict(evento="fin_entrega", reloj=17.2, rel_estado="Ocupado", acum_ocup_ay=3.0),
        3: dict(evento="llegada_cliente", reloj=30.08, motivo="Retirar", acum_total_retiros=1, rel_listos=3),
        4: dict(evento="fin_retiro", reloj=33.08, rel_listos=2, acum_ocup_ay=6.0),
        5: dict(evento="fin_reparacion", reloj=38.68, dur_refrig=2.4, tipo_refrig="Refresco", acum_ocup_rel=21.48),
        6: dict(evento="fin_refrigerio", reloj=41.08, rel_estado="Libre", acum_cafes=0),
        7: dict(evento="llegada_cliente", reloj=45.08, motivo="Entregar"),
        8: dict(evento="fin_entrega", reloj=48.08, rel_estado="Ocupado", acum_ocup_ay=9.0),
        9: dict(evento="llegada_cliente", reloj=61.36, motivo="Comprar"),
        10: dict(evento="fin_reparacion", reloj=66.12, dur_refrig=2.5, tipo_refrig="Cafe", rel_listos=4),
        11: dict(evento="fin_refrigerio", reloj=68.62, rel_estado="Libre", acum_cafes=1),
        12: dict(evento="fin_venta", reloj=69.76),
    }

    ok = True
    for f in filas:
        n = f["nro"]
        if n in esperado:
            for k, v in esperado[n].items():
                real = f.get(k)
                if isinstance(v, float) or isinstance(real, float):
                    coincide = abs(float(real) - float(v)) < 0.01
                else:
                    coincide = real == v
                if not coincide:
                    ok = False
                    print(f"  [FALLA] fila {n} {k}: esperado {v} != real {real}")

    print("\nRESULTADO:", "OK - coincide con el ejemplo" if ok else "HAY DIFERENCIAS")


if __name__ == "__main__":
    main()
