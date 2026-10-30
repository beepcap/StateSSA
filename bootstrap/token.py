from enum import Enum, auto
from dataclasses import dataclass

class TokenType(Enum):
    # Keywords
    MACHINE = auto()
    FLOW = auto()
    STATES = auto()
    REG = auto()
    WIRE = auto()
    LET = auto()
    CALL = auto()
    EXTERN = auto()
    TYPE = auto()
    RETURN = auto()
    PANIC = auto()
    INCLUDE = auto()
    CAST = auto()

    # Literals & Identifiers
    IDENT = auto()
    INT_LIT = auto()
    STRING_LIT = auto()
    Q64_LIT = auto()

    # Symbols & Operators
    ARROW = auto()        # ->
    FAT_ARROW = auto()    # =>
    STORE = auto()        # <-
    COLON = auto()        # :
    SEMICOLON = auto()    # ;
    COMMA = auto()        # ,
    DOT = auto()          # .
    EQUALS = auto()       # =
    STAR = auto()         # *
    AMP = auto()          # &
    LPAREN = auto()       # (
    RPAREN = auto()       # )
    LBRACE = auto()       # {
    RBRACE = auto()       # }
    LBRACKET = auto()     # [
    RBRACKET = auto()     # ]
    UNDERSCORE = auto()   # _

    # Binary / Relational Ops
    PLUS = auto()         # +
    MINUS = auto()        # -
    SLASH = auto()        # /
    SHL = auto()          # <<
    SHR = auto()          # >>
    BIT_AND = auto()      # &
    BIT_OR = auto()       # |
    BIT_XOR = auto()      # ^
    EQ = auto()           # ==
    NEQ = auto()          # !=
    LEQ = auto()          # <=
    GEQ = auto()          # >=
    LT = auto()           # <
    GT = auto()           # >
    OR = auto()           # ||
    AND = auto()          # &&

    EOF = auto()

@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int
