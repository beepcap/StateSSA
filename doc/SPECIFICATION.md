# StateSSA (FlowState) 言語仕様書 (Version 0.12.0)

## 1. 概要と基本哲学

StateSSA は、ハードウェア設計（FPGA/ASIC）における**「データパス（Data Path）」**と**「コントロールパス（Control Path / FSM）」**の完全な直交分離を、ソフトウェア言語（LLVM IR）に直接持ち込んだ**純粋データフロー・有限状態遷移言語**である。

### 設計の基本原則（Anti-Magic & True Separation Guarantee）

1. **True Orthogonal Separation**: 
   * **データパス（`flow`）**：マシン全体に常時存在するレジスタ（`reg`）と、そこから伸びる無時間的な組み合わせ回路ワイヤー（`wire`）。
   * **コントロールパス（`states`）**：データを持たない純粋な状態記号（State）。状態の遷移と、遷移時のレジスタへのラッチ更新（`[ reg <= wire ]`）のみを司る。
2. **State Nodes Have No Arguments**: 状態（Basic Block）は引数を抱え込まない。状態がデータを所有することを厳格に禁止する。
3. **Absolute Purity of Expressions & Total Elimination of Ternary Branching (式の完全純粋性と三項演算子の根絶)**:
   式の中に暗黙の条件分岐（`? :` 三項演算子）を持ち込むことを完全排除する。無時間データパス（`flow`）は一切の隠蔽された制御フローを持たない純粋なワイヤー網であり、あらゆる条件選択は `states` ブロック内の明示的な FSM 状態ノード（デシジョン・ステート）として陽に記述されなければならない。これにより、Mermaid 状態遷移図とソースコードが 100% 透過になる。
4. **Explicit External ABI & Call Invariants**: 言語が暗黙に知っている魔法の関数は存在しない。真に C言語等の外部環境とやり取りする場合にのみ **`extern` 宣言** でシグネチャが明示される。
5. **Phi Nodes = State Registers + Latches**: LLVM IRの `phi` 命令は、`flow` で宣言された `reg` と、遷移時のラッチ `[ reg <= wire ]` に1対1で機械的にマッピングされる。
6. **Deterministic Memory Mutability**: メモリへの書き込み（副作用）は、特定の状態（State）内のアクションとして `Target <- Value;` によって明示的に行われる。
7. **Explicit Entry Invariant & Zero-Magic Control**:
   各マシンの `states` ブロックにおける第1ステートは、**必ず `Entry` という名前で宣言されなければならない**。また、LLVM IRのエントリーブロックが先行ブロック（Predecessors）を持てない物理制約を透過的に反映し、**`Entry` 状態へ逆戻りする遷移（`=> Entry`、自己ループ含む）は静的検証により厳格に禁止される**。
8. **Strict Single Definition Rule (単一定義の原則 / v0.12.0 新設)**:
   型（`type`）、マシン（`machine`）、外部関数（`extern fn`）の**多重定義・重複宣言の自動解決（曖昧な重複排除）を完全に廃止**する。プロジェクト内のすべてのシンボルはプロジェクト全体で **唯一無二（Single Source of Truth）** でなければならない。同一スコープ内に同名シンボルが複数回宣言・定義された場合、コンパイラは `SYMBOL_COLLISION_ERROR` として即座にコンパイルを拒絶する。

---

## 2. 構文構造（EBNF）

```ebnf
Program         ::= IncludeStmt* ( TypeDef | ExternBlock | MachineDef )*

IncludeStmt     ::= "include" StringLiteral ";"

ExternBlock     ::= "extern" StringLiteral? "{" ExternFnDecl* "}"
ExternFnDecl    ::= "fn" Identifier "(" ParamList? ")" "->" Type ";"

MachineDef      ::= "machine" Identifier "(" ParamList? ")" "->" Type "{"
                      FlowBlock?
                      StatesBlock
                    "}"

FlowBlock       ::= "flow" "{" ( RegDef | WireDef )* "}"
RegDef          ::= "reg" Identifier ":" Type ("=" PureExpr)? ";"
WireDef         ::= "wire" Identifier "=" PureExpr ";"

StatesBlock     ::= "states" "{" EntryStateDef StateDef* "}"
EntryStateDef   ::= "Entry" ":" "{"
                      ActionStmt*
                      TransitionRule*
                    "}"
StateDef        ::= Identifier ":" "{"
                      ActionStmt*
                      TransitionRule*
                    "}"

ActionStmt      ::= "let" ( Identifier | "_" ) "=" EffectExpr ";"
                  | "call" Identifier "(" ArgList? ")" ";"
                  | MemStore ";"

MemStore        ::= TargetLocation "<-" PureExpr
TargetLocation  ::= "*" PureExpr | PureExpr "." Identifier

TransitionRule  ::= ( GuardExpr | "_" ) "=>" TargetState ";"

TargetState     ::= Identifier ( "[" LatchList "]" )?
                  | "return" PureExpr?
                  | "panic" "(" PureExpr ")"

LatchList       ::= LatchAssignment ( "," LatchAssignment )*
LatchAssignment ::= Identifier "<=" PureExpr

PureExpr        ::= IntLiteral | StringLiteral | NullLiteral | Identifier | CastExpr | BinaryOp | UnaryOp | FieldAccess | StructLit
CastExpr        ::= "cast" "(" Type ")" PureExpr
EffectExpr      ::= "call" Identifier "(" ArgList? ")" | PureExpr

BinaryOp        ::= "+" | "-" | "*" | "/"
                  | "<<" | ">>" | "&" | "|" | "^"
                  | "==" | "!=" | "<" | "<=" | ">" | ">="
                  | "&&" | "||"

UnaryOp         ::= "*" | "&"

IntLiteral      ::= [0-9]+ | "0x"[0-9a-fA-F]+
NullLiteral     ::= "null"
```

> [!NOTE]
> `<Code><=</Code>` 記号の直交性について：
> 式中（`parse_relational`）における `<=` は比較演算子（Less-than-or-Equal）として解釈され、遷移先の角括弧内（`parse_rule` の `[...]`）における `<=` はラッチ代入演算子（Latch Assignment）として解釈される。文脈が完全に直交しているため、字句解析器で不自然なトークン競合ハックを行うことなく正当にパースされる。

---

## 3. 型システムとリテラル

### 3.1 ポインタ型と `null` リテラル
ポインタ型 `*T` は、メモリ上の型 `T` の先頭アドレスを指す値である。
* **`null` リテラル**: 有効なメモリ領域を指していないことを示すポインタ型の定数値（LLVM IR の `null` 定数に対応）。
* ポインタ型のレジスタ（`reg ptr: *u8 = null;`）の初期値などに使用される。
* 整数型（`i32`, `u32` 等）への代入は型エラーとなり、数値 `0` とは厳密に区別される。

### 3.2 ポインタ演算（加算・減算）
* **ポインタ加算（`ptr + offset`）**:
  ポインタ型と整数の加算は、LLVM IR の `getelementptr inbounds` 命令へと展開され、要素型 `T` のサイズに応じたアドレスオフセットを計算する。
* **ポインタ減算（`ptr1 - ptr2`）**:
  同一の要素型を持つポインタ同士の減算は、LLVM IR の `ptrtoint` 命令によって整数アドレスへと変換され、バイト差分整数（`i32`）を計算する。

### 3.3 デシジョン・ステート・パターン（三項演算子の代替）
StateSSA では、三項演算子（`cond ? a : b`）による条件代入を禁止し、FSM の状態分岐によって値を決定する。

```state-ssa
states {
    Evaluate: {
        is_match != 0 => NextState [ reg_mode <= 1 ];
        _             => NextState [ reg_mode <= 0 ];
    }
}
```

### 3.4 明示的キャスト (`cast(TargetType) expr` / v0.12.0 新設)
暗黙の型昇格や暗黙の切り捨て（`trunc` / `zext` の自動挿入）を完全排除したことに伴い、プログラマが意図した型変換を明示的に行う構文を導入する。
* **構文**: `cast(TargetType) operand`
  * 例: `let x = cast(i64) u8_val;`
  * 例: `wire w = cast(u32) i64_val;`
  * 例: `let p = cast(*u8) int_addr;`
* **動作原則**:
  * 整数拡張（ゼロ拡張 / 符号拡張）: `zext` 等を発行。
  * 整数縮小: `trunc` を発行。
  * ポインタと整数の相互変換: `ptrtoint` / `inttoptr` を発行。
  * ポインタ同士の変換: `bitcast` を発行。
  * 同一型へのキャスト: NOP（変換なしでそのまま値を伝播）。
* **完全明示の原則 (Zero-Magic Coercion)**:
  * コンパイラ自身のコードベース（`compiler_v11/src/`）を含め、すべての境界調停において暗黙の型縮小やポインタ変換は完全に禁止される。すべてのビット解釈変更は `cast(TargetType)` を用いて 100% 明示的に行われなければならない。

### 3.5 静的型バリデータと適合性マトリクス (Static Type Validator & Diagnostics Engine / v0.12.0 改定)
暗黙型変換パッチの完全根絶に伴い、コンパイラは不正な LLVM IR を出力して Clang にクラッシュさせるのではなく、自身のコード生成フェーズにおいて 4 大境界で静的に型整合性を検証し、違反時には詳細な診断通知を出力して安全停止する。

#### 1. 4大検証境界
1. **関数呼び出し引数 (`CALL_ARG`)**: 関数の仮引数型と呼び出し側の実引数型の適合性を検証。
2. **メモリ / 構造体ストア (`STORE`)**: 書き込み先の型（デリファレンス先または構造体フィールド型）と右辺式の型の適合性を検証。
3. **レジスタラッチ更新 (`LATCH`)**: `reg` 定義時の型と、遷移ルールにおけるラッチ代入式（`reg <= expr`）の型の適合性を検証。
4. **マシンの戻り値 (`RETURN`)**: マシン定義の戻り値型と、`return expr` 式の型の適合性を検証。

#### 2. 型適合性判定規則 (Compatibility Matrix)
* **完全一致 (`exp == act`)**: 適合 (PASS)。
* **ポインタ型同士 (`*exp == 42 && *act == 42`)**: LLVM opaque pointer 規約により相互に適合 (PASS)。
* **Null ポインタ代入**: ポインタ型の対象への `null` または `*void` の代入・受け渡しは適合 (PASS)。
* **ポインタと整数の暗黙混在**: **完全非互換 (FAIL)**。暗黙の `ptrtoint` / `inttoptr` は絶対に認められず、必ず `cast(T)` による明示を要求する。
* **整数型同士の適合判定**:
  * **整数リテラル**: リテラル数値（`0`, `48` 等）は、任意の整数型（`i8`〜`i64`, `u8`〜`u64`）に対して適合 (PASS)。
  * **安全な整数拡張 (Widening)**: 小さい整数から大きい整数への拡張（`act_bits <= exp_bits`）は情報の損失がないため適合 (PASS)。
  * **小ビット幅整数へのストア**: メモリストア（`STORE`）において、ストア先が `i8`, `u8`, `i16`, `u16`（`exp_bits <= 16`）であるバイト・ワード書き込みはハードウェアストアとして適合 (PASS)。
  * **大きな整数の暗黙縮小**: `i64` / `u64` から `i32` / `u32` への縮小（`act_bits > exp_bits` かつ `act_bits >= 32`）は、上位ビット欠落の重大なバグを防ぐため **完全非互換 (FAIL)**。必ず `cast(u32)` などの明示を要求する。

#### 3. 診断通知と安全停止規約
型不整合が検出された場合、コンパイラは標準エラー出力（stderr / `write(2, ...)`）に対して以下の構造化レポートを出力し、不正な IR を出力することなく**終了コード `-50` で即座に安全停止**する：

```text
================================================================================
[StateSSA Type Error]: Incompatible type detected!
  Kind:      Function Call Argument | Memory Store | Register Latch | Return Value
  Machine:   <マシンの識別子>
  State:     <発生ステートの識別子>
  Target:    <対象変数名・フィールド名・関数引数番号>
  Expected:  <期待される型名>
  Actual:    <実際の式型名> (expression: '<式のテキスト表現>')
  Fix Hint:  Explicit conversion required. Use 'cast(<Expected>) <expression>'
================================================================================
```

---

## 4. モジュール結合規約と単一定義の原則 (v0.12.0)

### 4.1 単一定義の原則 (Single Definition Rule)
v0.12.0 より、**シンボルの多重定義の自動解決は完全に廃止された**。
* 同一プロジェクト内で、同じ名前の `type`、`machine`、`extern fn` を複数回定義・宣言することは重大なコンパイルエラーとなる。
* 型定義やマシンの共通化は、`common.ssa` などの独立した共通ファイルに定義し、それをプロジェクト全体で共有することで実現する。
* 暗黙の重複排除に頼る「勝手な同名定義」を排除することで、モジュール間の責務境界が物理的に強制される。

### 4.2 `include "path.ssa";`
* ファイル間の構造的依存関係をコード上で宣言する。
* コンパイラは重複して同一ファイルが include された場合、ヘッダガード相当の処理によりファイル単位での重複読み込みをスキップする。

### 4.3 プロジェクト一括結合 (`ssac src/*.ssa`)
* コマンドライン引数で複数ファイルを一括指定して結合する：
  ```bash
  ssac common.ssa lexer.ssa parser.ssa codegen.ssa -o compiler.ll
  ```
* すべてのファイルで定義されたシンボルは単一のグローバル空間に展開されるが、シンボルの重複が存在した場合は即座にエラーを出力して停止する。

---

## 5. 標準ライブラリ規約 (STL: `common.ssa`)

汎用メモリ管理モジュール `common.ssa` は、すべての StateSSA プログラム（コンパイラ、Web サーバ、ゲームエンジン等）で利用可能な純粋な標準ライブラリ（STL）として定義される。

* **`MemSlice`**: 汎用メモリスライス（ポインタと長さ）。
* **`BumpAlloc`**: 汎用バンプアロケータ構造体（`base_ptr`, `offset`, `capacity`）。
* **`init_bump_alloc`**: アロケータ初期化マシン。
* **`bump_alloc`**: 監視付きメモリ切り出しマシン。**領域オーバーフロー時は即時に `panic(1)` を発行し、サイレントな破壊を防ぐ**。
* **`MemPartition`**: 非重畳静的パーティションアロケータ。
* **ドメイン汚染の禁止**: `common.ssa` には、コンパイラ固有のメモリ算定（`calc_compiler_required_memory` 等）のような特定アプリケーションに依存したロジックを配置してはならない。
