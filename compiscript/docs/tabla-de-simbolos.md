# Tabla de símbolos de Compiscript

Documento de la Fase 3. Describe el modelo de tipos, los símbolos, los ámbitos
y las dos pasadas semánticas que los construyen.

## Ubicación del código

| Archivo | Rol |
| --- | --- |
| `program/semantic/types.py` | Modelo de tipos y reglas de compatibilidad |
| `program/semantic/symbols.py` | Símbolos almacenados en la tabla |
| `program/semantic/scopes.py` | Árbol de ámbitos y estado del recorrido |
| `program/semantic/symbol_table.py` | Fachada usada por el CLI y las pruebas |
| `program/semantic/diagnostics.py` | Diagnósticos estructurados y catálogo de códigos |
| `program/semantic/annotations.py` | Lectura de posiciones y anotaciones del parse tree |
| `program/semantic/collector.py` | Pasada 1: clases y firmas de funciones |
| `program/semantic/checker.py` | Pasada 2: ámbitos, resolución y tipos |
| `program/semantic/analyzer.py` | Ejecuta ambas pasadas |

## Modelo de tipos

Tipos primitivos: `integer`, `float`, `string`, `boolean`, `null`, `void`.
Tipos compuestos: `ArrayType` (con `dimensions` para arreglos anidados),
`ClassType` (nominal, con enlace al padre) y `FunctionType` (firma completa).
`ErrorType` es un tipo absorbente: cualquier operación con él vuelve a producir
`error`, lo que evita cascadas de diagnósticos a partir de un solo fallo.

Reglas de compatibilidad implementadas en `is_assignable`:

| Destino | Valor aceptado |
| --- | --- |
| Mismo tipo | Siempre |
| `float` | `integer` (ampliación segura) |
| Clase, arreglo o función | `null` |
| Clase padre | Cualquier subclase |
| Arreglo | Arreglo con el mismo tipo de elemento |
| `error` | Cualquiera, en ambos sentidos |

`common_type` calcula el tipo mínimo capaz de contener dos operandos y lo usan
los literales de arreglo y el operador ternario. `arithmetic_result` decide el
resultado de operaciones mixtas: si algún operando es `float`, el resultado es
`float`.

## Símbolos

Todos heredan de `Symbol` y guardan nombre, tipo, línea, columna, ámbito
propietario, mutabilidad y si están inicializados. Categorías: `variable`,
`constant`, `parameter`, `function`, `class`, `attribute`, `method`.

- `FunctionSymbol` guarda la lista de parámetros, el tipo de retorno, si el
  retorno estaba anotado, la clase propietaria cuando es un método, el ámbito
  de su cuerpo y la lista de variables capturadas por closure.
- `ClassSymbol` guarda el nombre del padre, el enlace resuelto al padre, los
  atributos, los métodos y el constructor, y resuelve miembros heredados con
  `lookup_attribute`, `lookup_method` y `lookup_constructor`.

Cada símbolo reserva cuatro campos vacíos para las fases futuras de TAC y MIPS:
`offset`, `size`, `storage` y `label`. Ninguna fase actual los escribe.

## Ámbitos

Se crea un ámbito para el programa y para cada bloque, función, clase,
`foreach` y `catch`. Cada ámbito conoce a su padre, de modo que `resolve`
recorre la cadena desde el ámbito actual hacia el global.

- Un identificador repetido **en el mismo ámbito** produce `SEM202`.
- Un identificador repetido **en un ámbito interno** es shadowing y está
  permitido (decisión 2 aprobada).
- Los parámetros y el cuerpo de una función comparten un solo ámbito, así que
  una variable local con el nombre de un parámetro sí es una redeclaración.
- Los atributos y métodos de una clase viven en el ámbito de la clase, por lo
  que un método puede nombrarlos directamente además de usar `this`.

`Environment` mantiene el estado del recorrido: ámbito actual, función actual,
clase actual, profundidad de bucles y profundidad de `switch`. Las fases 4 y
posteriores lo consultan para validar `return`, `break`, `continue` y `this`.

### Closures

Cuando `Environment.resolve` encuentra un nombre en un ámbito que pertenece a
otra función, registra la captura en todas las funciones intermedias de la
pila. Así una función anidada declara explícitamente qué variables del entorno
de definición necesita.

## Pasadas semánticas

1. **`Collector`** registra en el ámbito global las clases y las firmas de las
   funciones de nivel superior. Primero los nombres de clase, después los
   padres, después los ciclos de herencia y por último los miembros. Registrar
   la firma antes de visitar el cuerpo es lo que permite recursión, recursión
   mutua y referencias hacia adelante.
2. **`Checker`** recorre los cuerpos, crea el árbol de ámbitos, inserta los
   símbolos, resuelve los identificadores y calcula el tipo de cada expresión.
   Las funciones y clases declaradas dentro de un bloque se registran aquí,
   cuando el recorrido entra a su ámbito.

## Diagnósticos de esta fase

| Código | Significado |
| --- | --- |
| `SEM201` | Identificador no declarado |
| `SEM202` | Redeclaración en el mismo ámbito |
| `SEM203` | Parámetro duplicado |
| `SEM204` | Función duplicada en el mismo ámbito |
| `SEM205` | Clase duplicada |
| `SEM206` | Clase padre inexistente |
| `SEM207` | Ciclo de herencia |
| `SEM208` | Declaración sin tipo y sin inicializador |
| `SEM209` | Tipo desconocido en la anotación |
| `SEM210` | Parámetro sin anotación de tipo |
| `SEM211` | Miembro duplicado en la clase |

`DiagnosticBag` descarta duplicados exactos, de modo que un mismo error no se
reporta dos veces aunque el recorrido pase por el nodo más de una vez.

## Cómo verla

    ./.venv/Scripts/python.exe program/Driver.py program/program.cps --symbols text
    ./.venv/Scripts/python.exe program/Driver.py program/program.cps --format json --symbols json

La salida en texto imprime el árbol de ámbitos indentado; la salida JSON expone
`symbols.scopes` y `symbols.classes` para que la extensión de VS Code los pueda
consumir sin volver a analizar el archivo.

## Pruebas

    ./.venv/Scripts/python.exe -m unittest discover -s tests -v

`tests/test_symbols.py` cubre resolución global, resolución desde bloques
anidados, identificador no declarado, redeclaración, shadowing, parámetros
duplicados, funciones duplicadas, clases duplicadas, la creación de los seis
tipos de ámbito y la captura de variables por closures.
