"""Structured diagnostics shared by every phase of the compiler.

The CLI, the test suite and the VS Code extension all consume the dictionary
produced by :meth:`Diagnostic.as_dict`, so the shape must stay stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

# Diagnostic code families.
#   LEX/SYN/CLI  frontend, emitted by Driver.py
#   SEM1xx       type system
#   SEM2xx       scopes and name resolution
#   SEM3xx       functions
#   SEM4xx       control flow
#   SEM5xx       classes and objects
#   SEM6xx       arrays and indexing
#   SEM7xx       dead code
CODES: dict[str, str] = {
    "SEM101": "Operandos inválidos en una operación aritmética",
    "SEM102": "Operandos no booleanos en una operación lógica",
    "SEM103": "Operando no booleano en la negación",
    "SEM104": "Comparación entre tipos incompatibles",
    "SEM105": "Asignación incompatible con el tipo del destino",
    "SEM106": "La condición debe ser boolean",
    "SEM107": "Ramas incompatibles en el operador ternario",
    "SEM108": "Reasignación de una constante",
    "SEM109": "Argumento no imprimible en 'print'",
    "SEM110": "El destino de la asignación no es asignable",
    "SEM201": "Identificador no declarado",
    "SEM202": "Redeclaración en el mismo ámbito",
    "SEM203": "Parámetro duplicado",
    "SEM204": "Función duplicada en el mismo ámbito",
    "SEM205": "Clase duplicada",
    "SEM206": "Clase padre inexistente",
    "SEM207": "Ciclo de herencia",
    "SEM208": "Declaración sin tipo y sin inicializador",
    "SEM209": "Tipo desconocido en la anotación",
    "SEM210": "Parámetro sin anotación de tipo",
    "SEM211": "Miembro duplicado en la clase",
    "SEM301": "Número de argumentos incorrecto",
    "SEM302": "Tipo de argumento incompatible",
    "SEM303": "Retorno incompatible con la firma",
    "SEM304": "'return' fuera de una función",
    "SEM305": "La función puede terminar sin retornar un valor",
    "SEM306": "El valor llamado no es una función",
    "SEM401": "'break' fuera de un ciclo o 'switch'",
    "SEM402": "'continue' fuera de un ciclo",
    "SEM403": "'foreach' necesita un arreglo",
    "SEM404": "Caso incompatible con la expresión del 'switch'",
    "SEM405": "Caso duplicado en el 'switch'",
    "SEM501": "La clase instanciada no existe",
    "SEM502": "El miembro no existe en la clase",
    "SEM503": "'this' fuera de un método o constructor",
    "SEM504": "Argumentos incorrectos en el constructor",
    "SEM505": "La sobrescritura no respeta la firma heredada",
    "SEM506": "El valor no tiene miembros accesibles con '.'",
    "SEM601": "El índice debe ser integer",
    "SEM602": "El valor indexado no es un arreglo",
    "SEM603": "Elementos heterogéneos en el literal de arreglo",
    "SEM604": "Índice literal fuera de rango (advertencia)",
    "SEM701": "Código inalcanzable (advertencia)",
}


@dataclass(frozen=True)
class Diagnostic:
    code: str
    phase: str
    severity: str
    message: str
    line: int
    column: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "phase": self.phase,
            "severity": self.severity,
            "message": self.message,
            "line": self.line,
            "column": self.column,
        }


@dataclass
class DiagnosticBag:
    """Collects diagnostics in source order and keeps them de-duplicated."""

    phase: str = "semantic"
    items: list[Diagnostic] = field(default_factory=list)
    _seen: set[tuple[str, int, int, str]] = field(default_factory=set, repr=False)

    def add(
        self,
        code: str,
        message: str,
        line: int,
        column: int,
        severity: str = SEVERITY_ERROR,
    ) -> None:
        key = (code, line, column, message)
        if key in self._seen:
            return
        self._seen.add(key)
        self.items.append(
            Diagnostic(
                code=code,
                phase=self.phase,
                severity=severity,
                message=message,
                line=line,
                column=column,
            )
        )

    def warn(self, code: str, message: str, line: int, column: int) -> None:
        self.add(code, message, line, column, SEVERITY_WARNING)

    @property
    def errors(self) -> list[Diagnostic]:
        return [item for item in self.items if item.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [item for item in self.items if item.severity == SEVERITY_WARNING]

    def sorted_items(self) -> list[Diagnostic]:
        return sorted(self.items, key=lambda item: (item.line, item.column, item.code))
