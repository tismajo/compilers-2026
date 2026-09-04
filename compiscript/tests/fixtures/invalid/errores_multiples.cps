// Errores semánticos recuperables: el análisis continúa y los reporta todos.
const LIMITE: integer = 3;
let texto: string = "hola";

let malInicializado: integer = "no soy un entero";
LIMITE = 4;
let resta: integer = texto - 1;
let comparacion: boolean = texto == 1;
print(desconocido);

function unParametro(a: integer): integer {
  return a;
}
unParametro();

class Caja {
  let valor: integer;
}
let caja: Caja = new Caja();
print(caja.inexistente);

continue;
