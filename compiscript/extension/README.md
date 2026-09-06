# Compiscript para VS Code

IDE del compilador de Compiscript: resaltado de sintaxis, análisis semántico en
el panel *Problems*, árbol sintáctico interactivo y tabla de símbolos.

La extensión no incluye el compilador: invoca el `Driver.py` de este mismo
repositorio con un intérprete de Python. **Docker no es necesario.**

## Requisitos

- Python 3.10 o superior con `antlr4-python3-runtime==4.13.1` instalado.
- El compilador de este repositorio (`program/Driver.py`).

## Instalación desde el `.vsix`

```bash
cd extension
npm install
npm run compile
npm run package          # genera compiscript-0.1.0.vsix
code --install-extension compiscript-0.1.0.vsix
```

## Configuración

| Opción | Valor por defecto | Para qué sirve |
| --- | --- | --- |
| `compiscript.pythonPath` | `python3` | Intérprete de Python. Acepta rutas absolutas y `${workspaceFolder}`. |
| `compiscript.compilerPath` | `${workspaceFolder}/program/Driver.py` | Ruta del `Driver.py`. |
| `compiscript.analyzeOnSave` | `true` | Analizar automáticamente al guardar. |
| `compiscript.showSummary` | `true` | Mostrar el resumen en la barra de estado y en el panel de salida. |

En Windows, con el entorno virtual del repositorio:

```json
{
  "compiscript.pythonPath": "${workspaceFolder}/.venv/Scripts/python.exe"
}
```

Las rutas con espacios funcionan sin comillas: cada argumento viaja por
separado y el proceso se lanza sin shell.

## Comandos

| Comando | Qué hace |
| --- | --- |
| `Compiscript: Analizar archivo` | Analiza el archivo activo y publica los diagnósticos. |
| `Compiscript: Mostrar árbol` | Abre el árbol sintáctico interactivo en un panel. |
| `Compiscript: Mostrar tabla de símbolos` | Abre la tabla de símbolos por ámbitos. |

Los tres aparecen en la paleta de comandos, y los dos primeros también en el
menú contextual de un archivo `.cps`.

## Diagnósticos

Los errores y las advertencias del compilador aparecen en el panel *Problems*
con su código (`LEX001`, `SYN001`, `SEM101`…), su mensaje y su ubicación
exacta. Las advertencias, como `SEM604` o `SEM701`, se distinguen de los
errores y no impiden que el análisis se considere exitoso.

Los diagnósticos se reemplazan en cada análisis y se borran al cerrar el
archivo, así que nunca quedan marcas obsoletas.

## Desarrollo

```bash
npm run compile   # compila TypeScript a out/
npm run lint      # verificación estricta de tipos, sin emitir
npm test          # pruebas del contrato y de la integración con el compilador
```

Las pruebas de integración ejecutan el compilador real; se omiten solas si no
encuentran un Python con el runtime de ANTLR.
