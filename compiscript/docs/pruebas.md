# Batería de pruebas

Documento de la Fase 5. Describe la organización de la suite, la convención de
fixtures, cómo se ejecuta y cómo se mide la cobertura.

## Organización

    tests/
      support.py              helpers y clase base de las pruebas semánticas
      coverage_report.py      reporte de cobertura con la librería estándar
      test_grammar.py         gramática validada con Java y el JAR de ANTLR
      test_syntax.py          frontend sintáctico (Driver.analyze_file)
      test_cli.py             códigos de salida y formatos de salida del CLI
      fixtures/valid/         programas que deben analizarse sin errores
      fixtures/invalid/       programas que deben producir diagnósticos
      rules/                  batería semántica, un archivo por área
        test_types.py         aritmética, concatenación, lógica, comparaciones,
                              ternario, asignaciones, constantes y print
        test_scopes.py        ámbitos, resolución de nombres y tabla de símbolos
        test_functions.py     argumentos, retornos, recursión, anidadas, closures
        test_control_flow.py  condiciones, ciclos, break, continue, switch, catch
        test_classes.py       miembros, constructores, this y herencia
        test_arrays.py        literales, índices y límites estáticos
        test_programs.py      código muerto y programas completos
      codegen/                 batería de generación de código intermedio (TAC)
        test_expressions.py   expresiones, conversiones y reciclaje de temporales
        test_control_flow.py  if/else, while, do-while, for
        test_functions.py     llamadas, frames, direcciones y casos fallidos
        test_arrays.py        literales, lectura/escritura y chequeo de límites
        test_foreach_switch.py foreach (lowering a índice) y switch (fallthrough)
        test_try_catch.py     manejo de fallos en tiempo de ejecución
        test_classes.py       layout de objetos, vtable y despacho dinámico
        test_closures.py      funciones anidadas que capturan variables
        test_integration.py   program.cps completo, sin ningún `# TODO`

El paquete se llama `rules/` y no `semantic/` a propósito: `program/semantic`
ya ocupa ese nombre y `unittest discover` agrega `tests/` al `sys.path`, así
que dos paquetes homónimos se taparían entre sí. Por la misma razón el
paquete de TAC se llama `codegen/` y no `tac/`, que ya ocupa `program/tac`.

## Convención de fixtures

- `tests/fixtures/valid/` contiene programas que **no** deben producir ningún
  error. Pueden producir advertencias solo si la prueba lo declara.
- `tests/fixtures/invalid/` contiene programas que **sí** deben producir
  diagnósticos, y el nombre del archivo describe el error principal.
- Los casos de una sola regla no usan fixtures: se escriben como cadenas dentro
  de la prueba y se analizan con `support.analyze_code`, que crea un archivo
  temporal y lo elimina al terminar.
- Los fixtures se reservan para programas completos o para casos que también
  se usan desde la línea de comandos.

Fixtures actuales:

| Archivo | Propósito |
| --- | --- |
| `valid/float_and_assignment.cps` | `float` y asignación a propiedad |
| `valid/programa_completo.cps` | Programa válido que recorre todas las áreas |
| `invalid/missing_semicolon.cps` | Error sintáctico `SYN001` |
| `invalid/unknown_character.cps` | Error léxico `LEX001` |
| `invalid/errores_multiples.cps` | Ocho errores semánticos recuperables |

## Qué verifica cada aserción

`support.SemanticTestCase` ofrece dos aserciones:

- `assert_ok(fuente)` exige que no haya **ningún error**; las advertencias sí se
  permiten.
- `assert_diagnostic(fuente, código, línea, columna, severidad)` exige el
  código, la severidad y, cuando se indican, la línea y la columna exactas.
  También comprueba que el resultado global sea coherente: un error hace fallar
  el análisis, una advertencia no.

Las pruebas **nunca comparan el texto completo del mensaje**, solo códigos,
severidades y posiciones, para que reescribir un mensaje no rompa la suite.

## Ejecución

    ./.venv/Scripts/python.exe -m unittest discover -s tests -v

Estado actual: **251 pruebas**. `test_grammar.py` se omite si falta Java (4
pruebas) y la suite semántica y de TAC se omiten si falta el runtime de
ANTLR; en un entorno completo con Java instalado no debe haber ninguna
omisión.

## Cobertura

No se instalan dependencias adicionales, así que el reporte usa el módulo
`trace` de la librería estándar:

    ./.venv/Scripts/python.exe tests/coverage_report.py
    ./.venv/Scripts/python.exe tests/coverage_report.py --output cobertura

Cobertura medida sobre el compilador:

| Módulo | Cobertura |
| --- | ---: |
| `Driver` | 92.0 % |
| `semantic.checker` | 93.3 % |
| `semantic.collector` | 94.8 % |
| `semantic.symbols` | 98.7 % |
| `semantic.analyzer` | 95.7 % |
| `semantic.diagnostics` | 93.1 % |
| `semantic.symbol_table` | 92.9 % |
| `semantic.scopes` | 86.7 % |
| `semantic.annotations` | 85.1 % |
| `semantic.types` | 77.8 % |

Lo que queda sin cubrir son ramas defensivas: guardas de entorno, `__repr__` y
combinaciones de tipos que la gramática no puede producir.

## Integración continua

`.github/workflows/compiscript-tests.yml` ejecuta en cada push y en cada pull
request que toque `compiscript/`: instala Java y Python, instala el runtime de
ANTLR, verifica que el parser generado esté en el repositorio, corre la suite
completa, analiza el programa oficial y genera el reporte de cobertura.
