"""First semantic pass: register global classes and function signatures.

Running this before the body pass is what allows recursion, mutually recursive
functions, forward references to classes and inheritance from a class declared
later in the file.

Only top-level declarations are collected here. Functions and classes nested
inside blocks belong to an inner scope, so the second pass registers them when
it enters that scope.
"""

from __future__ import annotations

from typing import Any, Optional

from .annotations import TypeResolver, position
from .diagnostics import DiagnosticBag
from .symbol_table import SymbolTable
from .symbols import (
    AttributeSymbol,
    ClassSymbol,
    FunctionSymbol,
    MethodSymbol,
    ParameterSymbol,
    Symbol,
)
from .types import ERROR, VOID, ClassType, Type, is_assignable

CONSTRUCTOR_NAME = "constructor"


class Collector:
    """Populates the global scope with classes and function signatures."""

    def __init__(self, table: SymbolTable, bag: DiagnosticBag) -> None:
        self.table = table
        self.bag = bag
        self.resolver = TypeResolver(table.classes, bag)
        # Maps ``id(ctx)`` to the symbol already created, so the second pass
        # reuses it instead of reporting a duplicate declaration.
        self.declared: dict[int, Symbol] = {}

    # -- entry point ----------------------------------------------------
    def run(self, program_ctx: Any) -> None:
        statements = list(program_ctx.statement())
        class_contexts = [
            item.classDeclaration()
            for item in statements
            if item.classDeclaration() is not None
        ]
        function_contexts = [
            item.functionDeclaration()
            for item in statements
            if item.functionDeclaration() is not None
        ]

        for ctx in class_contexts:
            self.declare_class(ctx)
        for ctx in class_contexts:
            self.link_parent(ctx)
        self._detect_inheritance_cycles()
        for ctx in class_contexts:
            self.collect_members(ctx)
        self.check_overrides()
        for ctx in function_contexts:
            self._declare_function(ctx)

    # -- classes --------------------------------------------------------
    def declare_class(self, ctx: Any) -> None:
        name_node = ctx.Identifier(0)
        name = name_node.getText()
        line, column = position(name_node)
        if name in self.table.classes:
            previous = self.table.classes[name]
            self.bag.add(
                "SEM205",
                f"La clase '{name}' ya fue declarada en la línea {previous.line}",
                line,
                column,
            )
            return
        symbol = ClassSymbol(name=name, line=line, column=column)
        symbol.type = ClassType(name)
        symbol.class_type.symbol = symbol
        parent_node = ctx.Identifier(1)
        symbol.parent_name = parent_node.getText() if parent_node is not None else None
        clash = self.table.environment.global_scope.define(symbol)
        if clash is not None:
            self.bag.add(
                "SEM202",
                f"'{name}' ya fue declarado en la línea {clash.line}",
                line,
                column,
            )
            return
        self.table.register_class(symbol)
        self.declared[id(ctx)] = symbol

    def link_parent(self, ctx: Any) -> None:
        symbol = self.declared.get(id(ctx))
        if symbol is None or symbol.parent_name is None:
            return
        parent = self.table.lookup_class(symbol.parent_name)
        if parent is None:
            node = ctx.Identifier(1)
            line, column = position(node)
            self.bag.add(
                "SEM206",
                f"La clase padre '{symbol.parent_name}' no existe",
                line,
                column,
            )
            symbol.parent_name = None
            return
        symbol.parent = parent
        symbol.class_type.parent = parent.class_type

    def _detect_inheritance_cycles(self) -> None:
        for symbol in self.table.classes.values():
            seen = {symbol.name}
            current = symbol.parent
            while current is not None:
                if current.name in seen:
                    self.bag.add(
                        "SEM207",
                        f"La clase '{symbol.name}' participa en un ciclo de herencia",
                        symbol.line,
                        symbol.column,
                    )
                    symbol.parent = None
                    symbol.class_type.parent = None
                    symbol.parent_name = None
                    break
                seen.add(current.name)
                current = current.parent

    def collect_members(self, ctx: Any) -> None:
        symbol = self.declared.get(id(ctx))
        if symbol is None:
            return
        for member in ctx.classMember():
            function_ctx = member.functionDeclaration()
            if function_ctx is not None:
                self._collect_method(symbol, function_ctx)
                continue
            declaration = member.variableDeclaration() or member.constantDeclaration()
            if declaration is not None:
                self._collect_attribute(symbol, declaration, member)

    def _collect_attribute(self, owner: ClassSymbol, ctx: Any, member: Any) -> None:
        name_node = ctx.Identifier()
        name = name_node.getText()
        line, column = position(name_node)
        if name in owner.attributes or name in owner.methods:
            self.bag.add(
                "SEM211",
                f"El miembro '{name}' ya existe en la clase '{owner.name}'",
                line,
                column,
            )
            return
        annotation = ctx.typeAnnotation()
        declared_type: Type = (
            self.resolver.resolve(annotation.type_()) if annotation is not None else ERROR
        )
        attribute = AttributeSymbol(
            name=name,
            type=declared_type,
            line=line,
            column=column,
            owner_class=owner.name,
            mutable=member.constantDeclaration() is None,
            initialized=annotation is not None,
        )
        owner.attributes[name] = attribute
        self.declared[id(ctx)] = attribute

    def _collect_method(self, owner: ClassSymbol, ctx: Any) -> None:
        name_node = ctx.Identifier()
        name = name_node.getText()
        line, column = position(name_node)
        if name in owner.methods or name in owner.attributes:
            self.bag.add(
                "SEM211",
                f"El miembro '{name}' ya existe en la clase '{owner.name}'",
                line,
                column,
            )
            return
        method = MethodSymbol(name=name, line=line, column=column, owner_class=owner.name)
        self.fill_signature(method, ctx)
        method.type = method.signature
        owner.methods[name] = method
        if name == CONSTRUCTOR_NAME:
            owner.constructor = method
        self.declared[id(ctx)] = method

    def check_overrides(self) -> None:
        """An override must keep the signature its parent declared."""
        for symbol in self.table.classes.values():
            for name, method in symbol.methods.items():
                inherited = None
                for ancestor in symbol.ancestors():
                    if name in ancestor.methods:
                        inherited = ancestor.methods[name]
                        break
                if inherited is None:
                    continue
                parameters = [item.type for item in method.parameters]
                expected = [item.type for item in inherited.parameters]
                compatible = parameters == expected and is_assignable(
                    inherited.return_type, method.return_type
                )
                if not compatible:
                    self.bag.add(
                        "SEM505",
                        f"'{name}' no respeta la firma heredada "
                        f"{inherited.signature} de '{inherited.owner_class}'",
                        method.line,
                        method.column,
                    )

    # -- functions ------------------------------------------------------
    def _declare_function(self, ctx: Any) -> Optional[FunctionSymbol]:
        name_node = ctx.Identifier()
        name = name_node.getText()
        line, column = position(name_node)
        symbol = FunctionSymbol(name=name, line=line, column=column)
        self.fill_signature(symbol, ctx)
        symbol.type = symbol.signature
        clash = self.table.environment.global_scope.define(symbol)
        if clash is not None:
            code = "SEM204" if clash.category.value in ("function", "method") else "SEM202"
            self.bag.add(
                code,
                f"'{name}' ya fue declarado en la línea {clash.line}",
                line,
                column,
            )
            return None
        self.declared[id(ctx)] = symbol
        return symbol

    def fill_signature(self, symbol: FunctionSymbol, ctx: Any) -> None:
        parameters_ctx = ctx.parameters()
        seen: dict[str, ParameterSymbol] = {}
        if parameters_ctx is not None:
            for index, parameter_ctx in enumerate(parameters_ctx.parameter()):
                parameter = self._build_parameter(parameter_ctx, index)
                if parameter.name in seen:
                    previous = seen[parameter.name]
                    self.bag.add(
                        "SEM203",
                        f"El parámetro '{parameter.name}' ya fue declarado en la "
                        f"linea {previous.line}",
                        parameter.line,
                        parameter.column,
                    )
                    continue
                seen[parameter.name] = parameter
                symbol.parameters.append(parameter)
        return_ctx = ctx.type_()
        symbol.return_annotated = return_ctx is not None
        symbol.return_type = (
            self.resolver.resolve(return_ctx) if return_ctx is not None else VOID
        )

    def _build_parameter(self, ctx: Any, index: int) -> ParameterSymbol:
        name_node = ctx.Identifier()
        name = name_node.getText()
        line, column = position(name_node)
        annotation = ctx.type_()
        if annotation is None:
            self.bag.add(
                "SEM210",
                f"El parámetro '{name}' necesita una anotación de tipo",
                line,
                column,
            )
            declared_type: Type = ERROR
        else:
            declared_type = self.resolver.resolve(annotation)
        return ParameterSymbol(
            name=name,
            type=declared_type,
            line=line,
            column=column,
            index=index,
        )
