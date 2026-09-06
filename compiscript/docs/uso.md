# Guía de uso

Documento de la Fase 8. Todo lo necesario para instalar, ejecutar y probar el
compilador desde cero.

## Requisitos previos

| Herramienta | Versión | Para qué |
| --- | --- | --- |
| Python | 3.10 o superior | Ejecutar el compilador |
| `antlr4-python3-runtime` | 4.13.1 | Runtime del parser generado |
| Java | 17 o superior | Regenerar el parser y correr `tests/test_grammar.py` |
| Node y npm | 20 o superior | Solo para la extensión de VS Code |
| Docker | opcional | Entorno alterno; **no es obligatorio** |

El JAR de ANTLR viene incluido en el repositorio:
`antlr-4.13.1-complete.jar`.

## Instalación local

```bash
git clone https://github.com/tismajo/compilers-2026.git
cd compilers-2026/compiscript

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

En Windows, sin activar el entorno, se puede invocar directamente
`./.venv/Scripts/python.exe`. Los ejemplos de esta guía usan `python3`.

## Ejecución con Docker

Docker es una alternativa, no un requisito. Desde `compiscript/`:

```bash
docker build --rm . -t csp-image
docker run --rm -ti -v "$(pwd)/program":/program csp-image
```

Ese montaje solo expone `program/`, así que dentro del contenedor se puede
analizar y regenerar el parser, pero **no correr la suite**. Para eso hay que
montar el proyecto completo:

```bash
docker run --rm -ti -v "$(pwd)":/proyecto -w /proyecto csp-image
python3 -m unittest discover -s tests -v
```

Dentro del contenedor quedan disponibles Java 17, Python con el runtime
instalado y el JAR de ANTLR. La extensión de VS Code **no** usa Docker.

> Los wrappers `antlr` y `grun` están guardados con fin de línea CRLF y el
> kernel del contenedor los rechaza. Mientras no se conviertan a LF, dentro del
> contenedor hay que invocar el JAR directamente:
> `java -jar /usr/local/lib/antlr-4.13.1-complete.jar -Dlanguage=Python3 -visitor Compiscript.g4`

## Regenerar el parser

Solo hace falta si se modifica `Compiscript.g4`. Desde `program/`:

```bash
java -jar ../antlr-4.13.1-complete.jar -Dlanguage=Python3 -visitor Compiscript.g4
```

Dentro del contenedor de Docker:

```bash
antlr -Dlanguage=Python3 -visitor Compiscript.g4
```

Genera `CompiscriptLexer.py`, `CompiscriptParser.py`, `CompiscriptListener.py`,
`CompiscriptVisitor.py` y los archivos `.interp` y `.tokens`. **Nunca se editan
a mano.**

## Uso del CLI

```bash
python3 program/Driver.py program/program.cps
```

Sin errores no imprime nada y termina con código `0`. Con errores los escribe
en la salida de error:

    archivo.cps:8:22: error SEM101: El operador '-' necesita operandos numéricos, no string y integer

### Opciones

| Opción | Valores | Efecto |
| --- | --- | --- |
| `--format` | `text`, `json` | Formato de los diagnósticos. `json` es el que consume la extensión |
| `--tree` | `none`, `lisp`, `json`, `html`, `svg`, `dot` | Incluye el árbol sintáctico |
| `--tree-compact` | — | Colapsa las cadenas de precedencia de la gramática |
| `--tree-depth` | entero | Poda el árbol por niveles |
| `--tree-out` | ruta | Escribe el árbol en un archivo en vez de imprimirlo |
| `--symbols` | `none`, `text`, `json` | Incluye la tabla de símbolos |
| `--no-semantic` | — | Se detiene en la fase sintáctica |

### Códigos de salida

| Código | Significado |
| ---: | --- |
| `0` | Sin errores. Las advertencias no lo cambian |
| `1` | Errores léxicos, sintácticos o semánticos |
| `2` | El archivo no existe |

### Formatos de salida

Diagnósticos en JSON, listos para cualquier editor:

```bash
python3 program/Driver.py program/program.cps --format json
```

```json
{
  "success": true,
  "source": "program/program.cps",
  "phase": "semantic",
  "diagnostics": [
    {
      "code": "SEM604",
      "phase": "semantic",
      "severity": "warning",
      "message": "El índice 10 queda fuera del arreglo de 5 elementos...",
      "line": 58,
      "column": 32
    }
  ]
}
```

Las líneas y las columnas son **base 1**. La API de VS Code es base 0, así que
la extensión resta 1 a cada una.

Tabla de símbolos legible o en JSON:

```bash
python3 program/Driver.py program/program.cps --symbols text
python3 program/Driver.py program/program.cps --format json --symbols json
```

## Visualización del árbol

```bash
python3 program/Driver.py program/program.cps --tree dot --tree-compact --tree-out arbol.dot
dot -Tpng arbol.dot -o arbol.png          # requiere Graphviz instalado

python3 program/Driver.py program/program.cps --tree html --tree-out arbol.html
python3 program/Driver.py program/program.cps --tree svg  --tree-out arbol.svg
python3 program/Driver.py program/program.cps --tree json --tree-out arbol.json
python3 program/Driver.py program/program.cps --tree lisp
```

`--tree dot` es la representación visual recomendada: genera el grafo en
formato Graphviz y `dot` lo acomoda. El archivo `.dot` lo produce el compilador
con la librería estándar; Graphviz solo hace falta para convertirlo en imagen.

`--tree-compact` colapsa las cadenas de precedencia de la gramática, que no
aportan información y triplican el tamaño del dibujo: el programa oficial pasa
de 1 513 nodos a 488. `--tree-depth N` poda por niveles y se puede combinar.

El HTML es un documento autónomo: se abre en cualquier navegador, permite
expandir y contraer nodos, mostrar u ocultar la puntuación, y resalta los nodos
con diagnóstico. Detalles en [visualización](visualizacion.md).

## Ejecución de pruebas

```bash
python3 -m unittest discover -s tests -v
```

190 pruebas: gramática con Java, frontend sintáctico, CLI, serializador del
árbol y la batería semántica completa en `tests/rules/`.

Reporte de cobertura, sin dependencias adicionales:

```bash
python3 tests/coverage_report.py
```

La organización de la suite está en [pruebas](pruebas.md).

## Extensión de VS Code

```bash
cd extension
npm install
npm run compile
npm run package
code --install-extension compiscript-0.1.0.vsix
```

Configuración mínima en Windows, apuntando al entorno virtual del repositorio:

```json
{
  "compiscript.pythonPath": "${workspaceFolder}/.venv/Scripts/python.exe",
  "compiscript.compilerPath": "${workspaceFolder}/program/Driver.py"
}
```

Comandos disponibles en la paleta: **Compiscript: Analizar archivo**,
**Compiscript: Mostrar árbol** y **Compiscript: Mostrar tabla de símbolos**.
Los errores aparecen en el panel *Problems* con su código y su ubicación. Ver
[`extension/README.md`](../extension/README.md).

## Ejemplos

### Programa válido

`program/program.cps` es el ejemplo oficial: clases, herencia, closures,
`switch`, `try/catch`, arreglos y recursión. Produce una sola advertencia,
`SEM604`, por el `numbers[10]` que el propio ejemplo hace a propósito.

`tests/fixtures/valid/programa_completo.cps` recorre todas las áreas del
análisis y no produce ningún diagnóstico:

```bash
python3 program/Driver.py tests/fixtures/valid/programa_completo.cps
```

### Programas inválidos

| Archivo | Qué demuestra |
| --- | --- |
| `tests/fixtures/invalid/missing_semicolon.cps` | Error sintáctico `SYN001` |
| `tests/fixtures/invalid/unknown_character.cps` | Error léxico `LEX001` |
| `tests/fixtures/invalid/errores_multiples.cps` | Ocho errores semánticos recuperables |
| `tests/fixtures/invalid/muestra_por_grupo.cps` | Un error de **cada** grupo semántico |

```bash
python3 program/Driver.py tests/fixtures/invalid/muestra_por_grupo.cps
```

    5:7:  error   SEM201: 'noDeclarado' no ha sido declarado
    8:28: error   SEM101: El operador '-' necesita operandos numéricos...
    14:1: error   SEM301: 'unico' espera 1 argumentos y recibió 0
    21:11:error   SEM502: 'inexistente' no existe en la clase 'Caja'
    25:15:error   SEM601: El índice debe ser integer, no string
    30:3: warning SEM701: Código inalcanzable...
    35:1: error   SEM402: 'continue' solo puede usarse dentro de un ciclo

El catálogo completo de códigos está en
[reglas semánticas](reglas-semanticas.md).
