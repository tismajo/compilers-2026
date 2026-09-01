"""Second semantic pass: scopes, declarations, name resolution and type rules.

The walk creates the scope tree, inserts symbols, resolves identifiers, types
every expression and applies the semantic rules of the language. Scope-related
diagnostics use the ``SEM2xx`` family; the type, function, control-flow, class,
array and dead-code rules use ``SEM1xx`` and ``SEM3xx``-``SEM7xx``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from CompiscriptParser import CompiscriptParser
from CompiscriptVisitor import CompiscriptVisitor

from .annotations import TypeResolver, position
from .collector import Collector
from .diagnostics import DiagnosticBag
from .scopes import ScopeKind
from .symbol_table import SymbolTable
from .symbols import (
    ClassSymbol,
    ConstantSymbol,
    FunctionSymbol,
    Symbol,
    SymbolCategory,
    VariableSymbol,
)
from .types import (
    BOOLEAN,
    ERROR,
    FLOAT,
    INTEGER,
    NULL,
    STRING,
    VOID,
    ArrayType,
    ClassType,
    FunctionType,
    Type,
    arithmetic_result,
    common_type,
    is_assignable,
    is_comparable,
    is_numeric,
    is_printable,
)


@dataclass
class Target:
    """Result of walking a ``leftHandSide``: its type plus what it points to."""

    type: Type
    kind: str = "value"
    symbol: Optional[Symbol] = None
    length: Optional[int] = None
    line: int = 0
    column: int = 0


class Checker(CompiscriptVisitor):
    def __init__(
        self,
        table: SymbolTable,
        bag: DiagnosticBag,
        declared: Optional[dict[int, Symbol]] = None,
    ) -> None:
        self.table = table
        self.bag = bag
        self.declared = declared if declared is not None else {}
        self.env = table.environment
        self.resolver = TypeResolver(table.classes, bag)
        self.builder = Collector(table, bag)
        # ``id(ctx) -> type name`` for every expression, consumed by the tree
        # visualization so it can label nodes with their inferred type.
        self.types: dict[int, str] = {}

    def visit(self, tree: Any) -> Any:
        result = super().visit(tree)
        if isinstance(result, Type):
            self.types[id(tree)] = str(result)
        return result

    # -- entry point ----------------------------------------------------
    def run(self, program_ctx: Any) -> None:
        self._walk_statements(program_ctx.statement())

    # ------------------------------------------------------------------
    # Declarations
    # ------------------------------------------------------------------
    def visitVariableDeclaration(self, ctx: CompiscriptParser.VariableDeclarationContext):
        self._declare_value(ctx, constant=False)
        return None

    def visitConstantDeclaration(self, ctx: CompiscriptParser.ConstantDeclarationContext):
        self._declare_value(ctx, constant=True)
        return None

    def _declare_value(self, ctx: Any, constant: bool) -> Symbol:
        name_node = ctx.Identifier()
        name = name_node.getText()
        line, column = position(name_node)

        annotation = ctx.typeAnnotation()
        declared_type = (
            self.resolver.resolve(annotation.type_()) if annotation is not None else None
        )

        if constant:
            # The grammar already forces ``const`` to carry an initializer.
            value_ctx = ctx.expression()
        else:
            initializer = ctx.initializer()
            value_ctx = initializer.expression() if initializer is not None else None
        value_type = self.visit(value_ctx) if value_ctx is not None else None

        if declared_type is None and value_type is None:
            self.bag.add(
                "SEM208",
                f"'{name}' necesita una anotación de tipo o un inicializador",
                line,
                column,
            )
            final_type: Type = ERROR
        elif declared_type is None:
            final_type = value_type  # type: ignore[assignment]
        else:
            final_type = declared_type
            if value_type is not None and not is_assignable(declared_type, value_type):
                value_line, value_column = position(value_ctx)
                self.bag.add(
                    "SEM105",
                    f"No se puede inicializar '{name}' de tipo {declared_type} "
                    f"con un valor de tipo {value_type}",
                    value_line,
                    value_column,
                )

        factory = ConstantSymbol if constant else VariableSymbol
        symbol = factory(
            name=name,
            type=final_type,
            line=line,
            column=column,
            initialized=value_ctx is not None,
        )
        symbol.length = self._literal_length(value_ctx)  # type: ignore[attr-defined]
        clash = self.env.define(symbol)
        if clash is not None:
            self.bag.add(
                "SEM202",
                f"'{name}' ya fue declarado en la línea {clash.line}",
                line,
                column,
            )
        return symbol

    def visitFunctionDeclaration(self, ctx: CompiscriptParser.FunctionDeclarationContext):
        symbol = self.declared.get(id(ctx))
        if symbol is None:
            symbol = self._declare_nested_function(ctx)
        self._walk_function_body(symbol, ctx)
        return None

    def _declare_nested_function(self, ctx: Any) -> FunctionSymbol:
        name_node = ctx.Identifier()
        name = name_node.getText()
        line, column = position(name_node)
        symbol = FunctionSymbol(name=name, line=line, column=column)
        self.builder.fill_signature(symbol, ctx)
        symbol.type = symbol.signature
        clash = self.env.define(symbol)
        if clash is not None:
            code = "SEM204" if clash.category.value in ("function", "method") else "SEM202"
            self.bag.add(
                code,
                f"'{name}' ya fue declarado en la línea {clash.line}",
                line,
                column,
            )
        self.declared[id(ctx)] = symbol
        return symbol

    def _walk_function_body(self, symbol: FunctionSymbol, ctx: Any) -> None:
        line, column = position(ctx)
        scope = self.env.push(
            ScopeKind.FUNCTION,
            symbol.name,
            line,
            column,
            function_owner=symbol,
        )
        symbol.body_scope = scope
        self.env.function_stack.append(symbol)
        # A loop never crosses a function boundary.
        outer_loop, outer_switch = self.env.loop_depth, self.env.switch_depth
        self.env.loop_depth = 0
        self.env.switch_depth = 0
        for parameter in symbol.parameters:
            scope.define(parameter)
        # Parameters and body share one scope on purpose, so a local variable
        # that shadows a parameter is reported as a redeclaration.
        terminates = self._walk_statements(ctx.block().statement())
        self.env.loop_depth, self.env.switch_depth = outer_loop, outer_switch
        self.env.function_stack.pop()
        self.env.pop()

        if symbol.return_type not in (VOID, ERROR) and not terminates:
            self.bag.add(
                "SEM305",
                f"'{symbol.name}' declara retorno {symbol.return_type}, pero puede "
                f"terminar sin retornar un valor",
                symbol.line,
                symbol.column,
            )

    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        symbol = self.declared.get(id(ctx))
        if symbol is None:
            symbol = self._declare_nested_class(ctx)
        if symbol is None:
            return None

        line, column = position(ctx)
        scope = self.env.push(ScopeKind.CLASS, symbol.name, line, column)
        symbol.class_scope = scope
        self.env.class_stack.append(symbol)
        for attribute in symbol.attributes.values():
            scope.define(attribute)
        for method in symbol.methods.values():
            scope.define(method)

        for member in ctx.classMember():
            function_ctx = member.functionDeclaration()
            if function_ctx is not None:
                method = symbol.methods.get(function_ctx.Identifier().getText())
                if method is not None:
                    self._walk_function_body(method, function_ctx)
                continue
            declaration = member.variableDeclaration() or member.constantDeclaration()
            if declaration is not None:
                self._type_attribute(symbol, declaration)

        self.env.class_stack.pop()
        self.env.pop()
        return None

    def _declare_nested_class(self, ctx: Any) -> Optional[ClassSymbol]:
        """Register a class declared inside a block instead of at top level."""
        self.builder.declare_class(ctx)
        symbol = self.builder.declared.get(id(ctx))
        if symbol is None:
            return None
        self.builder.link_parent(ctx)
        self.builder.collect_members(ctx)
        self.builder.check_overrides()
        self.declared[id(ctx)] = symbol
        return symbol

    def _type_attribute(self, owner: ClassSymbol, ctx: Any) -> None:
        name = ctx.Identifier().getText()
        attribute = owner.attributes.get(name)
        if attribute is None:
            return
        value_ctx: Any = None
        if hasattr(ctx, "initializer") and ctx.initializer() is not None:
            value_ctx = ctx.initializer().expression()
        elif hasattr(ctx, "expression") and ctx.expression() is not None:
            value_ctx = ctx.expression()
        if value_ctx is None:
            return
        value_type = self.visit(value_ctx)
        if attribute.type.is_error:
            attribute.type = value_type
        elif not is_assignable(attribute.type, value_type):
            line, column = position(value_ctx)
            self.bag.add(
                "SEM105",
                f"No se puede inicializar el atributo '{name}' de tipo "
                f"{attribute.type} con un valor de tipo {value_type}",
                line,
                column,
            )
        attribute.initialized = True

    # ------------------------------------------------------------------
    # Statement walking and dead code
    # ------------------------------------------------------------------
    def _walk_statements(self, statements: list[Any]) -> bool:
        """Visit a statement list and report the first unreachable statement."""
        terminated = False
        reported = False
        for statement in statements:
            if terminated and not reported:
                line, column = position(statement)
                # Decision 5: dead code is a warning and does not fail the build.
                self.bag.warn(
                    "SEM701",
                    "Código inalcanzable: la ejecución ya terminó en esta rama",
                    line,
                    column,
                )
                reported = True
            self.visit(statement)
            if not terminated and self._terminates(statement):
                terminated = True
        return terminated

    def _terminates(self, ctx: Any) -> bool:
        """Whether a statement always transfers control out of its block."""
        if not isinstance(ctx, CompiscriptParser.StatementContext):
            return False
        if (
            ctx.returnStatement() is not None
            or ctx.breakStatement() is not None
            or ctx.continueStatement() is not None
        ):
            return True
        block = ctx.block()
        if block is not None:
            return self._list_terminates(block.statement())
        if_ctx = ctx.ifStatement()
        if if_ctx is not None:
            blocks = if_ctx.block()
            if len(blocks) == 2:
                return self._list_terminates(blocks[0].statement()) and (
                    self._list_terminates(blocks[1].statement())
                )
            return False
        try_ctx = ctx.tryCatchStatement()
        if try_ctx is not None:
            blocks = try_ctx.block()
            return self._list_terminates(blocks[0].statement()) and (
                self._list_terminates(blocks[1].statement())
            )
        switch_ctx = ctx.switchStatement()
        if switch_ctx is not None:
            default_case = switch_ctx.defaultCase()
            if default_case is None:
                return False
            cases = list(switch_ctx.switchCase()) + [default_case]
            return all(self._list_terminates(case.statement()) for case in cases)
        return False

    def _list_terminates(self, statements: list[Any]) -> bool:
        return any(self._terminates(statement) for statement in statements)

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------
    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        line, column = position(ctx)
        self.env.push(ScopeKind.BLOCK, f"block@{line}", line, column)
        self._walk_statements(ctx.statement())
        self.env.pop()
        return None

    def visitPrintStatement(self, ctx: CompiscriptParser.PrintStatementContext):
        value_type = self.visit(ctx.expression())
        if not is_printable(value_type):
            line, column = position(ctx.expression())
            self.bag.add(
                "SEM109",
                f"'print' no puede imprimir un valor de tipo {value_type}",
                line,
                column,
            )
        return None

    def visitExpressionStatement(self, ctx: CompiscriptParser.ExpressionStatementContext):
        self.visit(ctx.expression())
        return None

    def visitAssignment(self, ctx: CompiscriptParser.AssignmentContext):
        self._check_assignment(ctx.leftHandSide(), ctx.expression())
        return None

    def visitIfStatement(self, ctx: CompiscriptParser.IfStatementContext):
        self._require_boolean(ctx.expression(), "if")
        for block in ctx.block():
            self.visit(block)
        return None

    def visitWhileStatement(self, ctx: CompiscriptParser.WhileStatementContext):
        self._require_boolean(ctx.expression(), "while")
        self.env.loop_depth += 1
        self.visit(ctx.block())
        self.env.loop_depth -= 1
        return None

    def visitDoWhileStatement(self, ctx: CompiscriptParser.DoWhileStatementContext):
        self.env.loop_depth += 1
        self.visit(ctx.block())
        self.env.loop_depth -= 1
        self._require_boolean(ctx.expression(), "do-while")
        return None

    def visitForStatement(self, ctx: CompiscriptParser.ForStatementContext):
        line, column = position(ctx)
        self.env.push(ScopeKind.BLOCK, f"for@{line}", line, column)
        if ctx.variableDeclaration() is not None:
            self.visit(ctx.variableDeclaration())
        elif ctx.assignment() is not None:
            self.visit(ctx.assignment())
        condition_ctx, step_ctx = self._for_sections(ctx)
        if condition_ctx is not None:
            self._require_boolean(condition_ctx, "for")
        if step_ctx is not None:
            self.visit(step_ctx)
        self.env.loop_depth += 1
        self.visit(ctx.block())
        self.env.loop_depth -= 1
        self.env.pop()
        return None

    def _for_sections(self, ctx: Any) -> tuple[Any, Any]:
        """Split ``for`` into condition and step around its direct ``;``."""
        condition_ctx = None
        step_ctx = None
        passed_semicolon = False
        for index in range(ctx.getChildCount()):
            child = ctx.getChild(index)
            if isinstance(child, CompiscriptParser.ExpressionContext):
                if passed_semicolon:
                    step_ctx = child
                else:
                    condition_ctx = child
            elif child.getText() == ";":
                passed_semicolon = True
        return condition_ctx, step_ctx

    def visitForeachStatement(self, ctx: CompiscriptParser.ForeachStatementContext):
        iterable_type = self.visit(ctx.expression())
        name_node = ctx.Identifier()
        name = name_node.getText()
        line, column = position(name_node)
        element_type: Type = ERROR
        if isinstance(iterable_type, ArrayType):
            element_type = iterable_type.element
        elif not iterable_type.is_error:
            iterable_line, iterable_column = position(ctx.expression())
            self.bag.add(
                "SEM403",
                f"'foreach' necesita un arreglo, pero recibió {iterable_type}",
                iterable_line,
                iterable_column,
            )
        scope = self.env.push(ScopeKind.FOREACH, f"foreach@{line}", line, column)
        scope.define(
            VariableSymbol(
                name=name,
                type=element_type,
                line=line,
                column=column,
                initialized=True,
            )
        )
        self.env.loop_depth += 1
        self.visit(ctx.block())
        self.env.loop_depth -= 1
        self.env.pop()
        return None

    def visitTryCatchStatement(self, ctx: CompiscriptParser.TryCatchStatementContext):
        blocks = ctx.block()
        self.visit(blocks[0])
        name_node = ctx.Identifier()
        name = name_node.getText()
        line, column = position(name_node)
        scope = self.env.push(ScopeKind.CATCH, f"catch@{line}", line, column)
        # Decision 7: the catch variable is a string.
        scope.define(
            VariableSymbol(
                name=name,
                type=STRING,
                line=line,
                column=column,
                initialized=True,
            )
        )
        self.visit(blocks[1])
        self.env.pop()
        return None

    def visitSwitchStatement(self, ctx: CompiscriptParser.SwitchStatementContext):
        # The official example switches over an integer, so any comparable value
        # is accepted instead of requiring a boolean.
        subject_type = self.visit(ctx.expression())
        self.env.switch_depth += 1
        seen: dict[str, int] = {}
        for case in ctx.switchCase():
            case_type = self.visit(case.expression())
            line, column = position(case.expression())
            if not is_comparable(subject_type, case_type):
                self.bag.add(
                    "SEM404",
                    f"El caso de tipo {case_type} no es comparable con la "
                    f"expresión de tipo {subject_type}",
                    line,
                    column,
                )
            literal = self._constant_text(case.expression())
            if literal is not None:
                if literal in seen:
                    self.bag.add(
                        "SEM405",
                        f"El caso '{literal}' ya aparece en la línea {seen[literal]}",
                        line,
                        column,
                    )
                else:
                    seen[literal] = line
            self._walk_case_body(case)
        default_case = ctx.defaultCase()
        if default_case is not None:
            self._walk_case_body(default_case)
        self.env.switch_depth -= 1
        return None

    def _walk_case_body(self, ctx: Any) -> None:
        line, column = position(ctx)
        self.env.push(ScopeKind.BLOCK, f"case@{line}", line, column)
        self._walk_statements(ctx.statement())
        self.env.pop()

    def visitBreakStatement(self, ctx: CompiscriptParser.BreakStatementContext):
        # Decision 1: break is also valid inside a switch.
        if not (self.env.inside_loop or self.env.inside_switch):
            line, column = position(ctx)
            self.bag.add(
                "SEM401",
                "'break' solo puede usarse dentro de un ciclo o de un 'switch'",
                line,
                column,
            )
        return None

    def visitContinueStatement(self, ctx: CompiscriptParser.ContinueStatementContext):
        if not self.env.inside_loop:
            line, column = position(ctx)
            self.bag.add(
                "SEM402",
                "'continue' solo puede usarse dentro de un ciclo",
                line,
                column,
            )
        return None

    def visitReturnStatement(self, ctx: CompiscriptParser.ReturnStatementContext):
        line, column = position(ctx)
        value_ctx = ctx.expression()
        value_type = self.visit(value_ctx) if value_ctx is not None else None
        function = self.env.current_function
        if function is None:
            self.bag.add(
                "SEM304",
                "'return' solo puede usarse dentro de una función",
                line,
                column,
            )
            return None
        expected = function.return_type
        if value_ctx is None:
            if expected not in (VOID, ERROR):
                self.bag.add(
                    "SEM303",
                    f"'{function.name}' debe retornar un valor de tipo {expected}",
                    line,
                    column,
                )
            return None
        if expected == VOID:
            self.bag.add(
                "SEM303",
                f"'{function.name}' no retorna valores, pero se retornó un valor "
                f"de tipo {value_type}",
                line,
                column,
            )
            return None
        if not is_assignable(expected, value_type):
            self.bag.add(
                "SEM303",
                f"'{function.name}' debe retornar {expected}, no {value_type}",
                line,
                column,
            )
        return None

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------
    def visitExpression(self, ctx: CompiscriptParser.ExpressionContext) -> Type:
        return self.visit(ctx.assignmentExpr())

    def visitAssignExpr(self, ctx: CompiscriptParser.AssignExprContext) -> Type:
        return self._check_assignment(ctx.leftHandSide(), ctx.assignmentExpr())

    def visitExprNoAssign(self, ctx: CompiscriptParser.ExprNoAssignContext) -> Type:
        return self.visit(ctx.conditionalExpr())

    def _check_assignment(self, target_ctx: Any, value_ctx: Any) -> Type:
        target = self._lhs_target(target_ctx)
        value_type = self.visit(value_ctx)
        line, column = target.line, target.column

        if target.kind == "constant":
            name = target.symbol.name if target.symbol is not None else "?"
            self.bag.add(
                "SEM108",
                f"'{name}' es una constante y no puede reasignarse",
                line,
                column,
            )
            return target.type
        if target.kind in ("callable", "value"):
            if not target.type.is_error:
                self.bag.add(
                    "SEM110",
                    "El lado izquierdo de la asignación no es un destino asignable",
                    line,
                    column,
                )
            return target.type
        if not is_assignable(target.type, value_type):
            value_line, value_column = position(value_ctx)
            self.bag.add(
                "SEM105",
                f"No se puede asignar un valor de tipo {value_type} a un destino "
                f"de tipo {target.type}",
                value_line,
                value_column,
            )
        if target.symbol is not None:
            target.symbol.initialized = True
        return target.type

    def visitTernaryExpr(self, ctx: CompiscriptParser.TernaryExprContext) -> Type:
        condition_type = self.visit(ctx.logicalOrExpr())
        branches = ctx.expression()
        if not branches:
            return condition_type
        line, column = position(ctx.logicalOrExpr())
        if not condition_type.is_error and condition_type != BOOLEAN:
            self.bag.add(
                "SEM106",
                f"La condición del operador ternario debe ser boolean, no "
                f"{condition_type}",
                line,
                column,
            )
        left = self.visit(branches[0])
        right = self.visit(branches[1])
        merged = common_type(left, right)
        if merged is None:
            branch_line, branch_column = position(branches[0])
            self.bag.add(
                "SEM107",
                f"Las ramas del operador ternario tienen tipos incompatibles: "
                f"{left} y {right}",
                branch_line,
                branch_column,
            )
            return ERROR
        return merged

    def visitLogicalOrExpr(self, ctx: CompiscriptParser.LogicalOrExprContext) -> Type:
        return self._logical_chain(ctx.logicalAndExpr(), "||")

    def visitLogicalAndExpr(self, ctx: CompiscriptParser.LogicalAndExprContext) -> Type:
        return self._logical_chain(ctx.equalityExpr(), "&&")

    def _logical_chain(self, operands: list[Any], operator: str) -> Type:
        types = [self.visit(item) for item in operands]
        if len(types) == 1:
            return types[0]
        for operand_ctx, operand_type in zip(operands, types):
            if not operand_type.is_error and operand_type != BOOLEAN:
                line, column = position(operand_ctx)
                self.bag.add(
                    "SEM102",
                    f"El operador '{operator}' necesita operandos boolean, "
                    f"no {operand_type}",
                    line,
                    column,
                )
        return BOOLEAN

    def visitEqualityExpr(self, ctx: CompiscriptParser.EqualityExprContext) -> Type:
        operands = ctx.relationalExpr()
        types = [self.visit(item) for item in operands]
        if len(types) == 1:
            return types[0]
        for index in range(1, len(types)):
            if not is_comparable(types[index - 1], types[index]):
                line, column = position(operands[index])
                operator = ctx.getChild(2 * index - 1).getText()
                self.bag.add(
                    "SEM104",
                    f"No se puede comparar {types[index - 1]} con {types[index]} "
                    f"usando '{operator}'",
                    line,
                    column,
                )
        return BOOLEAN

    def visitRelationalExpr(self, ctx: CompiscriptParser.RelationalExprContext) -> Type:
        operands = ctx.additiveExpr()
        types = [self.visit(item) for item in operands]
        if len(types) == 1:
            return types[0]
        for index in range(1, len(types)):
            left, right = types[index - 1], types[index]
            if left.is_error or right.is_error:
                continue
            numeric = is_numeric(left) and is_numeric(right)
            textual = left == STRING and right == STRING
            if not (numeric or textual):
                line, column = position(operands[index])
                operator = ctx.getChild(2 * index - 1).getText()
                self.bag.add(
                    "SEM104",
                    f"El operador '{operator}' necesita dos números o dos strings, "
                    f"no {left} y {right}",
                    line,
                    column,
                )
        return BOOLEAN

    def visitAdditiveExpr(self, ctx: CompiscriptParser.AdditiveExprContext) -> Type:
        operands = ctx.multiplicativeExpr()
        result = self.visit(operands[0])
        for index in range(1, len(operands)):
            operator = ctx.getChild(2 * index - 1).getText()
            right = self.visit(operands[index])
            result = self._binary_result(operator, result, right, operands[index])
        return result

    def visitMultiplicativeExpr(
        self, ctx: CompiscriptParser.MultiplicativeExprContext
    ) -> Type:
        operands = ctx.unaryExpr()
        result = self.visit(operands[0])
        for index in range(1, len(operands)):
            operator = ctx.getChild(2 * index - 1).getText()
            right = self.visit(operands[index])
            result = self._binary_result(operator, result, right, operands[index])
        return result

    def _binary_result(
        self, operator: str, left: Type, right: Type, right_ctx: Any
    ) -> Type:
        if left.is_error or right.is_error:
            return ERROR
        # The official examples concatenate with '+', so a string operand turns
        # the whole operation into a concatenation.
        if operator == "+" and STRING in (left, right):
            other = right if left == STRING else left
            if is_printable(other):
                return STRING
            line, column = position(right_ctx)
            self.bag.add(
                "SEM101",
                f"No se puede concatenar un valor de tipo {other} con un string",
                line,
                column,
            )
            return ERROR
        result = arithmetic_result(left, right)
        if result.is_error:
            line, column = position(right_ctx)
            self.bag.add(
                "SEM101",
                f"El operador '{operator}' necesita operandos numéricos, "
                f"no {left} y {right}",
                line,
                column,
            )
        return result

    def visitUnaryExpr(self, ctx: CompiscriptParser.UnaryExprContext) -> Type:
        inner = ctx.unaryExpr()
        if inner is None:
            return self.visit(ctx.primaryExpr())
        operator = ctx.getChild(0).getText()
        operand_type = self.visit(inner)
        line, column = position(inner)
        if operator == "!":
            if not operand_type.is_error and operand_type != BOOLEAN:
                self.bag.add(
                    "SEM103",
                    f"El operador '!' necesita un operando boolean, no {operand_type}",
                    line,
                    column,
                )
            return BOOLEAN
        if operand_type.is_error:
            return ERROR
        if not is_numeric(operand_type):
            self.bag.add(
                "SEM101",
                f"El operador '-' necesita un operando numérico, no {operand_type}",
                line,
                column,
            )
            return ERROR
        return operand_type

    def visitPrimaryExpr(self, ctx: CompiscriptParser.PrimaryExprContext) -> Type:
        if ctx.literalExpr() is not None:
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide() is not None:
            return self.visit(ctx.leftHandSide())
        return self.visit(ctx.expression())

    def visitLiteralExpr(self, ctx: CompiscriptParser.LiteralExprContext) -> Type:
        if ctx.FloatLiteral() is not None:
            return FLOAT
        if ctx.Literal() is not None:
            text = ctx.Literal().getText()
            return STRING if text.startswith('"') else INTEGER
        if ctx.arrayLiteral() is not None:
            return self.visit(ctx.arrayLiteral())
        text = ctx.getText()
        if text == "null":
            return NULL
        return BOOLEAN

    def visitArrayLiteral(self, ctx: CompiscriptParser.ArrayLiteralContext) -> Type:
        expressions = ctx.expression()
        if not expressions:
            # An empty literal adapts to the declared type of its target.
            return ArrayType(ERROR)
        element: Type = self.visit(expressions[0])
        for item in expressions[1:]:
            item_type = self.visit(item)
            merged = common_type(element, item_type)
            if merged is None:
                line, column = position(item)
                self.bag.add(
                    "SEM603",
                    f"El arreglo mezcla elementos de tipo {element} y {item_type}",
                    line,
                    column,
                )
                element = ERROR
            else:
                element = merged
        return ArrayType(element)

    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext) -> Type:
        return self._lhs_target(ctx).type

    # ------------------------------------------------------------------
    # Left-hand sides, calls and members
    # ------------------------------------------------------------------
    def _lhs_target(self, ctx: Any) -> Target:
        target = self._atom_target(ctx.primaryAtom())
        for suffix in ctx.suffixOp():
            target = self._suffix_target(target, suffix)
        return target

    def _atom_target(self, ctx: Any) -> Target:
        line, column = position(ctx)
        if isinstance(ctx, CompiscriptParser.IdentifierExprContext):
            name = ctx.Identifier().getText()
            symbol = self.env.resolve(name)
            if symbol is None:
                self.bag.add("SEM201", f"'{name}' no ha sido declarado", line, column)
                return Target(ERROR, "value", line=line, column=column)
            kind = {
                SymbolCategory.CONSTANT: "constant",
                SymbolCategory.FUNCTION: "callable",
                SymbolCategory.METHOD: "callable",
                SymbolCategory.CLASS: "value",
            }.get(symbol.category, "variable")
            return Target(
                symbol.type,
                kind,
                symbol=symbol,
                length=getattr(symbol, "length", None),
                line=line,
                column=column,
            )
        if isinstance(ctx, CompiscriptParser.NewExprContext):
            return self._new_target(ctx)
        if isinstance(ctx, CompiscriptParser.ThisExprContext):
            current_class = self.env.current_class
            if current_class is None:
                self.bag.add(
                    "SEM503",
                    "'this' solo puede usarse dentro de un método o un constructor",
                    line,
                    column,
                )
                return Target(ERROR, "value", line=line, column=column)
            return Target(current_class.type, "variable", line=line, column=column)
        return Target(ERROR, "value", line=line, column=column)

    def _new_target(self, ctx: Any) -> Target:
        line, column = position(ctx)
        name = ctx.Identifier().getText()
        arguments = ctx.arguments()
        argument_contexts = list(arguments.expression()) if arguments is not None else []
        argument_types = [self.visit(item) for item in argument_contexts]
        class_symbol = self.table.lookup_class(name)
        if class_symbol is None:
            self.bag.add("SEM501", f"La clase '{name}' no existe", line, column)
            return Target(ERROR, "value", line=line, column=column)
        constructor = class_symbol.lookup_constructor()
        if constructor is None:
            if argument_types:
                self.bag.add(
                    "SEM504",
                    f"'{name}' no define un constructor, pero recibió "
                    f"{len(argument_types)} argumentos",
                    line,
                    column,
                )
        else:
            self._check_arguments(
                constructor,
                argument_contexts,
                argument_types,
                line,
                column,
                count_code="SEM504",
            )
        return Target(class_symbol.type, "value", line=line, column=column)

    def _suffix_target(self, target: Target, ctx: Any) -> Target:
        line, column = position(ctx)
        anchor_line = target.line or line
        anchor_column = target.column or column

        if isinstance(ctx, CompiscriptParser.CallExprContext):
            arguments = ctx.arguments()
            argument_contexts = (
                list(arguments.expression()) if arguments is not None else []
            )
            argument_types = [self.visit(item) for item in argument_contexts]
            callee = target.type
            if callee.is_error:
                return Target(ERROR, "value", line=line, column=column)
            if not isinstance(callee, FunctionType):
                self.bag.add(
                    "SEM306",
                    f"Un valor de tipo {callee} no se puede llamar como función",
                    anchor_line,
                    anchor_column,
                )
                return Target(ERROR, "value", line=line, column=column)
            if isinstance(target.symbol, FunctionSymbol):
                self._check_arguments(
                    target.symbol,
                    argument_contexts,
                    argument_types,
                    anchor_line,
                    anchor_column,
                )
            elif len(argument_types) != len(callee.parameters):
                self.bag.add(
                    "SEM301",
                    f"Se esperaban {len(callee.parameters)} argumentos y se "
                    f"recibieron {len(argument_types)}",
                    anchor_line,
                    anchor_column,
                )
            return Target(callee.return_type, "value", line=line, column=column)

        if isinstance(ctx, CompiscriptParser.IndexExprContext):
            index_type = self.visit(ctx.expression())
            index_line, index_column = position(ctx.expression())
            if not index_type.is_error and index_type != INTEGER:
                self.bag.add(
                    "SEM601",
                    f"El índice debe ser integer, no {index_type}",
                    index_line,
                    index_column,
                )
            container = target.type
            if container.is_error:
                return Target(ERROR, "value", line=line, column=column)
            if not isinstance(container, ArrayType):
                self.bag.add(
                    "SEM602",
                    f"Un valor de tipo {container} no se puede indexar",
                    anchor_line,
                    anchor_column,
                )
                return Target(ERROR, "value", line=line, column=column)
            self._check_static_index(target, ctx.expression(), index_line, index_column)
            return Target(container.element, "element", line=line, column=column)

        if isinstance(ctx, CompiscriptParser.PropertyAccessExprContext):
            return self._member_target(target, ctx.Identifier().getText(), line, column)

        return Target(ERROR, "value", line=line, column=column)

    def _check_static_index(
        self, target: Target, expression_ctx: Any, line: int, column: int
    ) -> None:
        """Report a literal index outside a literal array.

        Decision 6: this is a warning, because the official program indexes
        ``numbers[10]`` on purpose. Dynamic indexes stay a runtime concern.
        """
        if target.length is None:
            return
        text = self._constant_text(expression_ctx)
        if text is None or not text.isdigit():
            return
        index = int(text)
        if index >= target.length:
            self.bag.warn(
                "SEM604",
                f"El índice {index} queda fuera del arreglo de {target.length} "
                f"elementos; se verificará en ejecución",
                line,
                column,
            )

    def _member_target(self, target: Target, name: str, line: int, column: int) -> Target:
        owner = target.type
        if owner.is_error:
            return Target(ERROR, "value", line=line, column=column)
        if not isinstance(owner, ClassType) or owner.symbol is None:
            self.bag.add(
                "SEM506",
                f"Un valor de tipo {owner} no tiene miembros accesibles con '.'",
                target.line or line,
                target.column or column,
            )
            return Target(ERROR, "value", line=line, column=column)
        class_symbol: ClassSymbol = owner.symbol
        attribute = class_symbol.lookup_attribute(name)
        if attribute is not None:
            kind = "property" if attribute.mutable else "constant"
            return Target(attribute.type, kind, symbol=attribute, line=line, column=column)
        method = class_symbol.lookup_method(name)
        if method is not None:
            return Target(
                method.signature, "callable", symbol=method, line=line, column=column
            )
        self.bag.add(
            "SEM502",
            f"'{name}' no existe en la clase '{class_symbol.name}'",
            line,
            column,
        )
        return Target(ERROR, "value", line=line, column=column)

    def _check_arguments(
        self,
        function: FunctionSymbol,
        argument_contexts: list[Any],
        argument_types: list[Type],
        line: int,
        column: int,
        count_code: str = "SEM301",
    ) -> None:
        expected = function.parameters
        if len(argument_types) != len(expected):
            self.bag.add(
                count_code,
                f"'{function.name}' espera {len(expected)} argumentos y recibió "
                f"{len(argument_types)}",
                line,
                column,
            )
            return
        for parameter, argument_ctx, argument_type in zip(
            expected, argument_contexts, argument_types
        ):
            if not is_assignable(parameter.type, argument_type):
                argument_line, argument_column = position(argument_ctx)
                self.bag.add(
                    "SEM302",
                    f"El parámetro '{parameter.name}' espera {parameter.type} y "
                    f"recibió {argument_type}",
                    argument_line,
                    argument_column,
                )

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------
    def _require_boolean(self, expression_ctx: Any, keyword: str) -> None:
        condition_type = self.visit(expression_ctx)
        if condition_type.is_error or condition_type == BOOLEAN:
            return
        line, column = position(expression_ctx)
        self.bag.add(
            "SEM106",
            f"La condición de '{keyword}' debe ser boolean, no {condition_type}",
            line,
            column,
        )

    def _constant_text(self, expression_ctx: Any) -> Optional[str]:
        """Literal text of a constant expression, or ``None`` if it is not one."""
        text = expression_ctx.getText()
        if not text:
            return None
        if text.isdigit() or text in ("true", "false", "null"):
            return text
        if text.startswith('"') and text.endswith('"'):
            return text
        return None

    def _literal_length(self, value_ctx: Any) -> Optional[int]:
        """Element count when the initializer is an array literal."""
        node: Any = value_ctx
        while node is not None and not isinstance(
            node, CompiscriptParser.ArrayLiteralContext
        ):
            if node.getChildCount() != 1:
                return None
            node = node.getChild(0)
        if node is None:
            return None
        return len(node.expression())
