# Generación de código MIPS

Documento de la fase final: traducir el código de tres direcciones (TAC) ya
generado a ensamblador MIPS real, ejecutable en un simulador. Complementa
[lenguaje intermedio](lenguaje-intermedio.md), que describe el TAC que esta
fase toma como entrada.

> **Estado:** etapa 1 (núcleo). Cubre aritmética, conversiones, concatenación
> de strings, control de flujo, y llamadas/retornos de función — incluida la
> recursión. Arreglos, clases con vtable, `foreach`/`switch`/`try-catch` y
> closures quedan para una etapa siguiente; el generador emite un comentario
> `# TODO MIPS <op>` para esas construcciones en vez de fallar. Ver la
> sección 7, Fuera de alcance.

## 1. Cómo generarlo

```bash
python3 program/Driver.py programa.cps --mips text
python3 program/Driver.py programa.cps --format json --mips json --symbols json
```

El MIPS solo se genera si el TAC se generó sin errores (que a su vez requiere
que el programa no tenga errores semánticos). `--mips` activa `--tac`
internamente si no se pidió aparte. Con errores, el compilador avisa
`No se generó MIPS: el programa tiene errores` y termina con código `1`.

## 2. Cómo correrlo en un simulador

El simulador usado es [MARS](https://github.com/dpetersanderson/MARS)
(MIT, última release `v.4.5.1`, agosto 2014 — ya no tiene desarrollo activo,
pero sigue siendo el estándar de facto para cursos de este tipo).

1. Bajar `Mars.jar` desde
   `https://github.com/dpetersanderson/MARS/releases` (tag `v.4.5.1`,
   archivo `Mars4_5.jar`) y colocarlo como `compiscript/Mars.jar`.
2. Correr el `.asm` generado:

```bash
java -jar Mars.jar nc sm ae1 se1 programa.asm
```

- `nc`: no muestra el aviso de copyright (limpia la salida si se redirige).
- `sm`: arranca la ejecución en la etiqueta `main`.
- `ae1`/`se1`: el código de salida es `1` si falla el ensamblado o la
  simulación, para poder usarlo en scripts/pruebas automatizadas.

`tests/mipsgen/test_simulator.py` hace exactamente esto desde la batería de
pruebas, por subproceso, y compara la salida real contra lo esperado — se
omite solo si no hay `java` en el PATH o no se ha vendoreado `Mars.jar`,
igual que ya hace `tests/test_grammar.py` sin Java.

## 3. Arquitectura del módulo

```
tac.generate ──► TacProgram ──► mips.generate(tac, table) ──► MipsProgram ──► .asm
```

| Archivo | Contenido |
| --- | --- |
| `program/mips/blocks.py` | Bloques básicos y análisis de siguiente uso/vivacidad por bloque |
| `program/mips/registers.py` | `get_reg()`, `RegisterDescriptor`/`AddressDescriptor` |
| `program/mips/callseq.py` | Prólogo, epílogo, secuencia de llamada, layout del frame |
| `program/mips/runtime.py` | Rutinas de soporte escritas a mano (`tostr`, `concat`, impresión de booleanos) |
| `program/mips/emitter.py` | `MipsGenerator`: traduce cada cuádruplo, arma `.data`/`.text` |

Igual que `program/tac/`, cada módulo es chico y con una responsabilidad; el
emisor despacha por operación de TAC con una tabla, no con una cadena larga
de `if`/`elif`.

## 4. Asignación de registros — `get_reg()`

Algoritmo clásico de Aho & Ullman, restringido a un bloque básico a la vez
(usa la información de siguiente uso que calcula `blocks.py`). Dos pools:
`$t0`–`$t9` (temporales, de uso libre) y `$s0`–`$s7` (reservados para
preservar entre llamadas — no se usan todavía en esta etapa, ver sección 6).

Reglas, en orden:

1. **Reutilizar el registro de un operando que muere aquí**: si `x = y op z`
   y `y` no se vuelve a necesitar después de esta instrucción y su registro
   no tiene nada más adentro, ese registro se reutiliza para el resultado.
2. **Un registro vacío**, si lo hay.
3. **Derramar (spill)** el mejor candidato: se prefiere uno que ya tiene una
   copia en memoria (no hace falta guardar nada) y, entre varios igual de
   baratos, el que se necesita más lejos — o nunca más, dentro del bloque.

### El asignador se reinicia en cada bloque básico

Una etiqueta puede alcanzarse desde más de un predecesor (las dos ramas de un
`if` uniéndose, el salto de vuelta de un ciclo). Lo que el asignador cree que
hay en un registro al final de un bloque no es una suposición segura al
principio de otro: el camino que realmente se ejecutó en tiempo de ejecución
puede no ser el último que el compilador procesó. Por eso cada bloque empieza
sin ningún registro "confiable" — todo lo que necesita se recarga desde su
dirección de memoria, que siempre está al día porque:

- una variable con nombre (local, parámetro, global) se escribe a memoria
  **en el mismo momento** en que se define (*write-through*, nunca
  *write-back*) — nunca queda una copia "sucia" solo en un registro;
- un temporal nunca sobrevive más allá del final de su propio bloque (lo
  garantiza `program/tac/temps.py`, no es una suposición).

Esto costó un bug real durante el desarrollo: sin el reinicio, un `if`/`else`
que define la misma variable en las dos ramas podía, en el punto de unión,
confiar en el registro que la rama procesada *al final* (en el orden del
código fuente) dejó — no en la que realmente corrió. `tests/mipsgen/test_emitter.py::test_if_else_reloads_the_variable_at_the_join_point`
y la versión que de verdad corre en MARS
(`test_simulator.py::test_if_else_join_reads_the_branch_that_actually_ran`)
cubren exactamente este caso.

## 5. Secuencia de llamada y retorno

Exactamente el diseño de los diagramas del equipo:

```
LLAMADOR                                    LLAMADO
addiu $sp,$sp,-4n                            (etiqueta de la función)
sw argN, off($sp)  (cada argumento)          addiu $sp,$sp,-8
jal f_nombre          ───────────────►       sw $ra,4($sp)
                                              sw $fp,0($sp)
                                              move $fp,$sp
                                              addiu $sp,$sp,-(resto del frame)
                                              ... cuerpo ...
                                              return x: move $v0,Rx ; j f_ret
                                              f_ret:
                                              move $sp,$fp
                                              lw $ra,4($sp)
addiu $sp,$sp,4n      ◄───────────────       lw $fp,0($sp)
move Rt,$v0                                  addiu $sp,$sp,8 ; jr $ra
```

- **Los argumentos van por la pila, no por `$a0`–`$a3`**: así ya lo fija el
  frame que calculó `program/tac/layout.py` (los parámetros ya tienen offset
  `fp+8`, `fp+12`...), y un `float` de 8 bytes no cabría en un solo `$a`.
- **Un solo punto de salida por función** (`f_ret`): todo `return` hace
  `j f_ret` en vez de su propio `jr $ra`, así que el epílogo se escribe una
  sola vez.
- **`main` no tiene llamador**: nunca se alcanza por `jal`, así que su
  "epílogo" no es `jr $ra` (saltaría a una dirección basura) sino el syscall
  de salida (`li $v0,10 ; syscall`).
- **Llamada indirecta** (`calli`, para despacho por vtable — próxima etapa):
  `jalr` en vez de `jal`.

### El frame, con direcciones reales

```
        direcciones altas
   ┌──────────────────────┐
   │ parámetro n           │  fp+8+...      (ya resuelto por tac/layout.py)
   │ parámetro 1 / this    │  fp+8
   ├──────────────────────┤
   │ dirección de retorno  │  fp+4
   │ fp del llamador        │  fp+0   ← fp
   ├──────────────────────┤
   │ locales                │  fp-4, fp-8...  (ya resuelto por tac/layout.py)
   │ temporales             │  siguen hacia abajo, un home fijo por nombre
   └──────────────────────┘
        direcciones bajas  ← sp
```

`frameSize(MIPS) = frameSize(TAC) + 4 × (temporales que en algún punto
guardan un float)`. `frameSize(TAC)` (`8 + locales + 4×temporales`) ya la
calculó la fase anterior; esta etapa solo la extiende para los temporales que
necesitan 8 bytes en vez de 4 (sección 6). El `+4 × (#$s usados)` y el
`+4 si hay enlace de acceso` de la fórmula original del equipo son ambos 0 en
esta etapa — ver la sección 6.

## 6. Decisiones que simplifican el diseño original, a propósito

Dos términos de la fórmula del frame que el equipo diseñó quedan en 0 en esta
etapa — no porque los diagramas estuvieran mal, sino porque esta entrega
toma la instancia más simple de un diseño que sigue siendo válido:

1. **Ningún valor se promueve a un registro `$s`.** Antes de cualquier
   `call`/`calli` (de usuario o de una rutina de runtime como `tostr`), se
   derraman todos los `$t` activos (`RegisterAllocator.spill_all`) en vez de
   mantener alguno preservado en un `$s` a través de la llamada. Es
   correcto, solo que no optimiza los valores que "sobreviven" una llamada.
   Promoverlos a `$s` es una optimización real, pendiente.
2. **El enlace de acceso (closures) no está conectado todavía.** Las
   closures son parte de la etapa siguiente junto con arreglos y clases.

Una decisión nueva, no anticipada por los diagramas (que no mencionan
`$f`, centrados en un ejemplo entero puro):

3. **Los valores `float` nunca se asignan a un registro.** Cada operación
   flotante carga directo desde memoria a un par de registros `$f`
   (`$f0`/`$f2`/`$f4`, fijos, sin bookkeeping entre instrucciones), opera, y
   guarda el resultado directo a memoria. Es correcto — verificado en MARS
   (`1.5 + 2.25 = 3.75`) — pero no optimizado. Un asignador de registros `$f`
   en paralelo al de enteros es trabajo futuro.
   **Límite conocido:** comparar dos floats (`1.5 < 2.0`) todavía no se
   detecta como caso especial y cae por el camino entero, lo cual es
   incorrecto para ese caso puntual — no lo ejercita el alcance de esta
   etapa (aritmética/control de flujo/funciones), documentado aquí en vez de
   dejarlo silencioso.

Por la misma razón (sin registro para floats), un temporal que en algún
punto guarda un `float` necesita un *home* de 8 bytes en vez de 4 — de ahí
el término extra en la fórmula del frame de la sección 5. El generador lo
calcula con un barrido simple: cualquier cuádruplo cuyo `type` sea `"float"`
y cuyo resultado sea un temporal marca ese nombre para 8 bytes.

## 7. `alloc`, por qué sí entra en esta etapa

Arreglos y objetos (`load`/`store`/`calli` sobre ellos) quedan para la
siguiente etapa, pero `alloc` en sí **sí** se traduce ya, porque `concat` lo
necesita para ser correcto. Una concatenación encadenada
(`"a" + b + "c"`) genera dos cuádruplos `concat` seguidos, el segundo
leyendo el resultado del primero — si ambos escribieran a un mismo buffer
estático compartido, el segundo se pisaría a sí mismo mientras todavía lo
está leyendo, y una variable de tipo `string` que haya capturado el primer
resultado cambiaría de valor sola más adelante. El syscall `sbrk` (9) de
MARS ya es un asignador de memoria real, así que darle a cada `concat`/
`tostr` su propio bloque fresco no cuesta nada extra:

```
__alloc:
    li $v0, 9
    syscall      # $a0 ya trae el tamaño en bytes; $v0 devuelve la dirección
    jr $ra
```

Verificado en MARS con concatenación encadenada y reutilización posterior de
la variable resultante
(`test_simulator.py::test_chained_concat_does_not_corrupt_an_earlier_result`).

## 8. Rutinas de soporte (`program/mips/runtime.py`)

Texto MIPS fijo, escrito a mano, que se agrega una sola vez al final de todo
programa generado:

| Rutina | Qué hace |
| --- | --- |
| `__alloc` | Sección 7 |
| `__tostr_int` | Entero → su texto decimal, en un bloque nuevo de `__alloc`. Maneja negativos con un registro `$s` dedicado para el signo (ver nota abajo) |
| `__concat` | Dos strings → su concatenación, en un bloque nuevo |
| `__print_bool` | Imprime `"true"`/`"false"` (MIPS no tiene un syscall para booleano) |

**Nota de diseño de `__tostr_int`:** la primera versión reutilizaba `$a0`
para recordar si el número era negativo, pero `$a0` se pisa para pasarle el
tamaño a `__alloc` — para cuando se necesitaba el signo, ya no estaba. La
versión actual usa un registro `$s` dedicado (callee-saved, así que
sobrevive la llamada a `__alloc` sin ayuda extra) que se fija una sola vez al
principio y no se vuelve a tocar. Encontrado corriendo `print("neg: " + x)`
con `x` negativo en MARS de verdad, no por inspección del código — exactamente
el tipo de bug que una traza a mano del ensamblador no garantiza atrapar.

## 9. Impresión por tipo

`print` despacha por el campo `type` que ahora carga cada cuádruplo (ver
sección 10): `integer` → syscall 1, `string` → syscall 4, `float` → syscall 2
(carga el valor a `$f12` primero), `boolean` → `__print_bool`.

## 10. Prerrequisito: los cuádruplos ahora cargan su tipo

`Quad` (`program/tac/instructions.py`) ganó un campo `type` opcional —
el nombre del tipo de Compiscript (`"integer"`, `"float"`, `"string"`,
`"boolean"`, un nombre de clase) de su valor: el del resultado cuando
produce uno, el de su operando cuando no (`print`, `param`, `return`). El
generador de TAC ya conocía ese tipo en cada `Value` al momento de emitir —
nunca se había guardado, porque la fase de TAC no lo necesitaba. El back-end
de MIPS sí: para elegir entre instrucciones de enteros y de punto flotante,
para elegir el syscall de `print`, y para decidir si un temporal necesita un
*home* de 8 bytes. No es un rediseño — es un campo nuevo, poblado en los
mismos sitios donde `program/tac/generator.py` ya llama a `emit()` (con
`value.type`/`symbol.type`, que ya tenía en mano). No cambia el formato de
texto de `--tac` (los 257 tests previos de esa fase siguen pasando sin
tocarlos).

## 11. Fuera de alcance de esta etapa

- Arreglos y objetos: `load`, `store`, `alloc` de objeto y acceso a atributos
  — el generador emite `# TODO MIPS <op>` para estos cuádruplos.
- Clases, vtable y despacho dinámico (`calli`).
- `foreach`, `switch`, `try`/`catch`.
- Closures (el enlace de acceso, sección 6).
- División por cero y acceso a `null` como fallos en tiempo de ejecución
  (ya fuera de alcance desde la fase de TAC).
- Comparación entre dos valores `float` (sección 6, punto 3).
- Promoción de valores a registros `$s` — toda esta etapa usa solo `$t0`–`$t9`.

**Importante:** `# TODO MIPS <op>` es un comentario, no una instrucción — no
detiene el ensamblado ni la simulación. Un programa que mezcla construcciones
cubiertas con construcciones fuera de alcance (`program.cps` completo, por
ejemplo, que además de aritmética y funciones usa `foreach` y clases) sigue
ensamblando y corriendo, pero el comportamiento a partir del primer `TODO`
que se ejecuta de verdad queda indefinido: por ejemplo, el `foreach` de
`program.cps` depende de un `load` no traducido para leer tanto la longitud
del arreglo como cada elemento, así que su condición de salida nunca se
actualiza y el ciclo no termina como debería. Lo que sí está en el alcance de
esta etapa (aritmética, condicionales, `while`/`for`, funciones recursivas) se
verificó aislado — sección 2 y `test_simulator.py` — no mezclado con lo que
todavía no se traduce.

## 12. Pruebas

`tests/mipsgen/`, paralelo a `tests/codegen/`:

| Archivo | Cubre |
| --- | --- |
| `test_blocks.py` | Partición en bloques básicos, análisis de siguiente uso |
| `test_registers.py` | `get_reg()` en aislamiento: reutilización, derrame, recarga |
| `test_emitter.py` | TAC → MIPS estructural (sin simulador): prólogo/epílogo, tamaño de frame, construcciones fuera de alcance generan `# TODO` en vez de fallar |
| `test_simulator.py` | Los mismos programas, corridos de verdad en MARS, comparando la salida real — se omite sin Java/`Mars.jar` |

Todo lo que `test_simulator.py` verifica (factorial recursivo, aritmética con
negativos, `if`/`else`, `while`, floats, concatenación encadenada, booleanos)
corrió contra el simulador real durante el desarrollo, no solo se trazó a
mano.
