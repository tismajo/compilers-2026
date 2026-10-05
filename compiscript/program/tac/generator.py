"""Three-address code generator.

Walks the parse tree that the semantic phase already validated, the same way
``semantic.checker`` does, and reuses what the checker recorded:

* ``bindings``: the symbol behind every identifier and declaration;
* ``declared``: the symbol behind every function declaration;
* ``type_objects``: the type of every expression, to insert conversions.

Constructs that are not translated yet (classes, arrays, ``foreach``,
``switch``, ``try/catch`` and closures) emit a ``# TODO`` instruction instead
of failing, so any valid program still produces intermediate code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from CompiscriptParser import CompiscriptParser
from CompiscriptVisitor import CompiscriptVisitor

from semantic.annotations import position
from semantic.checker import Checker
from semantic.symbols import FunctionSymbol, MethodSymbol, Symbol
from semantic.types import BOOLEAN, ERROR, FLOAT, INTEGER, NULL, STRING, VOID, Type

from .instructions import FunctionCode, Quad, TacProgram
from .layout import ActivationRecord, Layout, assign_addresses
from .temps import TempAllocator

# User names that would read as a temporary or a label get a ``#v`` suffix.
RESERVED_NAME = re.compile(r"^[tL]\d+$")
TODO_TEXT_LIMIT = 40

DEFAULT_VALUES = {INTEGER: "0", FLOAT: "0.0", BOOLEAN: "false", STRING: '""'}


@dataclass
class Value:
    """Where an expression left its result and the type of that result."""

    place: str
    type: Type = ERROR


@dataclass
class Loop:
    break_label: str
    continue_label: str


class FunctionState:
    """Everything that is per function: code, temporaries and loop labels."""

    def __init__(
        self,
        code: FunctionCode,
        record: ActivationRecord,
        function: Optional[FunctionSymbol] = None,
    ) -> None:
        self.code = code
        self.record = record
        self.function = function
        self.temps = TempAllocator()
        self.loops: list[Loop] = []
        self.used_names: set[str] = set()
        self.begin: Optional[Quad] = None


class TacGenerator(CompiscriptVisitor):
    def __init__(self, semantic: Any) -> None:
        self.table = semantic.symbols
        self.bindings: dict[int, Symbol] = semantic.bindings
        self.declared: dict[int, Symbol] = semantic.declared
        self.type_objects: dict[int, Type] = semantic.type_objects
        self.layout: Layout = assign_addresses(self.table)
        self.program = TacProgram()
        self.state: FunctionState  # set by ``_open``
        self._labels = 0
        self._names: dict[int, str] = {}
        self._global_names: set[str] = set()

    # -- entry point ----------------------------------------------------
    def generate(self, program_ctx: Any) -> TacProgram:
        record = ActivationRecord(name="main", label="main", kind="main")
        saved = self._open("main", record)
        for statement in program_ctx.statement():
            self.visit(statement)
        self._close(saved)
        # ``main`` is closed last but printed first, it is where execution starts.
        self.program.functions.insert(0, self.program.functions.pop())
        self.table.activation_records.insert(0, record)
        return self.program

    # -- function bookkeeping -------------------------------------------
    def _open(
        self,
        name: str,
        record: ActivationRecord,
        function: Optional[FunctionSymbol] = None,
    ) -> Optional[FunctionState]:
        saved = getattr(self, "state", None)
        code = FunctionCode(name, record.label, record)
        self.state = FunctionState(code, record, function)
        self.state.begin = self.emit("begin_func", 0)
        return saved

    def _close(self, saved: Optional[FunctionState]) -> None:
        state = self.state
        self.emit("end_func")
        state.record.temps = state.temps.peak
        # The frame size is only known once the body used its temporaries.
        assert state.begin is not None
        state.begin.arg1 = str(state.record.frame_size)
        self.program.functions.append(state.code)
        if saved is not None:
            self.state = saved

    # -- small helpers --------------------------------------------------
    def emit(self, op: str, arg1: Any = None, arg2: Any = None, result: Any = None) -> Quad:
        return self.state.code.emit(op, arg1, arg2, result)

    def new_label(self) -> str:
        label = f"L{self._labels}"
        self._labels += 1
        return label

    def new_temp(self) -> str:
        return self.state.temps.new()

    def release(self, *values: Value) -> None:
        self.state.temps.release(*(item.place for item in values))

    def name_of(self, symbol: Symbol) -> str:
        """Unique TAC name for a symbol; shadowed names get a ``#n`` suffix."""
        key = id(symbol)
        if key in self._names:
            return self._names[key]
        base = symbol.name + ("#v" if RESERVED_NAME.match(symbol.name) else "")
        is_global = symbol.storage == "global"
        taken = self._global_names if is_global else self.state.used_names
        name = base
        counter = 2
        while name in taken or (not is_global and name in self._global_names):
            name = f"{base}#{counter}"
            counter += 1
        taken.add(name)
        self._names[key] = name
        return name

    def expr(self, ctx: Any) -> Value:
        value = self.visit(ctx)
        return value if isinstance(value, Value) else Value("?", ERROR)

    def coerce(self, value: Value, target: Type) -> Value:
        """Insert ``itof`` when an integer flows into a float."""
        if target == FLOAT and value.type == INTEGER:
            return self._convert(value, "itof", FLOAT)
        return value

    def _convert(self, value: Value, op: str, new_type: Type) -> Value:
        self.release(value)
        result = self.new_temp()
        self.emit(op, value.place, result=result)
        return Value(result, new_type)

    def todo(self, what: str, ctx: Any, as_value: bool = True) -> Value:
        line, _ = position(ctx)
        text = ctx.getText()
        if len(text) > TODO_TEXT_LIMIT:
            text = text[: TODO_TEXT_LIMIT - 3] + "..."
        description = f"{what} (línea {line}): {text}"
        if not as_value:
            self.emit("todo", description)
            return Value("?", ERROR)
        result = self.new_temp()
        self.emit("todo", description, result=result)
        return Value(result, self.type_objects.get(id(ctx), ERROR))

    # ------------------------------------------------------------------
    # Declarations
    # ------------------------------------------------------------------
    def visitVariableDeclaration(self, ctx: CompiscriptParser.VariableDeclarationContext):
        initializer = ctx.initializer()
        self._declare(ctx, initializer.expression() if initializer is not None else None)

    def visitConstantDeclaration(self, ctx: CompiscriptParser.ConstantDeclarationContext):
        self._declare(ctx, ctx.expression())

    def _declare(self, ctx: Any, value_ctx: Any) -> None:
        symbol = self.bindings[id(ctx)]
        name = self.name_of(symbol)
        if value_ctx is None:
            # Uninitialized variables start with the zero value of their type.
            self.emit("assign", DEFAULT_VALUES.get(symbol.type, "null"), result=name)
            return
        value = self.coerce(self.expr(value_ctx), symbol.type)
        self.emit("assign", value.place, result=name)
        self.release(value)

    def visitFunctionDeclaration(self, ctx: CompiscriptParser.FunctionDeclarationContext):
        symbol = self.declared.get(id(ctx))
        if not isinstance(symbol, FunctionSymbol) or isinstance(symbol, MethodSymbol):
            self.todo("función", ctx, as_value=False)
            return
        if symbol.captured:
            self.todo(f"closure '{symbol.name}' captura {', '.join(symbol.captured)}", ctx, False)
            return
        saved = self._open(symbol.name, self.layout.record_for(symbol), symbol)
        for statement in ctx.block().statement():
            self.visit(statement)
        self._close(saved)

    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        self.todo("clase", ctx, as_value=False)

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------
    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        for statement in ctx.statement():
            self.visit(statement)

    def visitExpressionStatement(self, ctx: CompiscriptParser.ExpressionStatementContext):
        self.release(self.expr(ctx.expression()))

    def visitPrintStatement(self, ctx: CompiscriptParser.PrintStatementContext):
        value = self.expr(ctx.expression())
        self.emit("print", value.place)
        self.release(value)

    def visitAssignment(self, ctx: CompiscriptParser.AssignmentContext):
        self.release(self._assign(ctx.leftHandSide(), ctx.expression()))

    def visitIfStatement(self, ctx: CompiscriptParser.IfStatementContext):
        blocks = ctx.block()
        else_label = self.new_label()
        condition = self.expr(ctx.expression())
        self.emit("if_false", condition.place, else_label)
        self.release(condition)
        self.visit(blocks[0])
        if len(blocks) == 1:
            self.emit("label", else_label)
            return
        end_label = self.new_label()
        self.emit("goto", end_label)
        self.emit("label", else_label)
        self.visit(blocks[1])
        self.emit("label", end_label)

    def visitWhileStatement(self, ctx: CompiscriptParser.WhileStatementContext):
        start, end = self.new_label(), self.new_label()
        self.emit("label", start)
        condition = self.expr(ctx.expression())
        self.emit("if_false", condition.place, end)
        self.release(condition)
        self._loop_body(ctx.block(), Loop(end, start))
        self.emit("goto", start)
        self.emit("label", end)

    def visitDoWhileStatement(self, ctx: CompiscriptParser.DoWhileStatementContext):
        body, check, end = self.new_label(), self.new_label(), self.new_label()
        self.emit("label", body)
        self._loop_body(ctx.block(), Loop(end, check))
        self.emit("label", check)
        condition = self.expr(ctx.expression())
        self.emit("if_true", condition.place, body)
        self.release(condition)
        self.emit("label", end)

    def visitForStatement(self, ctx: CompiscriptParser.ForStatementContext):
        if ctx.variableDeclaration() is not None:
            self.visit(ctx.variableDeclaration())
        elif ctx.assignment() is not None:
            self.visit(ctx.assignment())
        condition_ctx, step_ctx = Checker._for_sections(ctx)
        check, step, end = self.new_label(), self.new_label(), self.new_label()
        self.emit("label", check)
        if condition_ctx is not None:
            condition = self.expr(condition_ctx)
            self.emit("if_false", condition.place, end)
            self.release(condition)
        self._loop_body(ctx.block(), Loop(end, step))
        self.emit("label", step)
        if step_ctx is not None:
            self.release(self.expr(step_ctx))
        self.emit("goto", check)
        self.emit("label", end)

    def _loop_body(self, block: Any, loop: Loop) -> None:
        self.state.loops.append(loop)
        self.visit(block)
        self.state.loops.pop()

    def visitBreakStatement(self, ctx: CompiscriptParser.BreakStatementContext):
        self.emit("goto", self.state.loops[-1].break_label)

    def visitContinueStatement(self, ctx: CompiscriptParser.ContinueStatementContext):
        self.emit("goto", self.state.loops[-1].continue_label)

    def visitReturnStatement(self, ctx: CompiscriptParser.ReturnStatementContext):
        value_ctx = ctx.expression()
        if value_ctx is None:
            self.emit("return")
            return
        function = self.state.function
        value = self.expr(value_ctx)
        if function is not None:
            value = self.coerce(value, function.return_type)
        self.emit("return", value.place)
        self.release(value)

    def visitForeachStatement(self, ctx: CompiscriptParser.ForeachStatementContext):
        self.todo("foreach", ctx, as_value=False)

    def visitSwitchStatement(self, ctx: CompiscriptParser.SwitchStatementContext):
        self.todo("switch", ctx, as_value=False)

    def visitTryCatchStatement(self, ctx: CompiscriptParser.TryCatchStatementContext):
        self.todo("try/catch", ctx, as_value=False)

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------
    def visitExpression(self, ctx: CompiscriptParser.ExpressionContext) -> Value:
        return self.expr(ctx.assignmentExpr())

    def visitAssignExpr(self, ctx: CompiscriptParser.AssignExprContext) -> Value:
        return self._assign(ctx.leftHandSide(), ctx.assignmentExpr())

    def visitExprNoAssign(self, ctx: CompiscriptParser.ExprNoAssignContext) -> Value:
        return self.expr(ctx.conditionalExpr())

    def _assign(self, target_ctx: Any, value_ctx: Any) -> Value:
        atom = target_ctx.primaryAtom()
        if target_ctx.suffixOp() or not isinstance(
            atom, CompiscriptParser.IdentifierExprContext
        ):
            return self.todo("asignación a miembro o índice", target_ctx.parentCtx)
        symbol = self.bindings[id(atom)]
        name = self.name_of(symbol)
        value = self.coerce(self.expr(value_ctx), symbol.type)
        self.emit("assign", value.place, result=name)
        self.release(value)
        return Value(name, symbol.type)

    def visitTernaryExpr(self, ctx: CompiscriptParser.TernaryExprContext) -> Value:
        branches = ctx.expression()
        if not branches:
            return self.expr(ctx.logicalOrExpr())
        result_type = self.type_objects.get(id(ctx), ERROR)
        else_label, end_label = self.new_label(), self.new_label()
        condition = self.expr(ctx.logicalOrExpr())
        self.emit("if_false", condition.place, else_label)
        self.release(condition)
        result = self.new_temp()
        for index, branch in enumerate(branches):
            if index == 1:
                self.emit("goto", end_label)
                self.emit("label", else_label)
            value = self.coerce(self.expr(branch), result_type)
            self.emit("assign", value.place, result=result)
            self.release(value)
        self.emit("label", end_label)
        return Value(result, result_type)

    def visitLogicalOrExpr(self, ctx: CompiscriptParser.LogicalOrExprContext) -> Value:
        return self._short_circuit(ctx.logicalAndExpr(), "if_true")

    def visitLogicalAndExpr(self, ctx: CompiscriptParser.LogicalAndExprContext) -> Value:
        return self._short_circuit(ctx.equalityExpr(), "if_false")

    def _short_circuit(self, operands: list[Any], jump: str) -> Value:
        """``a || b`` skips ``b`` when ``a`` is true; ``a && b`` when it is false."""
        if len(operands) == 1:
            return self.expr(operands[0])
        end_label = self.new_label()
        first = self.expr(operands[0])
        self.release(first)
        result = self.new_temp()
        if result != first.place:
            self.emit("assign", first.place, result=result)
        for operand in operands[1:]:
            self.emit(jump, result, end_label)
            value = self.expr(operand)
            self.emit("assign", value.place, result=result)
            self.release(value)
        self.emit("label", end_label)
        return Value(result, BOOLEAN)

    def visitEqualityExpr(self, ctx: CompiscriptParser.EqualityExprContext) -> Value:
        return self._comparison_chain(ctx, ctx.relationalExpr())

    def visitRelationalExpr(self, ctx: CompiscriptParser.RelationalExprContext) -> Value:
        return self._comparison_chain(ctx, ctx.additiveExpr())

    def _comparison_chain(self, ctx: Any, operands: list[Any]) -> Value:
        left = self.expr(operands[0])
        for index in range(1, len(operands)):
            operator = ctx.getChild(2 * index - 1).getText()
            right = self.expr(operands[index])
            left, right = self._balance(left, right)
            left = self._binary(operator, left, right, BOOLEAN)
        return left

    def visitAdditiveExpr(self, ctx: CompiscriptParser.AdditiveExprContext) -> Value:
        return self._arithmetic_chain(ctx, ctx.multiplicativeExpr())

    def visitMultiplicativeExpr(
        self, ctx: CompiscriptParser.MultiplicativeExprContext
    ) -> Value:
        return self._arithmetic_chain(ctx, ctx.unaryExpr())

    def _arithmetic_chain(self, ctx: Any, operands: list[Any]) -> Value:
        left = self.expr(operands[0])
        for index in range(1, len(operands)):
            operator = ctx.getChild(2 * index - 1).getText()
            right = self.expr(operands[index])
            if operator == "+" and STRING in (left.type, right.type):
                left = self._concat(left, right)
                continue
            left, right = self._balance(left, right)
            result_type = FLOAT if FLOAT in (left.type, right.type) else INTEGER
            left = self._binary(operator, left, right, result_type)
        return left

    def _balance(self, left: Value, right: Value) -> tuple[Value, Value]:
        """Promote the integer side of a mixed integer/float operation."""
        if left.type == INTEGER and right.type == FLOAT:
            left = self._convert(left, "itof", FLOAT)
        elif left.type == FLOAT and right.type == INTEGER:
            right = self._convert(right, "itof", FLOAT)
        return left, right

    def _concat(self, left: Value, right: Value) -> Value:
        if left.type != STRING:
            left = self._convert(left, "tostr", STRING)
        if right.type != STRING:
            right = self._convert(right, "tostr", STRING)
        self.release(left, right)
        result = self.new_temp()
        self.emit("concat", left.place, right.place, result)
        return Value(result, STRING)

    def _binary(self, operator: str, left: Value, right: Value, result_type: Type) -> Value:
        # Operands are released first, so the result can reuse one of them.
        self.release(left, right)
        result = self.new_temp()
        self.emit(operator, left.place, right.place, result)
        return Value(result, result_type)

    def visitUnaryExpr(self, ctx: CompiscriptParser.UnaryExprContext) -> Value:
        inner = ctx.unaryExpr()
        if inner is None:
            return self.expr(ctx.primaryExpr())
        operator = ctx.getChild(0).getText()
        value = self.expr(inner)
        self.release(value)
        result = self.new_temp()
        if operator == "!":
            self.emit("not", value.place, result=result)
            return Value(result, BOOLEAN)
        self.emit("minus", value.place, result=result)
        return Value(result, value.type)

    def visitPrimaryExpr(self, ctx: CompiscriptParser.PrimaryExprContext) -> Value:
        if ctx.literalExpr() is not None:
            return self.expr(ctx.literalExpr())
        if ctx.leftHandSide() is not None:
            return self.expr(ctx.leftHandSide())
        return self.expr(ctx.expression())

    def visitLiteralExpr(self, ctx: CompiscriptParser.LiteralExprContext) -> Value:
        if ctx.FloatLiteral() is not None:
            return Value(ctx.getText(), FLOAT)
        if ctx.Literal() is not None:
            text = ctx.getText()
            return Value(text, STRING if text.startswith('"') else INTEGER)
        if ctx.arrayLiteral() is not None:
            return self.todo("arreglo", ctx)
        text = ctx.getText()
        return Value(text, NULL if text == "null" else BOOLEAN)

    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext) -> Value:
        atom = ctx.primaryAtom()
        suffixes = ctx.suffixOp()
        if not isinstance(atom, CompiscriptParser.IdentifierExprContext):
            return self.todo("objeto", ctx)
        symbol = self.bindings[id(atom)]
        if not suffixes and not isinstance(symbol, FunctionSymbol):
            return Value(self.name_of(symbol), symbol.type)
        is_plain_call = (
            len(suffixes) == 1
            and isinstance(suffixes[0], CompiscriptParser.CallExprContext)
            and isinstance(symbol, FunctionSymbol)
            and not isinstance(symbol, MethodSymbol)
        )
        if not is_plain_call:
            return self.todo("acceso a miembro o índice", ctx)
        return self._call(symbol, suffixes[0])

    def _call(self, function: FunctionSymbol, ctx: Any) -> Value:
        arguments = ctx.arguments()
        contexts = list(arguments.expression()) if arguments is not None else []
        # Every argument is evaluated before the first ``param``, so a nested
        # call never interleaves its parameters with the outer ones.
        values = [
            self.coerce(self.expr(item), parameter.type)
            for item, parameter in zip(contexts, function.parameters)
        ]
        for value in values:
            self.emit("param", value.place)
        self.release(*values)
        label = function.label or function.name
        if function.return_type == VOID:
            self.emit("call", label, len(values))
            return Value("", VOID)
        result = self.new_temp()
        self.emit("call", label, len(values), result)
        return Value(result, function.return_type)
