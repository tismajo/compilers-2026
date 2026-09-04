// Programa completo válido: cubre todas las áreas del análisis semántico.
const LIMITE: integer = 3;
let saludo: string = "Compiscript";
let activo: boolean = true;
let numeros: integer[] = [1, 2, 3];
let matriz: integer[][] = [[1, 2], [3, 4]];
let promedio: float = 1 + 1.5;

function sumar(a: integer, b: integer): integer {
  return a + b;
}

function factorial(n: integer): integer {
  if (n <= 1) {
    return 1;
  }
  return n * factorial(n - 1);
}

function acumulador(): integer {
  let total: integer = 0;
  function paso(valor: integer): integer {
    return total + valor;
  }
  return paso(1);
}

class Animal {
  let nombre: string;

  function constructor(nombre: string) {
    this.nombre = nombre;
  }

  function hablar(): string {
    return this.nombre + " hace ruido.";
  }
}

class Perro : Animal {
  function hablar(): string {
    return this.nombre + " ladra.";
  }
}

let perro: Perro = new Perro("Rex");
let mascota: Animal = perro;
print(perro.hablar());
print(mascota.nombre);

let total: integer = sumar(2, 3);
print("total = " + total);
print("factorial = " + factorial(LIMITE));
print("acumulado = " + acumulador());

numeros[0] = 10;
print(numeros[0]);
print(matriz[1][0]);

if (total > 4) {
  print("mayor");
} else {
  print("menor o igual");
}

while (total < 10) {
  total = total + 1;
}

do {
  total = total - 1;
} while (total > 5);

for (let i: integer = 0; i < LIMITE; i = i + 1) {
  print("indice " + i);
}

foreach (n in numeros) {
  if (n == 2) {
    continue;
  }
  if (n > 9) {
    break;
  }
  print("n = " + n);
}

switch (total) {
  case 5:
    print("cinco");
    break;
  case 6:
    print("seis");
  default:
    print("otro");
}

try {
  print("intento");
} catch (err) {
  print("error: " + err);
}

let etiqueta: string = activo ? "si" : "no";
print(etiqueta + " / " + promedio);
