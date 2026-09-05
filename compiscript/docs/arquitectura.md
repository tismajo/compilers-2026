# Arquitectura del compilador de Compiscript

Documento de la Fase 8. Describe los componentes, el flujo de datos y las
decisiones estructurales de la implementación.

Documentos relacionados:
[tabla de símbolos](tabla-de-simbolos.md) ·
[reglas semánticas](reglas-semanticas.md) ·
[visualización](visualizacion.md) ·
[pruebas](pruebas.md) ·
[decisiones](decisiones.md) ·
[guía de uso](uso.md)

## Visión general

    ┌──────────────┐
    │  archivo.cps │
    └──────┬───────┘
           │
    ┌──────▼───────────────────────────────────────────────────────┐
    │ program/Driver.py            (CLI y orquestador)             │
    │                                                              │
    │  ┌────────────┐   ┌────────────┐                             │
    │  │  Lexer     │──▶│  Parser    │  CompiscriptLexer.py        │
    │  │  (ANTLR)   │   │  (ANTLR)   │  CompiscriptParser.py       │
    │  └─────┬──────┘   └─────┬──────┘                             │
    │        │ LEX001         │ SYN001                             │
    │        └────────┬───────┘                                    │
    │                 ▼                                            │
    │           parse tree ──────────────┐                         │
    │                 │                  │                         │
    │  ┌──────────────▼───────────────┐  │                         │
    │  │ program/semantic/            │  │                         │
    │  │                              │  │                         │
    │  │  collector.py   pasada 1     │  │                         │
    │  │       │  clases y firmas     │  │                         │
    │  │       ▼                      │  │                         │
    │  │  checker.py     pasada 2     │  │                         │
    │  │       │  ámbitos, tipos      │  │                         │
    │  │       ▼                      │  │                         │
    │  │  symbol_table   diagnostics  │  │                         │
    │  │       │  SEM***              │  │                         │
    │  └───────┼──────────────────────┘  │                         │
    │          │                         │                         │
    │          ▼                         ▼                         │
    │   diagnósticos            program/treeview.py                │
    │   tabla de símbolos       árbol JSON / HTML / SVG            │
    └──────────┬───────────────────────────┬───────────────────────┘
               │  JSON en stdout           │
               ▼                           ▼
    ┌──────────────────────┐   ┌───────────────────────────┐
    │ extension/  (VS Code)│   │ terminal, pruebas, CI     │
    │  Problems, webviews  │   │                           │
    └──────────────────────┘   └───────────────────────────┘

El parse tree se construye **una sola vez**. El análisis semántico y la
visualización lo reciben ya construido; nada vuelve a leer el archivo fuente.

## Componentes

| Componente | Archivo | Responsabilidad |
| --- | --- | --- |
| Gramática | `program/Compiscript.g4` | Reglas léxicas y sintácticas; fuente de los archivos generados |
| Gramática BNF | `program/Compiscript.bnf` | Misma gramática en notación BNF, para el reporte |
| Lexer y parser | `program/Compiscript{Lexer,Parser}.py` | Generados por ANTLR 4.13.1; nunca se editan a mano |
| Listener y visitor | `program/Compiscript{Listener,Visitor}.py` | Generados; el analizador extiende el visitor |
| CLI | `program/Driver.py` | Lee el archivo, corre el frontend, invoca la semántica y formatea la salida |
| Modelo de tipos | `program/semantic/types.py` | Tipos y reglas de compatibilidad |
| Símbolos | `program/semantic/symbols.py` | Entidades de la tabla de símbolos |
| Ámbitos | `program/semantic/scopes.py` | Árbol de ámbitos y estado del recorrido |
| Tabla de símbolos | `program/semantic/symbol_table.py` | Fachada, exportación a JSON y volcado legible |
| Diagnósticos | `program/semantic/diagnostics.py` | Registro estructurado y catálogo de códigos |
| Anotaciones | `program/semantic/annotations.py` | Posiciones y resolución de anotaciones de tipo |
| Pasada 1 | `program/semantic/collector.py` | Clases, herencia y firmas globales |
| Pasada 2 | `program/semantic/checker.py` | Ámbitos, resolución, tipos y reglas semánticas |
| Orquestador semántico | `program/semantic/analyzer.py` | Ejecuta ambas pasadas y devuelve el resultado |
| Visualización | `program/treeview.py` | Árbol enriquecido y renderizadores HTML y SVG |
| IDE | `extension/` | Extensión de VS Code en TypeScript |

## Flujo de una compilación

1. **Lectura.** `Driver.analyze_file` abre el archivo como UTF-8. Si no existe,
   emite `CLI001` y termina con código `2`.
2. **Léxico y sintaxis.** Se quitan los listeners de error por defecto de ANTLR
   y se instalan dos propios: los errores léxicos salen como `LEX001` y los
   sintácticos como `SYN001`, con línea y columna base 1.
3. **Corte.** Si hubo errores sintácticos el proceso se detiene ahí: un árbol
   roto solo produciría diagnósticos semánticos sin sentido.
4. **Pasada 1.** `Collector` registra en el ámbito global las clases —primero
   los nombres, luego los padres, luego los ciclos de herencia y por último los
   miembros— y las firmas de las funciones de nivel superior. Registrar la
   firma antes de visitar el cuerpo es lo que habilita recursión, recursión
   mutua y referencias hacia adelante.
5. **Pasada 2.** `Checker` recorre los cuerpos: crea el árbol de ámbitos,
   inserta símbolos, resuelve identificadores, calcula el tipo de cada
   expresión y aplica las reglas semánticas.
6. **Salida.** El `Driver` entrega diagnósticos, tabla de símbolos y árbol en
   texto o JSON. Código de salida `0` sin errores, `1` con errores, `2` si el
   archivo no existe. Las advertencias no cambian el código de salida.

## Estructura del parse tree

Se recorre **directamente el parse tree de ANTLR**; no se construye un AST
propio. La decisión se tomó al inicio del proyecto y condiciona el diseño:

- Las reglas de la gramática ya distinguen cada construcción del lenguaje, así
  que un AST sería una segunda representación equivalente.
- Los nodos de ANTLR conservan línea y columna, que es lo que necesitan los
  diagnósticos y la visualización.
- El costo es que el analizador trabaja con las alternativas etiquetadas de la
  gramática (`AssignExpr`, `IdentifierExpr`, `CallExpr`, `IndexExpr`,
  `PropertyAccessExpr`, `NewExpr`, `ThisExpr`) en lugar de nodos propios.

Para las fases futuras de TAC y MIPS, cada símbolo reserva cuatro campos vacíos
—`offset`, `size`, `storage`, `label`— y el `Checker` ya guarda el tipo de cada
expresión en un diccionario indexado por nodo.

La forma serializada del árbol está documentada en
[visualización](visualizacion.md).

## Sistema de tipos

Jerarquía: `PrimitiveType` (`integer`, `float`, `string`, `boolean`, `null`,
`void`), `ArrayType`, `ClassType`, `FunctionType` y `ErrorType`.

`ErrorType` es absorbente: cualquier operación que lo toque vuelve a producir
`error` y no genera diagnóstico. Es lo que evita que un solo error se propague
como una cascada de mensajes.

Reglas de compatibilidad, conversión `integer`→`float`, comparabilidad y tipo
común están en [tabla de símbolos](tabla-de-simbolos.md#modelo-de-tipos).

## Tabla de símbolos y ámbitos

Un ámbito por programa, bloque, función, clase, `foreach` y `catch`. Cada
ámbito enlaza a su padre y la resolución sube por esa cadena. El diseño
completo —categorías de símbolo, política de shadowing, contexto de recorrido y
exportación a JSON— está en [tabla de símbolos](tabla-de-simbolos.md).

## Funciones, closures, clases, herencia y arreglos

- **Funciones.** La firma se registra antes del cuerpo, así que la recursión y
  la recursión mutua funcionan. Los parámetros y el cuerpo comparten un solo
  ámbito. Una función sin anotación de retorno es `void`.
- **Funciones como valor.** El tipo de una función es su `FunctionType`, de modo
  que `let f = miFuncion;` es válido y `f(1)` se valida contra la firma. No
  existe sintaxis para anotar ese tipo, solo se infiere.
- **Closures.** Cuando la resolución de un nombre cruza la frontera de una
  función, el nombre se registra como capturado en todas las funciones
  intermedias. La lista viaja en la tabla de símbolos, lista para la fase de
  generación de código.
- **Clases.** Un `ClassSymbol` guarda atributos, métodos y constructor, y
  resuelve miembros heredados subiendo por la cadena de padres. Una clase sin
  constructor explícito hereda el de su padre, y si no hay ninguno acepta cero
  argumentos.
- **Herencia.** Se detectan padres inexistentes y ciclos. Una subclase es
  asignable a su clase padre. Una sobrescritura debe respetar la firma
  heredada.
- **Arreglos.** El tipo de un literal se infiere como el tipo común de sus
  elementos; `[]` se adapta al tipo del destino. Los arreglos multidimensionales
  son arreglos de arreglos. El índice debe ser `integer` y solo se verifica
  estáticamente cuando es un literal sobre un arreglo de longitud conocida.

## Diagnósticos

Todos comparten la misma estructura —código, fase, severidad, mensaje, línea y
columna— y el mismo diccionario JSON, que consumen la CLI, las pruebas y la
extensión. El catálogo completo, con las 12 decisiones aplicadas, está en
[reglas semánticas](reglas-semanticas.md).

    LEX001   error léxico
    SYN001   error sintáctico
    CLI001   archivo no encontrado
    SEM1xx   sistema de tipos          SEM5xx   clases y objetos
    SEM2xx   ámbitos y declaraciones   SEM6xx   arreglos
    SEM3xx   funciones                 SEM7xx   código muerto
    SEM4xx   control de flujo

`DiagnosticBag` descarta duplicados exactos, así que un mismo error nunca se
reporta dos veces aunque el recorrido pase por el nodo más de una vez.

## Integración con VS Code

    VS Code ──execFile──▶ python Driver.py archivo.cps --format json
       ▲                                    │
       └──────── JSON por stdout ◀──────────┘

La extensión no reimplementa nada del compilador: lanza el proceso sin shell,
lee el JSON de la salida estándar y traduce cada diagnóstico a una entrada del
panel *Problems*, restando 1 a la línea y a la columna porque la API de VS Code
es base 0. Docker no interviene. El detalle está en
[`extension/README.md`](../extension/README.md).

## Qué no incluye esta entrega

Generación de código intermedio (TAC) y de código MIPS. Existen
`README_TAC_GENERATION.md` y `README_CODE_GENERATION.md` en el repositorio,
pero corresponden a fases posteriores del curso. La arquitectura las anticipa
con los campos reservados de los símbolos y con el registro de tipos por nodo.
