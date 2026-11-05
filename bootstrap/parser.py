from typing import Any
from .token import TokenType, Token
from .ast_nodes import Program, Machine, Flow, Reg, Wire, State, Rule, Action, TypeDef, TypeKind, BoundsNode, ExternFn, ParamDecl, NodeDecl, ConnectPipeline, NetworkDecl
from .expr_nodes import BinaryExpr, UnaryExpr, CallExpr, FieldExpr, StructLit, VarExpr, IntLit, StringLit, NullLit, CastExpr, Q64Lit, FloatLit
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
            if ttype == TokenType.IDENT and tok.type == TokenType.NODE:
                self.pos += 1
                return tok
            raise SyntaxError(f"Expected {ttype.name}, got {tok.type.name} ('{tok.value}') at line {tok.line}")
        self.pos += 1
        return tok

    def parse_program(self) -> Program:
        includes, types, externs, machines, networks = [], [], [], [], []
        while self.peek().type != TokenType.EOF:
            if self.peek().type == TokenType.INCLUDE:
                self.expect(TokenType.INCLUDE)
                inc_path = self.expect(TokenType.STRING_LIT).value
                self.expect(TokenType.SEMICOLON)
                includes.append(inc_path)
            elif self.peek().type == TokenType.TYPE:
                tdef = self.parse_type_def()
                if any(t.name == tdef.name for t in types):
                    raise SyntaxError(f"Duplicate type definition '{tdef.name}'")
                types.append(tdef)
            elif self.peek().type == TokenType.EXTERN:
                externs.extend(self.parse_extern_block())
            elif self.peek().type == TokenType.MACHINE:
                machines.append(self.parse_machine())
            elif self.peek().type == TokenType.NETWORK:
                networks.append(self.parse_network())
            else:
                raise SyntaxError(f"Unexpected token {self.peek().value} at top-level")
        return Program(includes, types, externs, machines, networks)

    def parse_bound_expr(self) -> Any:
        if self.match(TokenType.MINUS):
            operand = self.parse_bound_expr()
            if isinstance(operand, IntLit):
                return IntLit(-operand.val)
            if isinstance(operand, FloatLit):
                return FloatLit(-operand.val, f"-{operand.raw_str}")
            raise SyntaxError(f"Expected numeric literal after '-' in bound range at line {self.peek().line}")

        if self.peek().type == TokenType.FLOAT_LIT:
            tok = self.expect(TokenType.FLOAT_LIT)
            return FloatLit(float(tok.value), tok.value)

        if self.peek().type == TokenType.INT_LIT:
            tok = self.expect(TokenType.INT_LIT)
            return IntLit(int(tok.value))

        tok = self.peek()
        raise SyntaxError(f"Expected numeric literal in bound range, got {tok.type.name} ('{tok.value}') at line {tok.line}")

    def parse_type_def(self) -> TypeDef:
        self.expect(TokenType.TYPE)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.EQUALS)
        if self.match(TokenType.LBRACE):
            fields = []
            while not self.match(TokenType.RBRACE):
                fname = self.expect(TokenType.IDENT).value
                self.expect(TokenType.COLON)
                ftype = self.parse_type_str()
                self.match(TokenType.COMMA)
                fields.append((fname, ftype))
            self.expect(TokenType.SEMICOLON)
            return TypeDef(name=name, kind=TypeKind.STRUCT, fields=fields)

        base_type = self.parse_type_str()
        if self.match(TokenType.LBRACKET):
            min_expr = self.parse_bound_expr()
            if not self.match(TokenType.DOTDOT):
                raise SyntaxError(f"Expected '..' (DOTDOT) in range constraint at line {self.peek().line}")
            max_expr = self.parse_bound_expr()
            self.expect(TokenType.RBRACKET)
            self.expect(TokenType.SEMICOLON)
            return TypeDef(name=name, kind=TypeKind.BOUNDED, base_type=base_type, bounds=BoundsNode(min_expr, max_expr))

        self.expect(TokenType.SEMICOLON)
        return TypeDef(name=name, kind=TypeKind.NEWTYPE, base_type=base_type, fields=[])

    def parse_param(self) -> ParamDecl:
        pname = self.expect(TokenType.IDENT).value
        self.expect(TokenType.COLON)
        is_distinct = self.match(TokenType.DISTINCT)
        ptype = self.parse_type_str()
        return ParamDecl(name=pname, type_str=ptype, is_distinct=is_distinct)

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
            params: list[ParamDecl] = []
            while not self.match(TokenType.RPAREN):
                params.append(self.parse_param())
                self.match(TokenType.COMMA)
            self.expect(TokenType.ARROW)
            if self.peek().type == TokenType.DISTINCT:
                raise SyntaxError("Unexpected token DISTINCT in return type")
            ret_type = self.parse_type_str()
            self.expect(TokenType.SEMICOLON)
            fns.append(ExternFn(fname, params, ret_type))
        return fns

    def parse_type_str(self) -> str:
        if self.match(TokenType.LPAREN):
            t = self.parse_type_str()
            self.expect(TokenType.RPAREN)
            return t
        prefix = ""
        while self.match(TokenType.STAR):
            prefix += "*"
        if self.peek().type == TokenType.LPAREN:
            self.expect(TokenType.LPAREN)
            inner = self.parse_type_str()
            self.expect(TokenType.RPAREN)
            return prefix + inner
        base = self.expect(TokenType.IDENT).value
        return prefix + base

    def parse_machine(self) -> Machine:
        self.expect(TokenType.MACHINE)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.LPAREN)
        params: list[ParamDecl] = []
        while not self.match(TokenType.RPAREN):
            params.append(self.parse_param())
            self.match(TokenType.COMMA)
        self.expect(TokenType.ARROW)
        if self.peek().type == TokenType.DISTINCT:
            raise SyntaxError("Unexpected token DISTINCT in return type")
        ret_type = self.parse_type_str()
        self.expect(TokenType.LBRACE)

        flow = self.parse_flow()
        states = self.parse_states()
        self.expect(TokenType.RBRACE)
        return Machine(name, params, ret_type, flow, states)

    def parse_network(self) -> NetworkDecl:
        self.expect(TokenType.NETWORK)
        net_name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.LPAREN)
        params: list[ParamDecl] = []
        while not self.match(TokenType.RPAREN):
            params.append(self.parse_param())
            self.match(TokenType.COMMA)
        self.expect(TokenType.ARROW)
        if self.peek().type == TokenType.DISTINCT:
            raise SyntaxError("Unexpected token DISTINCT in return type")
        ret_type = self.parse_type_str()
        self.expect(TokenType.LBRACE)

        nodes: list[NodeDecl] = []
        while self.match(TokenType.NODE):
            node_id = self.expect(TokenType.IDENT).value
            self.expect(TokenType.COLON)
            m_name = self.expect(TokenType.IDENT).value
            self.expect(TokenType.SEMICOLON)
            nodes.append(NodeDecl(node_id, m_name))

        self.expect(TokenType.CONNECT)
        self.expect(TokenType.LBRACE)
        pipelines: list[ConnectPipeline] = []
        while not self.match(TokenType.RBRACE):
            elements = [self.expect(TokenType.IDENT).value]
            while self.match(TokenType.SHR):
                elements.append(self.expect(TokenType.IDENT).value)
            self.expect(TokenType.SEMICOLON)
            pipelines.append(ConnectPipeline(elements))

        self.expect(TokenType.RBRACE)
        return NetworkDecl(net_name, params, ret_type, nodes, pipelines)

    def parse_flow(self) -> Flow:
        self.expect(TokenType.FLOW)
        self.expect(TokenType.LBRACE)
        regs, wires = [], []
        while not self.match(TokenType.RBRACE):
            if self.match(TokenType.REG):
                rname = self.expect(TokenType.IDENT).value
                self.expect(TokenType.COLON)
                if self.peek().type == TokenType.DISTINCT:
                    raise SyntaxError("Unexpected token DISTINCT in flow register declaration")
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
                if self.peek().type == TokenType.DISTINCT:
                    raise SyntaxError("Unexpected token DISTINCT in action")
                if self.match(TokenType.LET):
                    if self.peek().type == TokenType.DISTINCT:
                        raise SyntaxError("Unexpected token DISTINCT in action")
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
            if isinstance(operand, FloatLit):
                return FloatLit(-operand.val, f"-{operand.raw_str}")
            return UnaryExpr("-", operand)
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
        if self.peek().type == TokenType.FLOAT_LIT:
            tok = self.expect(TokenType.FLOAT_LIT)
            return FloatLit(float(tok.value), tok.value)
        if self.peek().type == TokenType.STRING_LIT:
            val = self.expect(TokenType.STRING_LIT).value
            return StringLit(val)
        if self.peek().type in (TokenType.IDENT, TokenType.NODE):
            name = self.expect(self.peek().type).value
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
