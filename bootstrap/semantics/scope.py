from typing import Optional
from ..types import Type

class Scope:
    def __init__(self, parent: Optional["Scope"] = None):
        self.parent = parent
        self.symbols: dict[str, Type] = {}

    def define(self, name: str, type_: Type):
        self.symbols[name] = type_

    def lookup(self, name: str) -> Optional[Type]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def enter_scope(self) -> "Scope":
        return Scope(parent=self)
