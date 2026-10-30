import re
from .token import TokenType, Token

KEYWORDS = {
    "machine": TokenType.MACHINE,
    "flow": TokenType.FLOW,
    "states": TokenType.STATES,
    "reg": TokenType.REG,
    "wire": TokenType.WIRE,
    "let": TokenType.LET,
    "call": TokenType.CALL,
    "extern": TokenType.EXTERN,
    "type": TokenType.TYPE,
    "return": TokenType.RETURN,
    "panic": TokenType.PANIC,
    "include": TokenType.INCLUDE,
    "cast": TokenType.CAST,
}

SYMBOLS = [
    ("<<", TokenType.SHL),
    (">>", TokenType.SHR),
    ("->", TokenType.ARROW),
    ("=>", TokenType.FAT_ARROW),
    ("<=", TokenType.LEQ),
    ("<-", TokenType.STORE),
    ("==", TokenType.EQ),
    ("!=", TokenType.NEQ),
    (">=", TokenType.GEQ),
    ("||", TokenType.OR),
    ("&&", TokenType.AND),
    ("<", TokenType.LT),
    (">", TokenType.GT),
    ("&", TokenType.BIT_AND),
    ("|", TokenType.BIT_OR),
    ("^", TokenType.BIT_XOR),
    (":", TokenType.COLON),
    (";", TokenType.SEMICOLON),
    (",", TokenType.COMMA),
    (".", TokenType.DOT),
    ("=", TokenType.EQUALS),
    ("*", TokenType.STAR),
    ("+", TokenType.PLUS),
    ("-", TokenType.MINUS),
    ("/", TokenType.SLASH),
    ("(", TokenType.LPAREN),
    (")", TokenType.RPAREN),
    ("{", TokenType.LBRACE),
    ("}", TokenType.RBRACE),
    ("[", TokenType.LBRACKET),
    ("]", TokenType.RBRACKET),
    ("_", TokenType.UNDERSCORE),
]

def parse_q64_str(text: str) -> int:
    if '.' not in text:
        return int(text) << 32
    int_part_str, frac_part_str = text.split('.', 1)
    int_part = int(int_part_str) if int_part_str else 0
    frac_part_str = frac_part_str[:9]
    num = int(frac_part_str) if frac_part_str else 0
    denom = 10 ** len(frac_part_str) if frac_part_str else 1
    frac_q64 = (num * 4294967296 + denom // 2) // denom
    return (int_part << 32) + frac_q64

class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1

    def tokenize(self) -> list[Token]:
        tokens = []
        while self.pos < len(self.text):
            # Skip whitespace
            if self.text[self.pos].isspace():
                if self.text[self.pos] == '\n':
                    self.line += 1
                    self.col = 1
                else:
                    self.col += 1
                self.pos += 1
                continue

            # Skip comments
            if self.text.startswith("//", self.pos):
                end = self.text.find('\n', self.pos)
                if end == -1: break
                self.pos = end
                continue

            # Decimal float literal (e.g. 1.5, 0.125) -> Q64_LIT
            m = re.match(r'[0-9]+\.[0-9]+', self.text[self.pos:])
            if m:
                num = m.group(0)
                tokens.append(Token(TokenType.Q64_LIT, num, self.line, self.col))
                self.pos += len(num)
                self.col += len(num)
                continue

            # Check symbols
            matched_symbol = False
            for sym, ttype in SYMBOLS:
                if self.text.startswith(sym, self.pos):
                    tokens.append(Token(ttype, sym, self.line, self.col))
                    self.pos += len(sym)
                    self.col += len(sym)
                    matched_symbol = True
                    break
            if matched_symbol: continue

            # String literal
            if self.text[self.pos] == '"':
                start = self.pos + 1
                end = self.text.find('"', start)
                val = self.text[start:end]
                tokens.append(Token(TokenType.STRING_LIT, val, self.line, self.col))
                self.col += (end + 1 - self.pos)
                self.pos = end + 1
                continue

            # Identifiers / Keywords
            m = re.match(r'[a-zA-Z_][a-zA-Z0-9_]*', self.text[self.pos:])
            if m:
                ident = m.group(0)
                ttype = KEYWORDS.get(ident, TokenType.IDENT)
                tokens.append(Token(ttype, ident, self.line, self.col))
                self.pos += len(ident)
                self.col += len(ident)
                continue

            # Integer literal (decimal or hex)
            m = re.match(r'0[xX][0-9a-fA-F]+|[0-9]+', self.text[self.pos:])
            if m:
                num = m.group(0)
                tokens.append(Token(TokenType.INT_LIT, num, self.line, self.col))
                self.pos += len(num)
                self.col += len(num)
                continue

            raise SyntaxError(f"Unexpected char '{self.text[self.pos]}' at {self.line}:{self.col}")

        tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return tokens
