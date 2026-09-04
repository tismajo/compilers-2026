// Un error representativo de cada grupo semántico.
// Se usa en la demostración final de la entrega.

// SEM2xx - ámbitos y declaraciones: identificador no declarado.
print(noDeclarado);

// SEM1xx - sistema de tipos: operandos inválidos en una resta.
let suma: integer = true - 1;

// SEM3xx - funciones: número de argumentos incorrecto.
function unico(a: integer): integer {
  return a;
}
unico();

// SEM5xx - clases: miembro inexistente.
class Caja {
  let valor: integer;
}
let caja: Caja = new Caja();
print(caja.inexistente);

// SEM6xx - arreglos: índice que no es integer.
let numeros: integer[] = [1, 2, 3];
print(numeros["x"]);

// SEM7xx - código muerto (advertencia).
function conCodigoMuerto(): integer {
  return 1;
  print("inalcanzable");
}

// SEM4xx - control de flujo: continue fuera de un ciclo.
// Va al final porque interrumpe el flujo del programa.
continue;
