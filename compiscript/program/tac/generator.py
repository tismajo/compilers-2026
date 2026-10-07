"""Three-address code generator.

Walks the parse tree that the semantic phase already validated, the same way
``semantic.checker`` does, and reuses what the checker recorded:

* ``bindings``: the symbol behind every identifier, declaration and —since
  the checker's ``_record_target`` also covers ``suffixOp`` nodes— every
  ``new``, property access and call;
* ``declared``: the symbol behind every function declaration;
* ``type_objects``: the type of every expression, including suffix nodes, to
  insert conversions and compute array/attribute offsets.

Only closures that capture a variable from more than one lexical function up
still emit a ``# TODO`` instead of failing, so any valid program still
produces intermediate code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from CompiscriptParser import CompiscriptParser
from CompiscriptVisitor import CompiscriptVisitor

from semantic.annotations import position
from semantic.checker import Checker
from semantic.symbols import (
    AttributeSymbol,
    ClassSymbol,
    FunctionSymbol,
    MethodSymbol,
    Symbol,
)
from semantic.types import (
    BOOLEAN,
    ERROR,
    FLOAT,
    INTEGER,
    NULL,
    STRING,
    VOID,
    ArrayType,
    ClassType,
    Type,
)

from .instructions import FunctionCode, Quad, TacProgram, VTableData
from .layout import ARRAY_HEADER, WORD, ActivationRecord, Layout, assign_addresses, size_of
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
        # ``(catch label, TAC name of the catch variable)``, innermost last;
        # a fallible op with no active handler emits ``halt`` instead.
        self.handlers: list[tuple[str, str]] = []
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
        self.program.vtables = [
            VTableData(class_name=name, label=label, slots=slots)
            for name, label, slots in self.layout.vtable_data()
        ]
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

    def fail(self, condition_place: str, message: str) -> None:
        """Runtime fault: jump to the active ``catch``, or ``halt``.

        Only array bounds checks raise this today. Division by zero and
        ``null`` member access are out of scope for this phase (see
        ``docs/lenguaje-intermedio.md``), so exceptions never cross a
        function call: each function resolves its own ``try/catch``.
        """
        fail_label, ok_label = self.new_label(), self.new_label()
        self.emit("if_true", condition_place, fail_label)
        self.emit("goto", ok_label)
        self.emit("label", fail_label)
        if self.state.handlers:
            handler_label, err_name = self.state.handlers[-1]
            self.emit("assign", f'"{message}"', result=err_name)
            self.emit("goto", handler_label)
        else:
            self.emit("halt")
        self.emit("label", ok_label)

    @staticmethod
    def _class_name_of(value_type: Type) -> str:
        assert isinstance(value_type, ClassType)
        return value_type.name

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
        # A captured variable is referenced by the same flat TAC name as in
        # its owning function (``name_of`` keys on the symbol, not on which
        # ``FunctionState`` is current). Which physical frame that name
        # actually lives in at runtime is a MIPS-phase concern, resolved from
        # ``ActivationRecord.captured`` and the owner's offsets — both already
        # computed here — not something the TAC itself needs to encode.
        saved = self._open(symbol.name, self.layout.record_for(symbol), symbol)
        for statement in ctx.block().statement():
            self.visit(statement)
        self._close(saved)

    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        symbol = self.declared.get(id(ctx))
        if not isinstance(symbol, ClassSymbol):
            self.todo("clase", ctx, as_value=False)
            return
        for member in ctx.classMember():
            function_ctx = member.functionDeclaration()
            if function_ctx is None:
                continue
            method = symbol.methods.get(function_ctx.Identifier().getText())
            if method is None:
                continue
            saved = self._open(method.name, self.layout.record_for(method), method)
            for statement in function_ctx.block().statement():
                self.visit(statement)
            self._close(saved)

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
        # Lowered to an index-based loop over the same ``[length][elem0]...``
        # layout the array primitives use; ``idx`` is a temp pinned for the
        # whole loop instead of a variable with a frame slot (``Layout``
        # already ran, so there is nowhere left to reserve one).
        element_symbol = self.bindings[id(ctx)]
        element_name = self.name_of(element_symbol)
        array = self.expr(ctx.expression())
        stride = size_of(element_symbol.type)
        idx = self.new_temp()
        self.emit("assign", "0", result=idx)
        length = self.new_temp()
        self.emit("load", array.place, "0", length)
        check, cont, end = self.new_label(), self.new_label(), self.new_label()
        self.emit("label", check)
        cmp = self.new_temp()
        self.emit(">=", idx, length, cmp)
        self.emit("if_true", cmp, end)
        self.release(Value(cmp, ERROR))
        scaled = self.new_temp()
        self.emit("*", idx, str(stride), scaled)
        offset = self.new_temp()
        self.emit("+", scaled, str(ARRAY_HEADER), offset)
        self.release(Value(scaled, ERROR))
        self.emit("load", array.place, offset, element_name)
        self.release(Value(offset, ERROR))
        self._loop_body(ctx.block(), Loop(end, cont))
        self.emit("label", cont)
        self.emit("+", idx, "1", idx)
        self.emit("goto", check)
        self.emit("label", end)
        self.release(Value(idx, ERROR), Value(length, ERROR), array)

    def visitSwitchStatement(self, ctx: CompiscriptParser.SwitchStatementContext):
        # Every case body gets its own label and the bodies are emitted back
        # to back, so falling off one body flows straight into the next
        # (C-style fallthrough); ``break`` jumps past all of them.
        subject = self.expr(ctx.expression())
        cases = list(ctx.switchCase())
        default_case = ctx.defaultCase()
        end_label = self.new_label()
        body_labels = [self.new_label() for _ in cases]
        default_label = self.new_label() if default_case is not None else end_label
        for case, body_label in zip(cases, body_labels):
            case_value = self.expr(case.expression())
            cmp = self.new_temp()
            self.emit("==", subject.place, case_value.place, cmp)
            self.emit("if_true", cmp, body_label)
            self.release(case_value, Value(cmp, ERROR))
        self.emit("goto", default_label)
        self.release(subject)
        # ``continue`` inside a case must still reach the enclosing loop, not
        # this switch: checker.visitContinueStatement already requires a real
        # loop, so the switch only ever contributes its own ``break`` target.
        outer_continue = self.state.loops[-1].continue_label if self.state.loops else ""
        self.state.loops.append(Loop(end_label, outer_continue))
        for case, body_label in zip(cases, body_labels):
            self.emit("label", body_label)
            for statement in case.statement():
                self.visit(statement)
        if default_case is not None:
            self.emit("label", default_label)
            for statement in default_case.statement():
                self.visit(statement)
        self.state.loops.pop()
        self.emit("label", end_label)

    def visitTryCatchStatement(self, ctx: CompiscriptParser.TryCatchStatementContext):
        blocks = ctx.block()
        err_name = self.name_of(self.bindings[id(ctx)])
        catch_label, end_label = self.new_label(), self.new_label()
        self.state.handlers.append((catch_label, err_name))
        self.visit(blocks[0])
        self.state.handlers.pop()
        self.emit("goto", end_label)
        self.emit("label", catch_label)
        self.visit(blocks[1])
        self.emit("label", end_label)

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
        suffixes = list(target_ctx.suffixOp())
        if not suffixes:
            if not isinstance(atom, CompiscriptParser.IdentifierExprContext):
                return self.todo("asignación", target_ctx.parentCtx)
            return self._assign_simple(atom, value_ctx)
        current = self._atom_value(atom, suffixes)
        current = self._walk_suffixes(current, suffixes[:-1])
        last = suffixes[-1]
        if isinstance(last, CompiscriptParser.IndexExprContext):
            return self._assign_index(current, last, value_ctx)
        if isinstance(last, CompiscriptParser.PropertyAccessExprContext):
            return self._assign_attribute(current, last, value_ctx)
        return self.todo("asignación a miembro o índice", target_ctx.parentCtx)

    def _assign_simple(self, atom: Any, value_ctx: Any) -> Value:
        symbol = self.bindings[id(atom)]
        name = self.name_of(symbol)
        value = self.coerce(self.expr(value_ctx), symbol.type)
        self.emit("assign", value.place, result=name)
        self.release(value)
        return Value(name, symbol.type)

    def _assign_index(self, base: Value, ctx: Any, value_ctx: Any) -> Value:
        index_value = self.expr(ctx.expression())
        element_type = self.type_objects.get(id(ctx), ERROR)
        offset = self._bounds_checked_offset(base, index_value, element_type)
        value = self.coerce(self.expr(value_ctx), element_type)
        self.emit("store", base.place, offset.place, result=value.place)
        self.release(base, offset)
        return value

    def _assign_attribute(self, obj: Value, ctx: Any, value_ctx: Any) -> Value:
        symbol = self.bindings.get(id(ctx))
        if not isinstance(symbol, AttributeSymbol):
            return self.todo("asignación a miembro", ctx)
        value = self.coerce(self.expr(value_ctx), symbol.type)
        self.emit("store", obj.place, str(symbol.offset), result=value.place)
        self.release(obj)
        return value

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
            return self._array_literal(ctx.arrayLiteral())
        text = ctx.getText()
        return Value(text, NULL if text == "null" else BOOLEAN)

    def _array_literal(self, ctx: CompiscriptParser.ArrayLiteralContext) -> Value:
        # ``[length][elem0][elem1]...`` — the same layout array reads/writes
        # use, so the bounds check never needs to look anywhere else for the
        # length. A nested literal (a matrix) just recurses: its element is a
        # pointer, consistent with ``size_of`` treating every non-float type
        # as one word.
        array_type = self.type_objects.get(id(ctx), ERROR)
        element_type = array_type.element if isinstance(array_type, ArrayType) else ERROR
        elements = list(ctx.expression())
        stride = size_of(element_type)
        base = self.new_temp()
        self.emit("alloc", str(ARRAY_HEADER + stride * len(elements)), result=base)
        self.emit("store", base, "0", result=str(len(elements)))
        for index, element_ctx in enumerate(elements):
            value = self.coerce(self.expr(element_ctx), element_type)
            self.emit("store", base, str(ARRAY_HEADER + stride * index), result=value.place)
            self.release(value)
        return Value(base, array_type)

    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext) -> Value:
        atom = ctx.primaryAtom()
        suffixes = list(ctx.suffixOp())
        current = self._atom_value(atom, suffixes)
        return self._walk_suffixes(current, suffixes)

    def _atom_value(self, atom: Any, suffixes: list[Any]) -> Value:
        if isinstance(atom, CompiscriptParser.IdentifierExprContext):
            symbol = self.bindings[id(atom)]
            if isinstance(symbol, FunctionSymbol):
                if not suffixes:
                    # A bare function reference with nothing to call it is a
                    # first-class function value; not supported yet.
                    return self.todo("referencia a función sin llamar", atom)
                return Value(symbol.label or symbol.name, symbol.type)
            return Value(self.name_of(symbol), symbol.type)
        if isinstance(atom, CompiscriptParser.ThisExprContext):
            # ``this`` has no backing declared ``Symbol``; it is always the
            # literal name ``Layout`` already gave the method's first
            # parameter (``Slot("this", ...)`` in ``_open_record``).
            return Value("this", self.type_objects.get(id(atom), ERROR))
        if isinstance(atom, CompiscriptParser.NewExprContext):
            return self._new_object(atom)
        return self.todo("átomo", atom)

    def _walk_suffixes(self, current: Value, suffixes: list[Any]) -> Value:
        index = 0
        while index < len(suffixes):
            suffix = suffixes[index]
            if isinstance(suffix, CompiscriptParser.PropertyAccessExprContext):
                member = self.bindings.get(id(suffix))
                if isinstance(member, MethodSymbol):
                    has_call = index + 1 < len(suffixes) and isinstance(
                        suffixes[index + 1], CompiscriptParser.CallExprContext
                    )
                    if not has_call:
                        return self.todo("referencia a método sin llamar", suffix)
                    current = self._call_method(current, member, suffixes[index + 1])
                    index += 2
                    continue
                current = self._read_attribute(current, member, suffix)
                index += 1
                continue
            if isinstance(suffix, CompiscriptParser.IndexExprContext):
                current = self._read_index(current, suffix)
                index += 1
                continue
            if isinstance(suffix, CompiscriptParser.CallExprContext):
                callee = self.bindings.get(id(suffix))
                if isinstance(callee, FunctionSymbol) and not isinstance(callee, MethodSymbol):
                    current = self._call(callee, suffix)
                else:
                    current = self.todo("llamada", suffix)
                index += 1
                continue
            current = self.todo("sufijo", suffix)
            index += 1
        return current

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

    def _new_object(self, ctx: CompiscriptParser.NewExprContext) -> Value:
        class_symbol = self.bindings[id(ctx)]
        assert isinstance(class_symbol, ClassSymbol)
        arguments = ctx.arguments()
        contexts = list(arguments.expression()) if arguments is not None else []
        constructor = class_symbol.lookup_constructor()
        values = (
            [
                self.coerce(self.expr(item), parameter.type)
                for item, parameter in zip(contexts, constructor.parameters)
            ]
            if constructor is not None
            else []
        )
        base = self.new_temp()
        self.emit("alloc", str(class_symbol.size), result=base)
        # The descriptor is the class's vtable pointer; the constructor is
        # always called statically (never through it), so an override of an
        # inherited constructor label would be meaningless here.
        self.emit("store", base, "0", result=self.layout.vtable_label(class_symbol.name))
        if constructor is not None:
            self.emit("param", base)
            for value in values:
                self.emit("param", value.place)
            self.release(*values)
            self.emit("call", constructor.label, len(values) + 1)
        return Value(base, class_symbol.type)

    def _call_method(self, receiver: Value, method: MethodSymbol, ctx: Any) -> Value:
        """Dynamic dispatch: load the vtable through the object, then the
        method's slot in it, and call that address indirectly — the runtime
        class of ``receiver``, not its static type, decides which body runs."""
        arguments = ctx.arguments()
        contexts = list(arguments.expression()) if arguments is not None else []
        values = [
            self.coerce(self.expr(item), parameter.type)
            for item, parameter in zip(contexts, method.parameters)
        ]
        class_name = self._class_name_of(receiver.type)
        slot = self.layout.vtable_slot(class_name, method.name)
        vtable_ptr = self.new_temp()
        self.emit("load", receiver.place, "0", vtable_ptr)
        fn_ptr = self.new_temp()
        self.emit("load", vtable_ptr, str(slot * WORD), fn_ptr)
        self.release(Value(vtable_ptr, ERROR))
        self.emit("param", receiver.place)
        for value in values:
            self.emit("param", value.place)
        nargs = len(values) + 1
        self.release(receiver, *values)
        if method.return_type == VOID:
            self.emit("calli", fn_ptr, nargs)
            self.release(Value(fn_ptr, ERROR))
            return Value("", VOID)
        self.release(Value(fn_ptr, ERROR))
        result = self.new_temp()
        self.emit("calli", fn_ptr, nargs, result)
        return Value(result, method.return_type)

    def _read_attribute(self, obj: Value, symbol: Optional[Symbol], ctx: Any) -> Value:
        if not isinstance(symbol, AttributeSymbol):
            return self.todo("miembro", ctx)
        result = self.new_temp()
        self.emit("load", obj.place, str(symbol.offset), result)
        self.release(obj)
        return Value(result, symbol.type)

    def _read_index(self, base: Value, ctx: CompiscriptParser.IndexExprContext) -> Value:
        index_value = self.expr(ctx.expression())
        element_type = self.type_objects.get(id(ctx), ERROR)
        offset = self._bounds_checked_offset(base, index_value, element_type)
        result = self.new_temp()
        self.emit("load", base.place, offset.place, result)
        self.release(base, offset)
        return Value(result, element_type)

    def _bounds_checked_offset(self, base: Value, index: Value, element_type: Type) -> Value:
        length = self.new_temp()
        self.emit("load", base.place, "0", length)
        cmp = self.new_temp()
        self.emit(">=", index.place, length, cmp)
        self.release(Value(length, ERROR))
        self.fail(cmp, "Índice fuera de rango")
        self.release(Value(cmp, ERROR))
        stride = size_of(element_type)
        scaled = self.new_temp()
        self.emit("*", index.place, str(stride), scaled)
        self.release(index)
        offset = self.new_temp()
        self.emit("+", scaled, str(ARRAY_HEADER), offset)
        self.release(Value(scaled, ERROR))
        return Value(offset, INTEGER)
