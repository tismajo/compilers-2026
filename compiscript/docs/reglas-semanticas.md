# Reglas semánticas de Compiscript

Documento de la Fase 4. Describe qué valida el analizador, con qué código lo
reporta y qué decisiones se tomaron ante las contradicciones del enunciado.

Todas las reglas se aplican en `program/semantic/checker.py`, sobre el mismo
recorrido que construye la tabla de símbolos descrita en
[`tabla-de-simbolos.md`](tabla-de-simbolos.md).

## Catálogo de diagnósticos

Cada diagnóstico lleva código, fase, severidad, mensaje, línea y columna.

### `SEM1xx` — Sistema de tipos

| Código | Regla |
| --- | --- |
| `SEM101` | Operandos inválidos en `+`, `-`, `*`, `/`, `%` o en el `-` unario |
| `SEM102` | Operandos no booleanos en `&&` o `||` |
| `SEM103` | Operando no booleano en `!` |
| `SEM104` | Comparación entre tipos incompatibles |
| `SEM105` | Inicialización o asignación incompatible con el tipo del destino |
| `SEM106` | Condición no booleana en `if`, `while`, `do-while`, `for` o el ternario |
| `SEM107` | Ramas del ternario sin tipo común |
| `SEM108` | Reasignación de una constante |
| `SEM109` | Argumento no imprimible en `print` |
| `SEM110` | El lado izquierdo de la asignación no es un destino asignable |

### `SEM2xx` — Ámbitos y declaraciones

Documentados en [`tabla-de-simbolos.md`](tabla-de-simbolos.md): `SEM201` a
`SEM211`.

### `SEM3xx` — Funciones

| Código | Regla |
| --- | --- |
| `SEM301` | Número de argumentos distinto al de la firma |
| `SEM302` | Tipo de argumento incompatible, por posición |
| `SEM303` | Retorno incompatible con la firma, retorno ausente o retorno de valor en una función `void` |
| `SEM304` | `return` fuera de una función |
| `SEM305` | Función con retorno declarado que puede terminar sin retornar |
| `SEM306` | Llamada sobre un valor que no es una función |

### `SEM4xx` — Control de flujo

| Código | Regla |
| --- | --- |
| `SEM401` | `break` fuera de un ciclo o de un `switch` |
| `SEM402` | `continue` fuera de un ciclo |
| `SEM403` | `foreach` sobre algo que no es un arreglo |
| `SEM404` | `case` no comparable con la expresión del `switch` |
| `SEM405` | `case` constante duplicado |

### `SEM5xx` — Clases y objetos

| Código | Regla |
| --- | --- |
| `SEM501` | `new` sobre una clase inexistente |
| `SEM502` | Miembro inexistente en la clase o en sus ancestros |
| `SEM503` | `this` fuera de un método o de un constructor |
| `SEM504` | Cantidad o tipo de argumentos incorrecto en el constructor |
| `SEM505` | Sobrescritura que no respeta la firma heredada |
| `SEM506` | Acceso con `.` sobre un valor que no es un objeto |

### `SEM6xx` — Arreglos

| Código | Regla |
| --- | --- |
| `SEM601` | Índice que no es `integer` |
| `SEM602` | Indexación sobre un valor que no es arreglo |
| `SEM603` | Literal de arreglo con elementos sin tipo común |
| `SEM604` | **Advertencia.** Índice literal fuera de un arreglo de longitud conocida |

### `SEM7xx` — Código muerto

| Código | Regla |
| --- | --- |
| `SEM701` | **Advertencia.** Instrucción inalcanzable después de `return`, `break` o `continue`, o después de un `if` cuyas dos ramas terminan |

## Decisiones aplicadas

1. **Concatenación con `+`.** El enunciado exige operandos numéricos, pero el
   programa oficial escribe `"5 + 1 = " + addFive`. Si alguno de los operandos
   es `string`, la operación es concatenación y produce `string`. El otro
   operando debe ser imprimible: `integer`, `float`, `boolean`, `string`,
   `null`, un arreglo o un objeto. Concatenar una función es error `SEM101`.
2. **`switch` con cualquier valor comparable.** El enunciado pide condición
   booleana; el ejemplo oficial usa un `integer`. Gana el ejemplo: la
   expresión y cada `case` solo deben ser comparables entre sí.
3. **`break` dentro de `switch`** está permitido además de dentro de ciclos.
4. **Operaciones mixtas `integer`/`float`** producen `float`. `integer` se
   convierte a `float` de forma implícita; nunca al revés.
5. **Índices dinámicos.** Solo se verifica estáticamente un índice literal
   sobre una variable inicializada con un literal de arreglo, y se reporta como
   advertencia. Cualquier otro índice queda para verificación en ejecución.
6. **Código muerto** es advertencia: no cambia el código de salida.
7. **Parámetro sin anotación** es error (`SEM210`); **función sin anotación de
   retorno** es `void`.
8. **La variable de `catch` es `string`.**
9. **Constantes.** La gramática ya obliga a `const NOMBRE = valor;`, así que la
   inicialización obligatoria está garantizada sintácticamente; el analizador
   solo impide la reasignación posterior (`SEM108`).
10. **Arreglo vacío.** `[]` adopta el tipo del destino, de modo que
    `let a: integer[] = [];` es válido.
11. **Closures.** Una función anidada registra las variables que toma del
    entorno de definición; se listan en la tabla de símbolos.
12. **Herencia.** Una subclase es asignable a su clase padre. `null` es
    asignable a clases, arreglos y funciones.

## Resultado de los ejemplos oficiales

| Archivo | Resultado |
| --- | --- |
| `program/program.cps` | Válido. Un único diagnóstico: advertencia `SEM604` en la línea 58 por `numbers[10]`, que el propio ejemplo usa dentro de un `try`. Código de salida `0`. |
| `tests/fixtures/valid/float_and_assignment.cps` | Válido, sin diagnósticos. |
| `tests/fixtures/invalid/missing_semicolon.cps` | `SYN001`, la semántica no se ejecuta. |
| `tests/fixtures/invalid/unknown_character.cps` | `LEX001`, la semántica no se ejecuta. |

El `README.md` oficial documenta `if (n < 60) continue;` sin llaves. La
gramática exige un bloque en el `if`, así que ese fragmento no compila. Se
conserva la gramática y se deja registrada la discrepancia.

## Ejecución

    ./.venv/Scripts/python.exe program/Driver.py archivo.cps
    ./.venv/Scripts/python.exe program/Driver.py archivo.cps --format json

Códigos de salida: `0` sin errores (las advertencias no lo cambian), `1` con
errores léxicos, sintácticos o semánticos, `2` cuando el archivo no existe.
