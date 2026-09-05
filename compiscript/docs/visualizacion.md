# Visualización del árbol

Documento de la Fase 6. Describe el formato del árbol serializado y los tres
renderizadores construidos sobre él.

Todo vive en [`program/treeview.py`](../program/treeview.py) y se expone desde
el CLI con `--tree`.

## Formato del árbol

`treeview.serialize(tree, parser, types, diagnostics)` convierte el parse tree
de ANTLR en una estructura JSON enriquecida con lo que produjo la fase
semántica.

Nodo de regla:

```json
{
  "kind": "rule",
  "name": "variableDeclaration",
  "line": 2,
  "column": 1,
  "type": "integer",
  "children": [ ... ]
}
```

Nodo terminal:

```json
{ "kind": "token", "text": "total", "line": 2, "column": 5 }
```

Campos:

| Campo | Significado |
| --- | --- |
| `kind` | `rule` o `token` |
| `name` | Nombre de la regla de la gramática |
| `text` | Texto del token terminal |
| `line`, `column` | Posición base 1, igual que los diagnósticos |
| `type` | Tipo inferido por el analizador; solo en nodos de expresión |
| `noise` | `true` en la puntuación (`;`, `,`, `(`, `)`, `{`, `}`, `[`, `]`, `:`, `?`, `.`, `=`, `<EOF>`) |
| `diagnostic` | `{ code, severity, message }` del diagnóstico que cae en ese nodo |

Los tipos salen del recorrido semántico: el `Checker` guarda el tipo de cada
expresión que evalúa y el serializador los adjunta por identidad del nodo. En
el programa oficial eso son **994 nodos tipados**.

Un diagnóstico marca **un solo nodo**: el más interno que empieza en esa
posición. Sin esa regla, cada regla de la cadena de expresiones heredaría la
marca de su primer token y un solo error resaltaría una docena de nodos.

## Renderizador HTML

`treeview.render_html(nodo, título)` genera un documento **autónomo**: sin
scripts, hojas de estilo ni fuentes externas. Es el mismo documento que la
Fase 7 monta en el webview de VS Code y que puede abrirse directamente en un
navegador.

- Expandir y contraer con `<details>` / `<summary>` nativos. Los primeros tres
  niveles arrancan abiertos.
- Botones **Expandir todo**, **Contraer todo** y **Mostrar/ocultar puntuación**.
- La puntuación arranca oculta.
- Cada nodo muestra el nombre de la regla o el texto del token, el tipo
  inferido en cursiva y la posición `línea:columna`.
- Los nodos con diagnóstico se colorean según severidad y llevan una etiqueta
  con el código y el mensaje.
- El texto del programa se escapa, así que un literal como `"<b>hola</b>"` no
  puede inyectar HTML.

## Renderizador Graphviz (DOT)

`treeview.render_dot(nodo, hide_noise=True, max_depth=None)` produce el árbol en
el lenguaje **DOT**, para que Graphviz lo acomode con un algoritmo de verdad.
Es la representación visual recomendada.

El archivo `.dot` se genera **solo con la librería estándar**: el proyecto no
agrega dependencias. Graphviz hace falta únicamente para convertirlo en imagen.

    ./.venv/Scripts/python.exe program/Driver.py archivo.cps --tree dot --tree-out arbol.dot
    dot -Tpng arbol.dot -o arbol.png
    dot -Tsvg arbol.dot -o arbol.svg

Si no tienes Graphviz instalado, el `.dot` se puede pegar en cualquier visor en
línea o abrir con la extensión Graphviz de VS Code.

Convenciones del dibujo:

| Elemento | Aspecto |
| --- | --- |
| Nodo de regla | Caja redondeada azul, con el nombre de la regla |
| Tipo inferido | Segunda línea de la etiqueta, `: integer` |
| Posición | Última línea de la etiqueta, `línea:columna` |
| Token terminal | Elipse gris con el texto del token |
| Nodo con error | Relleno rojo y el código del diagnóstico |
| Nodo con advertencia | Relleno ámbar y el código del diagnóstico |
| Puntuación | Oculta por omisión |

### Compactar las cadenas de precedencia

La gramática recorre toda la escalera de precedencia aunque no haya ningún
operador: el literal `1` de `let total: integer = 1;` cuelga de doce reglas
seguidas (`expression` → `assignmentExpr` → `conditionalExpr` → `logicalOrExpr`
→ … → `literalExpr`). Esas reglas no aportan información y dominan el dibujo.

`--tree-compact` colapsa cada cadena de un solo hijo en su regla **más
específica**, la de más adentro, conservando el tipo, la posición y las marcas
de diagnóstico:

    ./.venv/Scripts/python.exe program/Driver.py archivo.cps --tree dot --tree-compact --tree-out arbol.dot

Efecto medido:

| Archivo | Nodos completos | Con `--tree-compact` |
| --- | ---: | ---: |
| `float_and_assignment.cps` | 128 | **49** |
| `program.cps` | 1 513 | **488** |

En el ejemplo pequeño la imagen pasa de 3 380 px de alto a 714. Las reglas con
varios hijos nunca se colapsan, así que `additiveExpr` con sus dos operandos y
su operador se conserva intacto.

La opción aplica a `dot`, `svg` y `html`. El JSON **no** se toca: es el contrato
que consume la extensión.

### Profundidad

El árbol completo del programa oficial tiene 1 513 nodos sin puntuación. Además
de compactar, se puede podar por niveles:

    ./.venv/Scripts/python.exe program/Driver.py program/program.cps --tree dot --tree-depth 6 --tree-out arbol.dot

Cada rama cortada se reemplaza por un nodo que dice cuántos descendientes se
omitieron, para que el dibujo no mienta. `--tree-depth` aplica a `dot`, `svg` y
`html`, y se puede combinar con `--tree-compact`; primero se compacta, de modo
que los niveles contados son los que de verdad se dibujan.

## Renderizador SVG

`treeview.render_svg(nodo)` produce una exportación estática sin depender de
ninguna herramienta externa. El acomodo es elemental: cada hoja ocupa una
columna y cada nodo interno se centra sobre sus hijos. Es el plan B cuando no
hay Graphviz disponible; con Graphviz, el DOT queda mucho mejor.

La puntuación se omite por defecto para que la imagen sea legible. Aun así, el
árbol completo del programa oficial mide unos 16 000 px de ancho: es una
exportación para revisar o imprimir por partes, no una vista de navegación. Para
explorar, usar el HTML.

## Uso desde el CLI

    # árbol como grafo, con Graphviz
    ./.venv/Scripts/python.exe program/Driver.py program/program.cps --tree dot --tree-depth 6 --tree-out arbol.dot
    dot -Tpng arbol.dot -o arbol.png

    # árbol interactivo en un archivo
    ./.venv/Scripts/python.exe program/Driver.py program/program.cps --tree html --tree-out arbol.html

    # exportación estática
    ./.venv/Scripts/python.exe program/Driver.py program/program.cps --tree svg --tree-out arbol.svg

    # JSON enriquecido, para la extensión o para inspección
    ./.venv/Scripts/python.exe program/Driver.py program/program.cps --tree json --tree-out arbol.json

    # notación Lisp de ANTLR
    ./.venv/Scripts/python.exe program/Driver.py program/program.cps --tree lisp

Sin `--tree-out` el árbol se imprime en la salida estándar. Con
`--format json`, el árbol JSON viaja dentro del payload en la clave `tree`.

## Comportamiento con archivos inválidos

- **Errores sintácticos**: el árbol se construye igual, pero la fase semántica
  no corre, así que no hay tipos ni marcas semánticas.
- **Errores semánticos recuperables**: el árbol se construye completo, con
  tipos, y cada error queda marcado en su nodo. `errores_multiples.cps` produce
  ocho marcas de error.
- **Advertencias**: se marcan igual que los errores, con otro color.

## Pruebas

`tests/test_treeview.py` cubre el serializador y los tres renderizadores:
nombres de regla, texto de terminales, posiciones, tipos inferidos, marcado de
diagnósticos, puntuación, escape de HTML, exportación SVG y el grafo DOT
—forma del `digraph`, formas y colores por tipo de nodo, escape de comillas y
poda por profundidad— y el compactado de cadenas de precedencia.
`tests/test_cli.py` cubre `--tree html`, `--tree svg`, `--tree dot`,
`--tree-compact`, `--tree-depth` y `--tree-out`.
