# Lenguaje intermedio: código de tres direcciones (TAC)

Este documento describe el código intermedio que genera el compilador de
Compiscript. Explica las instrucciones, el modelo de memoria, el reciclaje de
temporales y cómo se traduce cada construcción del lenguaje.

> **Estado:** completo (bloques A y B). `program.cps`, el programa oficial,
> traduce sin emitir ningún `# TODO`. La sección [Fuera de alcance](#10-fuera-de-alcance)
> documenta lo que se decidió no modelar y por qué.

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
  `op`, `arg1`, `arg2` y `result`. También incluye `vtables[]` (sección 4.3) y
  `text`, el TAC ya formateado.

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
| `x = calli p, n` | `(calli, p, n, x)` | Llamada **indirecta**: `p` es un valor en tiempo de ejecución (una entrada de vtable), no una etiqueta estática |
| `x = alloc n` | `(alloc, n, -, x)` | Reserva `n` bytes en el heap; `x` recibe la dirección base |
| `x = *(b + o)` | `(load, b, o, x)` | Carga la palabra en el byte `o` de la dirección `b` |
| `*(b + o) = x` | `(store, b, o, x)` | Escribe `x` en el byte `o` de la dirección `b` |
| `halt` | `(halt, -, -, -)` | Termina el programa: un fallo en tiempo de ejecución sin manejador activo |
| `return x` / `return` | `(return, x, -, -)` | Retorno |
| `print x` | `(print, x, -, -)` | Salida estándar |
| `begin_func n` / `end_func` | | Prólogo (reserva `n` bytes) y epílogo |
| `# TODO …` | `(todo, texto, -, x?)` | Construcción aún no traducida (hoy, ninguna) |

`load`/`store` **no** son el `a[i]` del código fuente: son acceso crudo a
memoria por desplazamiento en bytes desde una dirección base. Por eso se
imprimen como `*(base + offset)` y no como `base[offset]` — esa notación se
reserva para que un lector no confunda, por ejemplo, `*(numbers + 0)` (leer el
encabezado de longitud de un arreglo) con "el primer elemento de `numbers`"
(que en realidad vive en `*(numbers + 4)`, después del encabezado). El
`offset` real de un acceso `a[i]` del usuario siempre se calcula primero con
aritmética explícita (`idx * stride + encabezado`) antes del `load`/`store`;
ver sección 4.2.

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

### 4.1 Arreglos

Un arreglo es un bloque del heap con la forma `[length][elem0][elem1]...`: el
primer word (4 bytes, `ARRAY_HEADER`) guarda la cantidad de elementos, y los
elementos empiezan justo después. Un arreglo de arreglos (una matriz) guarda
**punteros** en cada elemento, no los datos de la fila — el elemento de un
`integer[][]` es un `integer[]`, que `size_of` ya trata como una referencia de
una palabra, igual que cualquier otro tipo no primitivo.

```
let m: integer[][] = [[1, 2], [3, 4]];

t0 = alloc 12        ← arreglo externo: encabezado + 2 punteros
*(t0 + 0) = 2
t1 = alloc 12         ← primera fila
*(t1 + 0) = 2
*(t1 + 4) = 1
*(t1 + 8) = 2
*(t0 + 4) = t1         ← el elemento 0 del externo es un puntero a la fila
t1 = alloc 12
*(t1 + 0) = 2
*(t1 + 4) = 3
*(t1 + 8) = 4
*(t0 + 8) = t1
m = t0
```

### 4.2 Acceso indexado y chequeo de límites

El `[i]` del código fuente nunca se traduce directamente a un `load`/`store`:
primero se calcula el desplazamiento real en bytes, y antes de eso se valida
que `i` esté dentro del arreglo. Esta es la única comprobación en tiempo de
ejecución que genera el compilador (ver sección 7, supuesto 7). El patrón es
siempre el mismo, para lectura o escritura:

```
t_len = *(base + 0)              ← longitud, guardada en el encabezado
t_cmp = idx >= t_len
if t_cmp goto L_fail
goto L_ok
L_fail:
    <variable del catch activo> = "Índice fuera de rango"
    goto <etiqueta del catch activo, o 'halt' si no hay ninguno>
L_ok:
t_off = idx * stride              ← stride = size_of(tipo del elemento)
t_off2 = t_off + 4                 ← 4 = ARRAY_HEADER, para saltar el encabezado
resultado = *(base + t_off2)       ← o, para escritura: *(base + t_off2) = valor
```

`fail()` (`program/tac/generator.py`) es la única función que decide a dónde
salta un fallo: al manejador de `try/catch` más interno que esté activo
(sección 6.4) o, si no hay ninguno, a `halt`. Nada más en el generador conoce
ese salto; cualquier operación fallible futura (por ejemplo, división por
cero) reutilizaría la misma función.

### 4.3 Objetos

El byte 0 de cada objeto guarda el **descriptor de clase**: un puntero a la
vtable de la clase con la que se creó el objeto (sección 4.4), no a su propio
código. Los atributos van a continuación, y los heredados primero, así una
subclase conserva los offsets de su clase padre. Para `class A { let x: integer; }`
y `class B : A { let y: float; }`, `x` queda en `obj+4` y `y` en `obj+8`. `A`
ocupa 8 bytes y `B` 16.

### 4.4 Tablas de métodos virtuales (vtable)

Cada clase tiene una vtable: una lista de etiquetas de método, una por cada
nombre de método visible en la clase. `program/tac/layout.py` la construye
recursivamente — la de una clase empieza como una copia de la de su padre, y
luego:

- si la clase **sobrescribe** un método heredado, su etiqueta **reemplaza** la
  del padre en el mismo índice (así el índice de un nombre de método es el
  mismo en toda la jerarquía, que es justamente lo que permite el despacho
  dinámico);
- si declara un método **nuevo**, se agrega al final.

El constructor nunca entra a la vtable: siempre se llama de forma estática
(`call NombreClase_constructor, n`), porque no tiene sentido despachar
dinámicamente la construcción de un objeto.

```
class Animal { function eat()... function speak()... }
class Dog : Animal { function speak()... function fetch()... }

vtable Animal_vtable: [Animal_eat, Animal_speak]
vtable Dog_vtable:    [Animal_eat, Dog_speak,  Dog_fetch]
                         ↑ heredado   ↑ sobrescrito  ↑ nuevo
```

`new Dog(...)` reserva el objeto y guarda `Dog_vtable` en el byte 0:

```
t0 = alloc 8
*(t0 + 0) = Dog_vtable
param t0
param "Rex"
call Animal_constructor, 2   ← Dog no tiene constructor propio: hereda el de Animal
```

Una llamada `obj.metodo(args)` nunca usa el nombre de la clase estática de
`obj` para decidir a qué código saltar — carga la vtable *real* del objeto en
tiempo de ejecución y de ahí el puntero al método, y llama a través de ese
puntero con `calli`. Por eso `let a: Animal = new Dog(...); a.speak();`
ejecuta `Dog_speak`, no `Animal_speak`, aunque `a` esté declarada `Animal`:

```
t0 = *(a + 0)        ← vtable real del objeto (Dog_vtable, no Animal_vtable)
t1 = *(t0 + 0)        ← slot 0 de esa vtable = Dog_speak
param a
t1 = calli t1, 1
```

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

### `foreach`

Se traduce a un ciclo por índice sobre las mismas primitivas de arreglo de la
sección 4.1–4.2: longitud, chequeo de límites y acceso por `stride`. El índice
es un temporal que simplemente no se libera mientras el ciclo esté activo —no
una variable con su propio slot en el frame, porque `Layout` ya corrió para
cuando el generador necesita el índice y no hay dónde reservarle uno nuevo.
Es seguro: `TempAllocator` nunca reasigna un temporal que sigue vivo.

```
foreach (n in nums) { ... }

idx = 0
t_len = *(nums + 0)            ← se lee una sola vez, antes del ciclo
L_check:
    t_cmp = idx >= t_len
    if t_cmp goto L_end
    t_off = idx * stride + 4
    n = *(nums + t_off)
    ...
L_cont:
    idx = idx + 1
    goto L_check
L_end:
```

### `switch`

Cada `case` recibe su propia etiqueta de cuerpo, y los cuerpos se emiten uno
detrás de otro — así, "caer" de un cuerpo al siguiente cuando no hay `break`
(estilo C) es automático, no algo que el generador tenga que construir con
saltos extra. `break` reutiliza la misma pila de ciclos que `while`/`for`
(sección anterior); dentro de un `switch` anidado en un ciclo, `continue`
sigue afectando al ciclo externo, nunca al `switch`, porque la regla semántica
(`checker.visitContinueStatement`) ya exige un ciclo real, y el `switch` solo
aporta su propio `break_label` a esa pila.

```
switch (x) { case 7: A case 6: B default: C }

t0 = x == 7;  if t0 goto L_A
t0 = x == 6;  if t0 goto L_B
goto L_C
L_A: A            ← si A no tiene 'break', sigue derecho hacia L_B
L_B: B
L_C: C
L_end:
```

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

### Clases

`this` nunca tiene un `Symbol` propio en la tabla de símbolos (el checker no
lo registra como binding, porque no se declara); el generador lo trata
siempre como el nombre literal `"this"`, que es exactamente el nombre que
`Layout._open_record` ya le da al primer parámetro de todo método
(`Slot("this", fp+8, 4)`). Los atributos se leen y escriben con `load`/`store`
sobre el offset que la sección 4.3 ya calculó; los métodos, incluido cuando se
llaman sobre `this` (`this.hablar()`), siempre despachan por vtable (sección
4.4) — ni siquiera dentro de la propia clase hay una ruta "rápida" que evite
la vtable, porque el objeto real detrás de `this` podría ser de una subclase.
`new` y la construcción del objeto están en la sección 4.4.

### `try`/`catch`

El único fallo en tiempo de ejecución que el compilador modela hoy es un
acceso a arreglo fuera de rango (sección 4.2); no hay división por cero ni
acceso a propiedades de `null`. Las excepciones **no se propagan entre
llamadas a función** — cada función resuelve sus propios `try/catch`, y un
fallo sin manejador activo en la función donde ocurre ejecuta `halt`. Esto es
deliberado: implementar un *unwind* real de la pila de llamadas es trabajo de
la fase de MIPS (manejo del stack pointer y de las direcciones de retorno),
no de esta.

`FunctionState` mantiene una pila de manejadores (`(etiqueta_catch,
nombre_de_err)`), empujada al entrar a un `try` y desempujada al salir —
exactamente el mismo patrón que la pila de ciclos usa para `break`/`continue`.
`fail()` (sección 4.2) consulta el tope de esa pila.

```
try { print(arr[10]); } catch (err) { print(err); }

t_len = *(arr + 0)
t_cmp = 10 >= t_len
if t_cmp goto L_fail
goto L_ok
L_fail:
    err = "Índice fuera de rango"
    goto L_catch
L_ok:
    ...
    goto L_end
L_catch:
    print err
L_end:
```

### Closures

Una función anidada que captura una variable de la función que la contiene
(`FunctionSymbol.captured`, ya calculado por la fase semántica) simplemente
**referencia esa variable por su nombre**, igual que lo haría la propia
función dueña. Esto funciona porque, a diferencia de los arreglos y los
objetos, el TAC de este compilador nunca modela los frames de las funciones
como memoria direccionable — cada variable es un nombre (`name_of`, que la
asocia al `Symbol`, no a qué `FunctionState` está activo en ese momento), y
los offsets de `ActivationRecord` son metadata para la fase de MIPS, no algo
que el TAC mismo consuma. *Quién* resuelve en qué frame físico vive ese nombre
en tiempo de ejecución (el enlace estático) es responsabilidad de esa fase
futura, apoyada en `captured` y en los offsets que `Layout` ya calculó aquí.

Una consecuencia práctica: el TAC no distingue un nivel de anidación de
cinco — `f_outer_middle_inner` lee `x`, capturada por `f_outer`, exactamente
igual que si `x` fuera suya.

```
function outer(): integer {
  let x: integer = 10;
  function middle(): integer {
    function inner(): integer { return x + 1; }
    return inner();
  }
  return middle();
}

f_outer_middle_inner:
    begin_func 12
    t0 = x + 1
    return t0
    end_func
```

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
7. El único fallo en tiempo de ejecución que se modela es el acceso a
   arreglo fuera de rango; no hay división por cero ni acceso a propiedades
   de `null`, y una excepción nunca cruza una llamada a función (sección 6,
   `try`/`catch`).
8. Una variable capturada por una función anidada se referencia por su
   nombre llano, sin un parámetro de enlace estático explícito en el TAC —
   ese enlace es trabajo de la fase de MIPS (sección 6, Closures).
9. El constructor de una clase siempre se llama de forma estática; solo los
   métodos declarados con `function` dentro del cuerpo despachan por vtable
   (sección 4.4).

## 8. Arquitectura del módulo

```
Driver.analyze_file ─► semantic.analyze ─► SemanticResult (symbols, bindings, declared, type_objects)
                                                     │
AnalysisResult.generate_tac ─► tac.generate ─► layout.assign_addresses (direcciones + frames)
                                             └► TacGenerator (visitor del parse tree) ─► TacProgram
```

| Archivo | Contenido |
| --- | --- |
| `program/tac/instructions.py` | `Quad`, `FunctionCode`, `TacProgram`, `VTableData` (formato texto y JSON) |
| `program/tac/temps.py` | `TempAllocator`: asignación y reciclaje de temporales |
| `program/tac/layout.py` | Tamaños, direcciones, `ActivationRecord`, layout de objetos, cómputo de vtables |
| `program/tac/generator.py` | `TacGenerator`: traducción construcción por construcción |
| `program/tac/__init__.py` | `generate(tree, semantic)` |

Pruebas: `tests/codegen/` — expresiones y temporales, control de flujo,
funciones y frames, arreglos, `foreach`/`switch`, `try`/`catch`, clases y
vtable, closures, y un caso de integración que corre `program.cps` completo y
confirma que no queda ningún `# TODO`.

## 9. Decisiones de diseño de los arreglos, clases y excepciones

Tres decisiones que afectan directamente el TAC generado y que conviene poder
justificar:

1. **Chequeo de límites en tiempo de ejecución.** Todo acceso a arreglo
   (lectura o escritura, con índice literal o calculado) genera la secuencia
   de la sección 4.2, no solo una advertencia estática. La advertencia
   estática (`SEM604`) sigue existiendo para índices literales fuera de rango
   detectables en compilación, pero no sustituye al chequeo en tiempo de
   ejecución.
2. **`switch` sin `break` cae al siguiente `case`** (estilo C), coherente con
   que Compiscript es un subset de TypeScript/JavaScript, donde `switch`
   también hace *fallthrough* por defecto.
3. **La sobrescritura de métodos usa vtable**, es decir, despacho dinámico
   real basado en la clase con la que el objeto se construyó (`new`), no en
   el tipo declarado de la variable que lo referencia. Es lo que exige el
   polimorfismo y lo que la fase de MIPS va a necesitar para generar las
   llamadas indirectas.

## 10. Fuera de alcance

Explícitamente no se modelan, y quedan documentadas aquí para que la
ausencia sea una decisión y no un olvido:

- División por cero y acceso a propiedades de un valor `null` como fallos en
  tiempo de ejecución (solo el acceso a arreglo fuera de rango dispara
  `fail()`/`halt`).
- Propagación de excepciones entre llamadas a función (un `try/catch` solo
  protege operaciones dentro de la misma función).
- Funciones como valores de primera clase sin llamarlas de inmediato
  (`let f = miFuncion;` sin una invocación en la misma expresión).
