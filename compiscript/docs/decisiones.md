# Decisiones e interpretaciones

Documento de la Fase 8. Reúne las contradicciones detectadas en el enunciado y
qué se decidió en cada caso. Regla general: **ante una contradicción gana la
validez de los ejemplos oficiales**, y la decisión queda escrita aquí.

## Contradicciones del enunciado

### 1. `+` numérico contra concatenación

`README_SEMANTIC_ANALYSIS.md` exige que los operandos de `+` sean `integer` o
`float`. El programa oficial escribe `print("5 + 1 = " + addFive)`.

**Decisión.** Si alguno de los operandos es `string`, la operación es
concatenación y produce `string`. El otro operando debe ser imprimible:
`integer`, `float`, `boolean`, `string`, `null`, un arreglo o un objeto.
Concatenar una función es error `SEM101`. Sin operandos `string` se aplica la
regla aritmética estricta.

### 2. Condición del `switch`

El enunciado pide que la condición de `switch` sea `boolean`. El ejemplo
oficial hace `switch (addFive)` sobre un `integer`.

**Decisión.** `switch` acepta cualquier valor y cada `case` solo debe ser
comparable con él (`SEM404`). Exigir `boolean` invalidaría el ejemplo entregado
por el profesor.

### 3. Closures sin tipo de función

Se piden closures, pero la gramática no tiene sintaxis para anotar el tipo de
una función.

**Decisión.** Existe un `FunctionType` interno, no denotable: se infiere pero no
se puede escribir en una anotación. Permite pasar y retornar funciones y validar
las llamadas contra la firma.

### 4. Validación de índices

Se pide "validación de índices" sin distinguir qué es estático y qué de
ejecución. El programa oficial indexa `numbers[10]` sobre un arreglo de cinco
elementos, dentro de un `try`.

**Decisión.** Un índice literal sobre una variable inicializada con un literal
de arreglo se verifica y se reporta como **advertencia** `SEM604`. Cualquier
otro índice queda para ejecución. Si fuera error, el programa oficial no
compilaría.

### 5. `break` dentro de `switch`

La gramática no distingue el `break` de ciclo del de `switch`, y el `README.md`
lo usa dentro de un `switch`.

**Decisión.** `break` es válido dentro de un ciclo **o** de un `switch`
(`SEM401`). `continue` sigue restringido a ciclos (`SEM402`).

### 6. Ejemplo del `README.md` que no cumple la gramática

El `README.md` oficial documenta:

```cps
foreach (n in notas) {
  if (n < 60) continue;
  if (n == 100) break;
}
```

La regla `ifStatement: 'if' '(' expression ')' block ...` **exige llaves**, así
que ese fragmento no parsea.

**Decisión.** No se toca la gramática. Relajar el `if` para aceptar una
instrucción suelta reintroduce la ambigüedad del *dangling else*, que la
gramática entregada evita a propósito. La discrepancia queda documentada; el
fragmento equivalente válido es:

```cps
foreach (n in notas) {
  if (n < 60) { continue; }
  if (n == 100) { break; }
}
```

### 7. Versión de ANTLR

El JAR del repositorio es 4.13.1 y `requirements.txt` pedía el runtime 4.13.0.

**Decisión.** Se alineó el runtime a `antlr4-python3-runtime==4.13.1`.

### 8. Asignación por dos caminos

La gramática original permitía la asignación como `statement` y como
expresión, lo que producía ambigüedad.

**Decisión.** Se normalizó con `leftHandSide` y se eliminó la duplicidad dentro
de `statement`. La asignación sigue siendo expresión, porque el incremento del
`for` la necesita.

## Decisiones aprobadas del lenguaje

Aprobadas el 2026-09-06. También están en la checklist del proyecto.

| # | Tema | Decisión |
| ---: | --- | --- |
| 1 | `break` dentro de `switch` | Permitido |
| 2 | Shadowing en bloques anidados | Permitido, como TypeScript |
| 3 | Parámetro sin anotación de tipo | Error `SEM210` |
| 4 | Función sin anotación de retorno | `void` |
| 5 | Código muerto | Advertencia `SEM701`; no cambia el código de salida |
| 6 | Índice literal fuera de rango | Advertencia `SEM604` |
| 7 | Tipo de la variable de `catch` | `string` |
| 8 | Integración continua | `.github/workflows/` es la única excepción fuera de `compiscript/` |
| 9 | Ejemplo sin llaves del `README.md` | Se documenta; la gramática no cambia |
| 10 | Códigos de salida | `0`, `1`, `2`; los errores semánticos devuelven `1` |

## Interpretaciones de implementación

Casos que el enunciado no menciona y que hubo que resolver:

1. **Atributos y métodos viven en el ámbito de la clase.** Dentro de un método
   se pueden nombrar directamente además de usar `this`. Evita falsos errores en
   programas que no califican todos los accesos.
2. **Parámetros y cuerpo comparten un solo ámbito.** Una variable local con el
   nombre de un parámetro es redeclaración (`SEM202`), no shadowing.
3. **`[]` adopta el tipo del destino.** `let a: integer[] = [];` es válido.
4. **`null` es asignable a clases, arreglos y funciones**, nunca a un tipo
   primitivo.
5. **Operaciones mixtas `integer`/`float` producen `float`.** La conversión es
   implícita solo en esa dirección.
6. **Comparaciones relacionales** (`<`, `<=`, `>`, `>=`) aceptan dos números o
   dos strings; la igualdad acepta cualquier par comparable.
7. **Un diagnóstico marca un solo nodo del árbol**, el más interno que empieza
   en esa posición.
8. **La semántica no corre si hubo errores sintácticos**, porque el árbol roto
   solo produciría ruido.
9. **Constantes.** La gramática ya obliga a `const NOMBRE = valor;`, así que la
   inicialización obligatoria está garantizada sintácticamente; el analizador
   solo impide la reasignación (`SEM108`).
10. **Una clase sin constructor propio hereda el de su padre**; si no hay
    ninguno en la cadena, acepta cero argumentos.

## Decisiones de proyecto

- **Se recorre el parse tree directamente, sin AST propio.** Ver
  [arquitectura](arquitectura.md#estructura-del-parse-tree).
- **La entrega cubre solo el análisis semántico.** No hay TAC ni MIPS.
- **El equipo es de cuatro integrantes**, aunque el enunciado hable de grupos de
  tres. Cada quien conserva commits identificables.
- **El compilador es Python y el IDE es una extensión de VS Code en
  TypeScript.**
- **El paquete de pruebas semánticas se llama `tests/rules/`**, no
  `tests/semantic/`: `unittest discover` agrega `tests/` al `sys.path` y un
  paquete homónimo taparía a `program/semantic`.
