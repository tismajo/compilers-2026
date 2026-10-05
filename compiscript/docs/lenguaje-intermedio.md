# Lenguaje intermedio: código de tres direcciones (TAC)

Este documento describe el código intermedio que genera el compilador de
Compiscript. Explica las instrucciones, el modelo de memoria, el reciclaje de
temporales y cómo se traduce cada construcción del lenguaje.

> **Estado:** avance (bloque A). Las construcciones de la sección
> [Pendientes](#9-pendientes) se emiten por ahora como `# TODO` para que cualquier
> programa válido produzca código sin fallar.

---

## 1. Cómo generarlo

```bash
./.venv/Scripts/python.exe program/Driver.py programa.cps --tac text
./.venv/Scripts/python.exe program/Driver.py programa.cps --tac text --symbols text
./.venv/Scripts/python.exe program/Driver.py programa.cps --format json --tac json --symbols json
```

- El TAC solo se genera si el programa pasó el análisis léxico, sintáctico y
  semántico sin errores. Con errores, el compilador imprime los diagnósticos,
  avisa `No se generó código intermedio` y termina con código de salida `1`.
- Con `--symbols`, la tabla de símbolos muestra las direcciones asignadas y los
  registros de activación (sección 4).
- Con `--format json`, la salida incluye el campo `tac`, que contiene
  `functions[]`. Cada función trae `label`, `frame` y `quads[]` con
  `op`, `arg1`, `arg2` y `result`. También incluye `text`, el TAC ya
  formateado.

## 2. Representación

Internamente, cada instrucción es un **cuádruplo** `(op, arg1, arg2, result)`
(`program/tac/instructions.py`). El código se agrupa por función:

```
main:                      ← etiqueta de la función
    begin_func 12          ← reserva el frame (bytes)
    ...
    end_func               ← retorno implícito
```

`main` contiene las sentencias de nivel superior y se imprime primero, porque
ahí empieza la ejecución. Las demás funciones se imprimen después, en el orden
en que terminan de generarse.

## 3. Catálogo de instrucciones

| Instrucción | Cuádruplo | Significado |
| --- | --- | --- |
| `x = y` | `(assign, y, -, x)` | Copia |
| `x = y op z` | `(op, y, z, x)` | `op` ∈ `+ - * / %` `== != < <= > >=` |
| `x = - y` | `(minus, y, -, x)` | Negación aritmética |
| `x = ! y` | `(not, y, -, x)` | Negación lógica |
| `x = itof y` | `(itof, y, -, x)` | Conversión `integer` → `float` |
| `x = tostr y` | `(tostr, y, -, x)` | Conversión a `string` para concatenar |
| `x = concat y, z` | `(concat, y, z, x)` | Concatenación de strings |
| `L:` | `(label, L, -, -)` | Etiqueta |
| `goto L` | `(goto, L, -, -)` | Salto incondicional |
| `ifFalse x goto L` | `(if_false, x, L, -)` | Salta si `x` es falso |
| `if x goto L` | `(if_true, x, L, -)` | Salta si `x` es verdadero |
| `param x` | `(param, x, -, -)` | Apila un argumento |
| `x = call f, n` | `(call, f, n, x)` | Llama a `f` con `n` argumentos; `x` recibe el retorno |
| `call f, n` | `(call, f, n, -)` | Llamada a función `void` |
| `return x` / `return` | `(return, x, -, -)` | Retorno |
| `print x` | `(print, x, -, -)` | Salida estándar |
| `begin_func n` / `end_func` | | Prólogo (reserva `n` bytes) y epílogo |
| `# TODO …` | `(todo, texto, -, x?)` | Construcción aún no traducida |

### Nombres

| Elemento | Forma | Ejemplo |
| --- | --- | --- |
| Temporal | `t0`, `t1`… (se reinician en cada función) | `t0 = a + b` |
| Etiqueta | `L0`, `L1`… (únicas en todo el programa) | `goto L3` |
| Función | `f_<nombre>`; anidada: `f_<externa>_<nombre>` | `f_factorial`, `f_outer_helper` |
| Método | `<Clase>_<método>` | `Animal_speak` |
| Variable | su nombre; si otra variable visible ya lo usa: `nombre#2`, `nombre#3`… | `x#2` |
| Variable llamada como un temporal o una etiqueta | sufijo `#v` | `t0#v` |

`#` no es válido en los identificadores de Compiscript, así que un nombre
generado nunca choca con uno del usuario.

## 4. Modelo de memoria y tabla de símbolos

`program/tac/layout.py` llena los campos que la tabla de símbolos tenía
reservados (`offset`, `size`, `storage`, `label`) y construye un **registro de
activación** por función.

### Tamaños

| Tipo | Bytes |
| --- | --- |
| `float` | 8 |
| `integer`, `boolean` | 4 |
| `string`, arreglos, objetos, funciones (referencias) | 4 |

### Dónde vive cada símbolo

| Símbolo | `storage` | `offset` |
| --- | --- | --- |
| Variable o constante global, incluidas las declaradas en bloques de `main` | `global` | Desde el inicio del segmento de datos |
| Parámetro | `stack` | Positivo desde `fp`: `fp+8`, `fp+12`… |
| Variable local | `stack` | Negativo desde `fp`: `fp-4`, `fp-8`… |
| Atributo | `heap` | Dentro del objeto, desde 4 |
| Función o método | `code` | — (`label` = etiqueta de su código) |
| Clase | `heap` | — (`size` = tamaño del objeto) |

### Registro de activación

```
        direcciones altas
   ┌──────────────────────┐
   │ parámetro n          │  fp+8+…
   │ …                    │
   │ parámetro 1 / this   │  fp+8
   ├──────────────────────┤
   │ dirección de retorno │  fp+4
   │ enlace de control    │  fp+0   ← fp (fp del llamador)
   ├──────────────────────┤
   │ local 1              │  fp-4
   │ …                    │
   │ temporales           │
   └──────────────────────┘
        direcciones bajas
```

- `frameSize = 8 (encabezado) + tamaño de locales + 4 × temporales`. Este es
  el valor de `begin_func`.
- El llamador apila los parámetros (`param`). El llamado reserva el resto.
- En los métodos, `this` es el primer parámetro (`fp+8`).
- Si una variable de un bloque interno ocultaba a otra del mismo nombre,
  recibe su propio espacio. Los espacios no se comparten entre bloques.
- El registro también exporta `captured`, la lista de variables de funciones
  externas que necesita un closure.

Ejemplo (`--symbols text`):

```
  [function] global.f
    - parameter a: integer (3:12) [stack fp+8, 4B]
    - parameter b: float (3:24) [stack fp+12, 8B]
    - variable x: integer (4:7) [stack fp-4, 4B]
...
frame f_f (function) — 20 bytes
  param a: fp+8 (4B)
  param b: fp+12 (8B)
  local x: fp-4 (4B)
  local x: fp-8 (4B)
  temps: 1 × 4B
```

### Objetos

El byte 0 de cada objeto guarda un puntero al descriptor de su clase. Los
atributos van a continuación, y los heredados primero. Así una subclase
conserva los offsets de su clase padre. Para `class A { let x: integer; }` y
`class B : A { let y: float; }`, `x` queda en `obj+4` y `y` en `obj+8`. `A`
ocupa 8 bytes y `B` 16.

## 5. Asignación y reciclaje de temporales

`program/tac/temps.py` implementa `TempAllocator`:

1. `new()` toma el último temporal liberado (pool LIFO). Si el pool está
   vacío, crea `t<n>`.
2. Una instrucción **libera sus operandos temporales antes de pedir el
   temporal de su resultado**. Por eso el resultado reutiliza uno de ellos.
3. Las variables con nombre nunca se liberan.
4. Cada función registra su **pico** de temporales vivos. Ese pico define
   cuánto espacio para temporales reserva el frame.

```
r = a + b * c - d          r = (a + b) * (c - d)
    t0 = b * c                 t0 = a + b
    t0 = a + t0                t1 = c - d
    t0 = t0 - d                t1 = t0 * t1
    r = t0                     r = t1
    pico: 1 temporal           pico: 2 temporales
```

## 6. Traducción por construcción

### Expresiones

- **Aritmética:** de izquierda a derecha, respetando la precedencia de la
  gramática. Si se mezcla `integer` con `float`, el lado entero se convierte con
  `itof` y el resultado es `float`.
- **Concatenación:** si un operando de `+` es `string`, el otro se convierte
  con `tostr` y se emite `concat`.
- **Asignación a `float`:** un valor entero que se guarda en una variable,
  parámetro o retorno de tipo `float` pasa por `itof`.
- **`&&` / `||`:** usan cortocircuito. El operando derecho solo se evalúa si
  hace falta.

```
ok = a < b && c < d            m = a > b ? a : b
    t0 = a < b                     t0 = a > b
    ifFalse t0 goto L0             ifFalse t0 goto L0
    t1 = c < d                     t0 = a
    t0 = t1                        goto L1
L0:                            L0:
    ok = t0                        t0 = b
                               L1:
                                   m = t0
```

### Declaraciones

- Con inicializador: `x = <valor>`.
- Sin inicializador, la variable recibe el valor cero de su tipo: `0`, `0.0`,
  `false` o `""`. Para referencias es `null`.

### Control de flujo

```
if (c) A else B         while (c) S             do S while (c)         for (I; c; P) S
    t = c                L0:                     L0:                     I
    ifFalse t goto L0        t = c                   S                   L0:
    A                        ifFalse t goto L1   L1:   ← continue            t = c
    goto L1                  S                       t = c                   ifFalse t goto L2
L0:                          goto L0                 if t goto L0            S
    B                    L1:   ← break           L2:   ← break           L1:   ← continue
L1:                                                                          P
                                                                             goto L0
                                                                         L2:   ← break
```

`break` y `continue` saltan a las etiquetas del ciclo más interno. Cada función
mantiene su propia pila de etiquetas de ciclo.

### Funciones

Primero se evalúan **todos** los argumentos y después se emiten los `param`.
Así, una llamada anidada como argumento nunca mezcla sus parámetros con los de
la llamada externa.

```
function factorial(n: integer): integer {     f_factorial:
  if (n <= 1) { return 1; }                       begin_func 12
  return n * factorial(n - 1);                    t0 = n <= 1
}                                                 ifFalse t0 goto L0
print(factorial(5));                              return 1
                                              L0:
main:                                             t0 = n - 1
    begin_func 12                                 param t0
    param 5                                       t0 = call f_factorial, 1
    t0 = call f_factorial, 1                      t0 = n * t0
    print t0                                      return t0
    end_func                                      end_func
```

Las funciones anidadas se generan como funciones aparte, con su propia
etiqueta (`f_outer_helper`).

## 7. Supuestos

1. La entrada ya pasó el análisis semántico. El generador no vuelve a validar
   tipos ni a resolver nombres: usa el símbolo y el tipo que el checker
   registró para cada nodo (`bindings`, `declared`, `type_objects`).
2. Las condiciones se evalúan a un temporal booleano y luego se salta con
   `ifFalse` o `if`. No se generan saltos directos sobre cada operador
   relacional.
3. Las variables declaradas en bloques de nivel superior (por ejemplo, el `i`
   de un `for` en `main`) son globales, porque `main` no tiene variables
   locales en pila.
4. Los temporales ocupan una palabra (4 bytes) en el frame.
5. `print` acepta cualquier valor imprimible. La conversión a texto queda a
   cargo de la fase de código objeto.
6. Leer una variable global desde una función no cuenta como captura de closure,
   porque las globales tienen dirección estática.

## 8. Arquitectura del módulo

```
Driver.analyze_file ─► semantic.analyze ─► SemanticResult (symbols, bindings, declared, type_objects)
                                                     │
AnalysisResult.generate_tac ─► tac.generate ─► layout.assign_addresses (direcciones + frames)
                                             └► TacGenerator (visitor del parse tree) ─► TacProgram
```

| Archivo | Contenido |
| --- | --- |
| `program/tac/instructions.py` | `Quad`, `FunctionCode`, `TacProgram` (formato texto y JSON) |
| `program/tac/temps.py` | `TempAllocator`: asignación y reciclaje de temporales |
| `program/tac/layout.py` | Tamaños, direcciones, `ActivationRecord`, layout de objetos |
| `program/tac/generator.py` | `TacGenerator`: traducción construcción por construcción |
| `program/tac/__init__.py` | `generate(tree, semantic)` |

Pruebas: `tests/codegen/` (expresiones y temporales, control de flujo,
funciones y frames, casos fallidos).

## 9. Pendientes

Estas construcciones se emiten hoy como `# TODO` y se traducen en la siguiente
entrega:

- arreglos: literal, lectura y escritura indexada
- `foreach`, `switch` y `try/catch`
- clases: `new`, constructor, `this`, atributos, métodos y sobrescritura
- closures: funciones anidadas que capturan variables de una función externa
