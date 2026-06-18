# Simulacion de Colas - Relojeria (PyQt5)

Simulacion por eventos discretos de un negocio de arreglo y venta de relojes,
con interfaz grafica en PyQt5.

## Instalacion

```bash
pip install -r requirements.txt
```

## Ejecucion

```bash
python main.py
```

## Estructura

- `main.py` - Punto de entrada.
- `entidades.py` - Objetos del sistema: `Cliente`, `Ayudante`, `Relojero` y constantes.
- `integracion_euler.py` - Metodo de Euler para la duracion del refrigerio.
- `simulacion.py` - Motor de eventos (`Simulacion`, `Parametros`), vector de estado y estadisticas.
- `interfaz/ventana_principal.py` - Ventana principal: formulario, controles, resultados y pestanas.
- `interfaz/tabla_vector.py` - Tabla del vector de estado (scroll H/V, headers fijos, copy a Excel, fuente monoespaciada).
- `test_validacion.py` - Verifica el motor contra la fila de ejemplo del enunciado.

## Uso

1. Cargar los parametros (X, i, j, A..F, probabilidades, `a`, `h`).
2. Pulsar **Simular**.
3. Ver el vector de estado (pestana *Vector de Estado*) y el detalle de cada
   refrigerio (pestana *Integracion Euler*, exportable a CSV).
4. Copiar la grilla con **Ctrl+C** sobre la seleccion o con *Copiar grilla completa*.

## Notas de implementacion

- El vector se filtra: filas con `reloj >= j`, hasta `i` filas, y siempre la fila final en `X`.
- RND generados con `random.random()` en `[0, 1)`.
- **Contador de cafes**: cuenta solo refrigerios de tipo *cafe* (segun la
  especificacion textual del enunciado). La tabla de ejemplo contaba todos los
  refrigerios; se opto por la regla textual explicita.
- El tiempo en refrigerio NO cuenta como ocupacion del relojero.
- Validado contra el ejemplo del enunciado (`python test_validacion.py` -> *OK*).
