from typing import Any
from .token import TokenType, Token
from .ast_nodes import Program, Machine, Flow, Reg, Wire, State, Rule, Action, TypeDef, ExternFn
from .expr_nodes import BinaryExpr, UnaryExpr, CallExpr, FieldExpr, StructLit, VarExpr, IntLit, StringLit, NullLit, CastExpr, Q64Lit
from .lexer import parse_q64_str

class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def match(self, *types: TokenType) -> bool:
        if self.peek().type in types:
            self.pos += 1
            return True
        return False

    def expect(self, ttype: TokenType) -> Token:
        tok = self.peek()
        if tok.type != ttype:
            raise SyntaxError(f"Expected {ttype.name}, got {tok.type.name} ('{tok.value}') at line {tok.line}")
        self.pos += 1
        return tok

    def parse_program(self) -> Program:
        includes, types, externs, machines = [], [], [], []
        while self.peek().type != TokenType.EOF:
            if self.peek().type == TokenType.INCLUDE:
                self.expect(TokenType.INCLUDE)
                inc_path = self.expect(TokenType.STRING_LIT).value
                self.expect(TokenType.SEMICOLON)
                includes.append(inc_path)
            elif self.peek().type == TokenType.TYPE:
                types.append(self.parse_type_def())
            elif self.peek().type == TokenType.EXTERN:
                externs.extend(self.parse_extern_block())
            elif self.peek().type == TokenType.MACHINE:
                machines.append(self.parse_machine())
            else:
                raise SyntaxError(f"Unexpected token {self.peek().value} at top-level")
        return Program(includes, types, externs, machines)

    def parse_type_def(self) -> TypeDef:
        self.expect(TokenType.TYPE)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.EQUALS)
        if self.match(TokenType.STAR):
            target_type = self.expect(TokenType.IDENT).value
            self.expect(TokenType.SEMICOLON)
            return TypeDef(name, [("__ptr__", f"*{target_type}")])
        self.expect(TokenType.LBRACE)
        fields = []
        while not self.match(TokenType.RBRACE):
            fname = self.expect(TokenType.IDENT).value
            self.expect(TokenType.COLON)
            ftype = self.parse_type_str()
            self.match(TokenType.COMMA)
            fields.append((fname, ftype))
        self.expect(TokenType.SEMICOLON)
        return TypeDef(name, fields)

    def parse_extern_block(self) -> list[ExternFn]:
        self.expect(TokenType.EXTERN)
        if self.peek().type == TokenType.STRING_LIT:
            self.pos += 1
        self.expect(TokenType.LBRACE)
        fns = []
        while not self.match(TokenType.RBRACE):
            self.expect(TokenType.IDENT) # 'fn'
            fname = self.expect(TokenType.IDENT).value
            self.expect(TokenType.LPAREN)
            params = []
            while not self.match(TokenType.RPAREN):
                pname = self.expect(TokenType.IDENT).value
                self.expect(TokenType.COLON)
                ptype = self.parse_type_str()
                self.match(TokenType.COMMA)
                params.append((pname, ptype))
            self.expect(TokenType.ARROW)
            ret_type = self.parse_type_str()
            self.expect(TokenType.SEMICOLON)
            fns.append(ExternFn(fname, params, ret_type))
        return fns

    def parse_type_str(self) -> str:
        prefix = ""
        while self.match(TokenType.STAR):
            prefix += "*"
        base = self.expect(TokenType.IDENT).value
        return prefix + base

    def parse_machine(self) -> Machine:
        self.expect(TokenType.MACHINE)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.LPAREN)
        params = []
        while not self.match(TokenType.RPAREN):
            pname = self.expect(TokenType.IDENT).value
            self.expect(TokenType.COLON)
            ptype = self.parse_type_str()
            self.match(TokenType.COMMA)
            params.append((pname, ptype))
        self.expect(TokenType.ARROW)
        ret_type = self.parse_type_str()
        self.expect(TokenType.LBRACE)

        flow = self.parse_flow()
        states = self.parse_states()
        self.expect(TokenType.RBRACE)
        return Machine(name, params, ret_type, flow, states)

    def parse_flow(self) -> Flow:
        self.expect(TokenType.FLOW)
        self.expect(TokenType.LBRACE)
        regs, wires = [], []
        while not self.match(TokenType.RBRACE):
            if self.match(TokenType.REG):
                rname = self.expect(TokenType.IDENT).value
                self.expect(TokenType.COLON)
                rtype = self.parse_type_str()
                init_expr = None
                if self.match(TokenType.EQUALS):
                    init_expr = self.parse_expr()
                self.expect(TokenType.SEMICOLON)
                regs.append(Reg(rname, rtype, init_expr))
            elif self.match(TokenType.WIRE):
                wname = self.expect(TokenType.IDENT).value
                self.expect(TokenType.EQUALS)
                wexpr = self.parse_expr()
                self.expect(TokenType.SEMICOLON)
                wires.append(Wire(wname, wexpr))
            else:
                raise SyntaxError(f"Unexpected token {self.peek().value} in flow")
        return Flow(regs, wires)

    def parse_states(self) -> list[State]:
        self.expect(TokenType.STATES)
        self.expect(TokenType.LBRACE)
        states = []
        while not self.match(TokenType.RBRACE):
            sname = self.expect(TokenType.IDENT).value
            self.expect(TokenType.COLON)
            self.expect(TokenType.LBRACE)
            actions = []
            rules = []
            while not self.match(TokenType.RBRACE):
                if self.match(TokenType.LET):
                    if self.match(TokenType.UNDERSCORE):
                        tname = "_"
                    else:
                        tname = self.expect(TokenType.IDENT).value
                    self.expect(TokenType.EQUALS)
                    expr = self.parse_expr()
                    self.expect(TokenType.SEMICOLON)
                    actions.append(Action("let", tname, expr))
                elif self.match(TokenType.CALL):
                    expr = self.parse_call_expr()
                    self.expect(TokenType.SEMICOLON)
                    actions.append(Action("call", None, expr))
                elif self.is_rule_start():
                    rules.append(self.parse_rule())
                else:
                    # MemStore: target_expr <- val_expr ;
                    target = self.parse_expr()
                    self.expect(TokenType.STORE)
                    val = self.parse_expr()
                    self.expect(TokenType.SEMICOLON)
                    actions.append(Action("store", target, val))
            states.append(State(sname, actions, rules))
        return states

    def is_rule_start(self) -> bool:
        if self.peek().type == TokenType.UNDERSCORE:
            return True
        # Lookahead for '=>'
        for i in range(self.pos, min(self.pos + 10, len(self.tokens))):
            if self.tokens[i].type == TokenType.FAT_ARROW:
                return True
            if self.tokens[i].type in (TokenType.SEMICOLON, TokenType.STORE):
                return False
        return False

    def parse_rule(self) -> Rule:
        guard = None
        if not self.match(TokenType.UNDERSCORE):
            guard = self.parse_expr()
        self.expect(TokenType.FAT_ARROW)

        if self.match(TokenType.RETURN):
            ret_expr = None
            if not self.match(TokenType.SEMICOLON):
                ret_expr = self.parse_expr()
                self.expect(TokenType.SEMICOLON)
            return Rule(guard, None, [], is_return=True, ret_expr=ret_expr)
        elif self.match(TokenType.PANIC):
            self.expect(TokenType.LPAREN)
            err_expr = self.parse_expr()
            self.expect(TokenType.RPAREN)
            self.expect(TokenType.SEMICOLON)
            return Rule(guard, None, [], is_panic=True, ret_expr=err_expr)

        target = self.expect(TokenType.IDENT).value
        latches = []
        if self.match(TokenType.LBRACKET):
            while not self.match(TokenType.RBRACKET):
                rname = self.expect(TokenType.IDENT).value
                self.expect(TokenType.LEQ)
                lexpr = self.parse_expr()
                self.match(TokenType.COMMA)
                latches.append((rname, lexpr))
        self.expect(TokenType.SEMICOLON)
        return Rule(guard, target, latches)

    def parse_expr(self) -> Any:
        return self.parse_logic_or()

    def parse_logic_or(self) -> Any:
        left = self.parse_logic_and()
        while self.match(TokenType.OR):
            right = self.parse_logic_and()
            left = BinaryExpr("||", left, right)
        return left

    def parse_logic_and(self) -> Any:
        left = self.parse_bit_or()
        while self.match(TokenType.AND):
            right = self.parse_bit_or()
            left = BinaryExpr("&&", left, right)
        return left

    def parse_bit_or(self) -> Any:
        left = self.parse_bit_xor()
        while self.match(TokenType.BIT_OR):
            right = self.parse_bit_xor()
            left = BinaryExpr("|", left, right)
        return left

    def parse_bit_xor(self) -> Any:
        left = self.parse_bit_and()
        while self.match(TokenType.BIT_XOR):
            right = self.parse_bit_and()
            left = BinaryExpr("^", left, right)
        return left

    def parse_bit_and(self) -> Any:
        left = self.parse_relational()
        while self.match(TokenType.BIT_AND):
            right = self.parse_relational()
            left = BinaryExpr("&", left, right)
        return left

    def parse_relational(self) -> Any:
        left = self.parse_shift()
        for op_type, op_str in [(TokenType.EQ, "=="), (TokenType.NEQ, "!="),
                                (TokenType.LEQ, "<="), (TokenType.GEQ, ">="),
                                (TokenType.LT, "<"), (TokenType.GT, ">")]:
            if self.match(op_type):
                right = self.parse_shift()
                return BinaryExpr(op_str, left, right)
        return left

    def parse_shift(self) -> Any:
        left = self.parse_additive()
        while True:
            if self.match(TokenType.SHL):
                left = BinaryExpr("<<", left, self.parse_additive())
            elif self.match(TokenType.SHR):
                left = BinaryExpr(">>", left, self.parse_additive())
            else:
                break
        return left

    def parse_additive(self) -> Any:
        left = self.parse_multiplicative()
        while True:
            if self.match(TokenType.PLUS):
                left = BinaryExpr("+", left, self.parse_multiplicative())
            elif self.match(TokenType.MINUS):
                left = BinaryExpr("-", left, self.parse_multiplicative())
            else:
                break
        return left

    def parse_multiplicative(self) -> Any:
        left = self.parse_unary()
        while True:
            if self.match(TokenType.STAR):
                left = BinaryExpr("*", left, self.parse_unary())
            elif self.match(TokenType.SLASH):
                left = BinaryExpr("/", left, self.parse_unary())
            else:
                break
        return left

    def parse_unary(self) -> Any:
        if self.match(TokenType.CAST):
            self.expect(TokenType.LPAREN)
            target_type = self.parse_type_str()
            self.expect(TokenType.RPAREN)
            operand = self.parse_unary()
            return CastExpr(target_type, operand)
        if self.match(TokenType.MINUS):
            operand = self.parse_unary()
            if isinstance(operand, IntLit):
                return IntLit(-operand.val)
            if isinstance(operand, Q64Lit):
                return Q64Lit(-operand.val)
            return BinaryExpr("-", IntLit(0), operand)
        if self.match(TokenType.STAR):
            return UnaryExpr("*", self.parse_unary())
        if self.match(TokenType.BIT_AND):
            return UnaryExpr("&", self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self) -> Any:
        base = self.parse_primary()
        while True:
            if self.match(TokenType.DOT):
                field = self.expect(TokenType.IDENT).value
                base = FieldExpr(base, field)
            else:
                break
        return base

    def parse_primary(self) -> Any:
        if self.match(TokenType.CALL):
            return self.parse_call_expr()
        if self.match(TokenType.LPAREN):
            e = self.parse_expr()
            self.expect(TokenType.RPAREN)
            return e
        if self.peek().type == TokenType.INT_LIT:
            val = int(self.expect(TokenType.INT_LIT).value, 0)
            return IntLit(val)
        if self.peek().type == TokenType.Q64_LIT:
            tok = self.expect(TokenType.Q64_LIT)
            val = parse_q64_str(tok.value)
            return Q64Lit(val)
        if self.peek().type == TokenType.STRING_LIT:
            val = self.expect(TokenType.STRING_LIT).value
            return StringLit(val)
        if self.peek().type == TokenType.IDENT:
            name = self.expect(TokenType.IDENT).value
            if name == "null":
                return NullLit()
            # Struct literal: TypeName { ... }
            if self.peek().type == TokenType.LBRACE:
                self.expect(TokenType.LBRACE)
                fields = []
                while not self.match(TokenType.RBRACE):
                    fname = self.expect(TokenType.IDENT).value
                    self.expect(TokenType.COLON)
                    fexpr = self.parse_expr()
                    self.match(TokenType.COMMA)
                    fields.append((fname, fexpr))
                return StructLit(name, fields)
            return VarExpr(name)
        raise SyntaxError(f"Unexpected token {self.peek().value} in primary expr at line {self.peek().line}")

    def parse_call_expr(self) -> CallExpr:
        func = self.expect(TokenType.IDENT).value
        self.expect(TokenType.LPAREN)
        args = []
        while not self.match(TokenType.RPAREN):
            args.append(self.parse_expr())
            self.match(TokenType.COMMA)
        return CallExpr(func, args)
