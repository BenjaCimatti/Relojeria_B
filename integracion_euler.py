"""Integracion numerica por el metodo de Euler para la duracion del refrigerio.

EDO:  dD/dt = 0.4 * C_act + t + a * R

Donde:
    C_act = valor objetivo de la actividad (50 refresco / 80 cafe)
    t     = tiempo local desde el inicio del refrigerio (empieza en 0)
    a     = constante de apuro (parametrizable)
    R     = relojes en la cola a reparar al inicio del refrigerio (constante)

Se integra desde D=0 hasta D >= C_act. La duracion del refrigerio es el
valor de t_local alcanzado.
"""


def integrar_refrigerio(c_act, a, r, h=0.1):
    """Resuelve la EDO por Euler.

    Devuelve una tupla (duracion, historial) donde:
        duracion  = t_local final (cuando D >= C_act)
        historial = lista de filas dict con claves 't', 'D', 'dD' (la derivada
                    evaluada en cada paso, antes de avanzar).
    """
    D = 0.0
    t_local = 0.0
    historial = [{"t": t_local, "D": D, "dD": None}]

    # Salvaguarda contra bucles infinitos (no deberia alcanzarse).
    max_pasos = 10_000_000
    pasos = 0

    while D < c_act and pasos < max_pasos:
        dD = 0.4 * c_act + t_local + a * r
        D = D + h * dD
        t_local = t_local + h
        historial.append({"t": t_local, "D": D, "dD": dD})
        pasos += 1

    return t_local, historial
