# Video

[Link al video](https://youtu.be/ffRXo1Cn4B0)

# 🧪 Compiscript

## 📋 Descripción General

Este lenguaje se encuentra basado en Typescript, por lo que representa un subset del mismo, con algunas diferencias.

---

## 🧰 Instrucciones de Configuración

1. **Construir y Ejecutar el Contenedor Docker:** Desde el directorio raíz, ejecuta el siguiente comando para construir la imagen y lanzar un contenedor interactivo:

   ```bash
   docker build --rm . -t csp-image && docker run --rm -ti -v "$(pwd)/program":/program csp-image
   ```
2. **Entender el Entorno**

   - El directorio `program` se monta dentro del contenedor.
   - Este contiene la **gramática de ANTLR de Compiscript y una versión en BNF**, un archivo `Driver.py` (punto de entrada principal) y un archivo `program.cps` (entrada de prueba con la extensión de archivos de Compiscript).
3. **Generar Archivos de Lexer y Parser:** Dentro del contenedor, compila la gramática ANTLR a Python con:

   ```bash
   antlr -Dlanguage=Python3 Compiscript.g4
   ```
4. **Ejecutar el Analizador**
   Usa el driver para analizar el archivo de prueba:

   ```bash
   python3 Driver.py program.cps
   ```

   - ✅ Si el archivo es sintácticamente correcto, **no se mostrará ningún resultado**.
   - ❌ Si existen errores, ANTLR los mostrará en la consola.

---

## 🧩 Características del Lenguaje

Compiscript soporta los siguientes conceptos fundamentales:

### ✅ Tipos de Datos

```cps
let a: integer = 10;
let b: string = "hola";
let c: boolean = true;
let d = null;
```

### ✅ Literales

```cps
123          // integer
"texto"      // string
true, false  // boolean
null         // nulo
```

### ✅ Expresiones Aritméticas y Lógicas

```cps
let x = 5 + 3 * 2;
let y = !(x < 10 || x > 20);
```

### ✅ Precedencia y Agrupamiento

```cps
let z = (1 + 2) * 3;
```

### ✅ Declaración y Asignación de Variables

```cps
let nombre: string;
nombre = "Compiscript";
```

### ✅ Constantes (`const`)

```cps
const PI: integer = 314;
```

### ✅ Funciones y Parámetros

```cps
function saludar(nombre: string): string {
  return "Hola " + nombre;
}
```

### ✅ Expresiones de Llamada

```cps
let mensaje = saludar("Mundo");
```

### ✅ Acceso a Propiedades (`.`)

```cps
print(dog.nombre);
```

### ✅ Acceso a Elementos de Arreglo (`[]`)

```cps
let lista = [1, 2, 3];
print(lista[0]);
```

### ✅ Arreglos

```cps
let notas: integer[] = [90, 85, 100];
let matriz: integer[][] = [[1, 2], [3, 4]];
```

### ✅ Funciones como Closures

```cps
function crearContador(): integer {
  function siguiente(): integer {
    return 1;
  }
  return siguiente();
}
```

### ✅ Clases y Constructores

```cps
class Animal {
  let nombre: string;

  function constructor(nombre: string) {
    this.nombre = nombre;
  }

  function hablar(): string {
    return this.nombre + " hace ruido.";
  }
}
```

### ✅ Herencia

```cps
class Perro : Animal {
  function hablar(): string {
    return this.nombre + " ladra.";
  }
}
```

### ✅ `this`

```cps
this.nombre = "Firulais";
```

### ✅ Instanciación con `new`

```cps
let perro: Perro = new Perro("Toby");
```

### ✅ Bloques y Ámbitos

```cps
{
  let x = 42;
  print(x);
}
```

### ✅ Control de Flujo

#### `if` / `else`

```cps
if (x > 10) {
  print("Mayor a 10");
} else {
  print("Menor o igual");
}
```

#### `while`

```cps
while (x < 5) {
  x = x + 1;
}
```

#### `do-while`

```cps
do {
  x = x - 1;
} while (x > 0);
```

#### `for`

```cps
for (let i: integer = 0; i < 3; i = i + 1) {
  print(i);
}
```

#### `foreach`

```cps
foreach (item in lista) {
  print(item);
}
```

#### `break` / `continue`

```cps
foreach (n in notas) {
  if (n < 60) continue;
  if (n == 100) break;
  print(n);
}
```

### ✅ `switch / case`

```cps
switch (x) {
  case 1:
    print("uno");
  case 2:
    print("dos");
  default:
    print("otro");
}
```

### ✅ `try / catch`

```cps
try {
  let peligro = lista[100];
} catch (err) {
  print("Error atrapado: " + err);
}
```

### ✅ `return`

```cps
function suma(a: integer, b: integer): integer {
  return a + b;
}
```

### ✅ Recursión

```cps
function factorial(n: integer): integer {
  if (n <= 1) return 1;
  return n * factorial(n - 1);
}
```

---

## 📦 Extensión de Archivo

Todos los archivos fuente de Compiscript deben usar la extensión:

```bash
program.cps
```

---

## Documentación

| Documento | Contenido |
| --- | --- |
| [`docs/arquitectura.md`](docs/arquitectura.md) | Componentes, flujo de compilación, diagramas y estructura del parse tree |
| [`docs/uso.md`](docs/uso.md) | Guía completa: requisitos, instalación, Docker, CLI, pruebas y ejemplos |
| [`docs/tabla-de-simbolos.md`](docs/tabla-de-simbolos.md) | Modelo de tipos, símbolos, ámbitos y las dos pasadas |
| [`docs/reglas-semanticas.md`](docs/reglas-semanticas.md) | Catálogo de los 35 diagnósticos y las reglas que los producen |
| [`docs/visualizacion.md`](docs/visualizacion.md) | Formato del árbol y renderizadores HTML y SVG |
| [`docs/pruebas.md`](docs/pruebas.md) | Organización de la suite, fixtures, cobertura e integración continua |
| [`docs/decisiones.md`](docs/decisiones.md) | Contradicciones del enunciado y qué se decidió en cada caso |
| [`extension/README.md`](extension/README.md) | Instalación, configuración y comandos del IDE |

## Frontend sintáctico

La gramática genera Lexer, Parser, Listener y Visitor para Python. Los archivos
generados están incluidos en `program`, pero pueden regenerarse con:

```bash
cd program
antlr -Dlanguage=Python3 -visitor Compiscript.g4
```

Instale primero el runtime cuya versión coincide con el JAR del proyecto:

```bash
pip install -r requirements.txt
```

Analice un archivo y obtenga diagnósticos legibles:

```bash
python3 program/Driver.py program/program.cps
```

La salida JSON está pensada para la extensión de VS Code:

```bash
python3 program/Driver.py program/program.cps --format json
```

También se puede incluir el parse tree en formato Lisp o JSON:

```bash
python3 program/Driver.py program/program.cps --format json --tree json
```

El proceso retorna `0` cuando el archivo es válido, `1` cuando existen errores
léxicos, sintácticos o semánticos, y `2` cuando no se puede abrir el archivo
solicitado.

## Análisis semántico

El análisis semántico se ejecuta automáticamente cuando el archivo no tiene
errores sintácticos, sobre el mismo parse tree, sin volver a analizarlo. Para
detenerse en la fase sintáctica:

```bash
python3 program/Driver.py program/program.cps --no-semantic
```

La tabla de símbolos se puede imprimir de forma legible o en JSON:

```bash
python3 program/Driver.py program/program.cps --symbols text
python3 program/Driver.py program/program.cps --format json --symbols json
```

## IDE: extensión de VS Code

La extensión vive en [`extension/`](extension/) y convierte a VS Code en el IDE
del lenguaje: resaltado de sintaxis, diagnósticos en el panel *Problems*, árbol
sintáctico interactivo y tabla de símbolos.

```bash
cd extension
npm install
npm run compile
npm run package                                  # genera compiscript-0.1.0.vsix
code --install-extension compiscript-0.1.0.vsix
```

La extensión invoca este mismo `Driver.py`; **Docker no es necesario**. En
Windows conviene apuntar al entorno virtual del repositorio:

```json
{ "compiscript.pythonPath": "${workspaceFolder}/.venv/Scripts/python.exe" }
```

La instalación, la configuración y los comandos están documentados en
[`extension/README.md`](extension/README.md).

## Visualización del árbol

El árbol puede exportarse como documento HTML interactivo, como SVG o como JSON
enriquecido con los tipos inferidos y las marcas de diagnóstico:

```bash
# grafo con Graphviz (representación visual recomendada)
python3 program/Driver.py program/program.cps --tree dot --tree-compact --tree-out arbol.dot
dot -Tpng arbol.dot -o arbol.png

python3 program/Driver.py program/program.cps --tree html --tree-out arbol.html
python3 program/Driver.py program/program.cps --tree svg --tree-out arbol.svg
python3 program/Driver.py program/program.cps --tree json --tree-out arbol.json
```

El `.dot` lo genera el compilador con la librería estándar, sin dependencias
nuevas; Graphviz solo hace falta para convertirlo en imagen.

El formato y los renderizadores están descritos en
[`docs/visualizacion.md`](docs/visualizacion.md).

El modelo de tipos, los ámbitos y las dos pasadas están documentados en
[`docs/tabla-de-simbolos.md`](docs/tabla-de-simbolos.md). El catálogo completo
de reglas y diagnósticos está en
[`docs/reglas-semanticas.md`](docs/reglas-semanticas.md).

### Pruebas

Desde la raíz del proyecto ejecute:

```bash
python3 -m unittest discover -s tests -v
```

`tests/test_grammar.py` valida la gramática directamente con Java y el JAR
incluido, `tests/test_syntax.py` el frontend Python, `tests/test_cli.py` los
códigos y formatos de salida, y `tests/rules/` la batería semántica completa,
con al menos un caso exitoso y uno fallido por regla.

El reporte de cobertura usa solo la librería estándar:

```bash
python3 tests/coverage_report.py
```

La organización de la suite y la convención de fixtures están en
[`docs/pruebas.md`](docs/pruebas.md).
