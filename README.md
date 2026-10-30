# StateSSA

StateSSA は、有限状態機械（Finite State Machine; FSM）と静的単一代入（Static Single Assignment; SSA）データフローで直接記述するプログラミング言語です。

高水準言語の構文木（AST）への翻訳を行わず、不変のデータストリーム（ワイヤー）、離散的な状態遷移（ステート）、および 1-bit 述語による遷移エッジ（ガード）により、予測可能な実行パイプラインを構築します。

---

## 1. ディレクトリ構成とファイル配置

リポジトリ内のディレクトリ構成は以下の通りです：

```text
StateSSA/
├── configure           # POSIX 準拠の環境検証 ＆ Stage-3 自動ブートストラップスクリプト
├── LICENSE             # ライセンスファイル (BSD 3-Clause)
├── README.md           # 本ドキュメント
├── RELEASE_NOTES.md    # リリースノート
│
├── bootstrap/          # Stage-0 Python ブートストラップコンパイラ
│   ├── main.py         # Stage-0 CLI エントリーポイント (キューローダー内包)
│   ├── lexer.py        # 字句解析器
│   ├── parser.py       # 構文解析器
│   └── codegen.py      # LLVM IR コード生成エンジン (q64 / C-ABI 自動変換)
│
├── source/             # StateSSA で記述されたセルフホストコンパイラソース
│   ├── common.ssa      # 共通構造体型・メモリ確保・診断通知エンジン
│   ├── lexer.ssa       # 字句解析 FSM
│   ├── parser.ssa      # 構文解析 FSM (extern マージ・include パス解決内包)
│   ├── codegen.ssa     # LLVM IR コード生成 FSM (静的型バリデータ・q64/C-ABI自動変換)
│   └── driver.ssa      # CLI 引数解析・ファイルキューローダー・動的メモリ算定
│
├── doc/                # 言語仕様書
│   └── SPECIFICATION.md# 言語仕様書
│
└── samples/            # StateSSA サンプル集 (C言語ファイルなし)
    ├── 01_hello_world/ # 最小構成の Hello World
    ├── 02_simple_loop/ # ループとレジスタラッチ更新
    ├── 03_parallel_sum/# POSIX pthread による並行タスクオーケストレーション
    ├── 04_xz/          # LZMA2 ＆ XZ コンテナの圧縮・解凍ラウンドトリップ
    ├── 05_web_server/  # Linux io_uring による非同期 Web サーバー
    └── 06_fixed_math/  # q64 固定小数点数による実数計算と C-ABI 境界自動変換
```

---

## 2. ビルドと環境構築 (Setup & Build)

### 前提要件
* `clang` (LLVM C/IR コンパイラ)
* `python3` (初回 Stage-0 ブートストラップ用)
* `cmp`, `make` (POSIX 標準ユーティリティ)

### ブートストラップ
リポジトリのルートで `./configure` を実行します：

```sh
./configure
```

* **既存のコンパイラがある場合**: `bin/ssac` を検知して即座に完了します。
* **初回実行時**:
  1. `bootstrap/`（Python Stage-0）で `source/driver.ssa` をコンパイルし、Stage-1 IR を生成。
  2. `clang` でビルドした Stage-1 コンパイラで自身（`source/driver.ssa`）をコンパイルし、Stage-2 IR を生成。
  3. Stage-2 コンパイラで自身をコンパイルし、Stage-3 IR を生成。
  4. Stage-2 IR と Stage-3 IR の **固定点照合 (Fixed-Point Verification)** を実行（完全一致を確認）。
  5. Stage-3 バイナリを `bin/ssac` としてインストールし、ルート `Makefile` を自動生成します。

---

## 3. サンプルのビルドとお試し方法

すべてのサンプルは C 言語ファイルを用いず、StateSSA（`.ssa`）のみで構成されています。

### ① 全サンプルの一括ビルド＆検証
ルートディレクトリで以下のコマンドを実行すると、全サンプルのコンパイルと自己検証テストが走ります：

```sh
make test
```

実行結果の例：
```text
============================================================
Running All StateSSA Sample Verifications
============================================================
--- [Test 1/6] 01_hello_world ---
Hello, StateSSA World!

--- [Test 2/6] 02_simple_loop ---
simple_loop(10) = 45: SUCCESS!

--- [Test 3/6] 03_parallel_sum ---
ParallelSum([1..8]) = 36: SUCCESS!

--- [Test 4/6] 04_xz ---
XZ Clone (Compress -> Decompress Roundtrip): 100% SUCCESS!

--- [Test 5/6] 05_web_server (Self-Test) ---
StateSSA io_uring Web Server listening on 0.0.0.0:18080...
GET / -> 200 OK & Hello verified!
GET /baseline11 -> 200 OK & Sum 100 verified!
POST /echo -> 200 OK & Echo verified!
web_server verification passed.

--- [Test 6/6] 06_fixed_math ---
=== StateSSA Sample 06: Deterministic Math (q64) ===
a + b (expected 3.500000): 3.500000
b - a (expected 0.500000): 0.500000
a * b (expected 3.000000): 3.000000
a / b (expected 0.750000): 0.750000
altitude at t=1.0s (expected 15.100000): 15.100000
sin(0.0) (expected 0.000000): 0.000000
cos(0.0) (expected 1.000000): 1.000000
sqrt(4.0) (expected 2.000000): 2.000000

============================================================
>>> ALL SAMPLES PASSED 100% ON STAGE-3 BINARY COMPILER! <<<
============================================================
```

---

### ② 個別サンプルの手動ビルド＆お試し手順

#### 01. Hello World (`samples/01_hello_world/`)
最小限のエントリーポイントと文字列出力のサンプルです。

```sh
# ビルド
make 01_hello_world

# 実行
./build/01/hello
# 出力: Hello, StateSSA World!
```

#### 02. Simple Loop (`samples/02_simple_loop/`)
レジスタラッチ代入（`res <= ...`）と 1-bit predicate ガードによる有限状態ループです。

```sh
# ビルド
make 02_simple_loop

# 実行
./build/02/simple_loop
# 出力: simple_loop(10) = 45: SUCCESS!
```

#### 03. Parallel Sum (`samples/03_parallel_sum/`)
StateSSA から直接 POSIX `pthread` を呼び出し、2つのスレッドで並列に配列要素を合算して同期・回収します。

```sh
# ビルド
make 03_parallel_sum

# 実行
./build/03/parallel_sum
# 出力: ParallelSum([1..8]) = 36: SUCCESS!
```

#### 04. XZ Clone (`samples/04_xz/`)
LZMA2、CRC32、マッチファインダ、レンジエンコーダ/デコーダ、XZ コンテナ形式による圧縮および解凍パイプラインです。テスト文字列を圧縮し、解凍して原本と全バイト照合を行います。

```sh
# ビルド
make 04_xz

# 実行
./build/04/xz_sample
# 出力: XZ Clone (Compress -> Decompress Roundtrip): 100% SUCCESS!
```

#### 05. io_uring Web Server (`samples/05_web_server/`)
Linux `io_uring` システムコールを直接呼び出す非同期 Web サーバーです。

```sh
# ビルド
make 05_web_server

# サーバー起動 (ポート 18080 で待受)
./build/05/web_server
```

別ターミナルから `curl` でリクエストを送信して動作を確認できます：

```sh
# 1. ルートエンドポイント
curl http://127.0.0.1:18080/
# レスポンス: Hello from StateSSA!

# 2. パラメータ計算エンドポイント
curl "http://127.0.0.1:18080/baseline11?a=42&b=58"
# レスポンス: 100

# 3. エコーバックエンドポイント
curl -X POST -d "StateSSA Pure Web Server" http://127.0.0.1:18080/echo
# レスポンス: StateSSA Pure Web Server
```

#### 06. Fixed-Point Math (`samples/06_fixed_math/`)
固定小数点数 `q64` (Q32.32) による実数計算と、外部 C 数学ライブラリ（`libm` の `sin`, `cos`, `sqrt`）との自動型変換境界のサンプルです。

```sh
# ビルド
make 06_fixed_math

# 実行
./build/06/fixed_math
```

---

## 4. コンパイラ `bin/ssac` の直接利用方法

Stage-3 コンパイラバイナリ `bin/ssac` を直接使って StateSSA ソースコードをコンパイルできます：

```sh
# 1. 単一ファイルまたは include を含むソースコードから LLVM IR (.ll) を生成
./bin/ssac my_program.ssa -o my_program.ll

# 複数ファイルをコマンドライン引数で直接指定して結合・コンパイルすることも可能です
./bin/ssac src/types.ssa src/parser.ssa src/main.ssa -o compiler.ll

# 2. Clang でネイティブバイナリへコンパイル
clang -O2 my_program.ll -o my_program

# 3. 実行
./my_program
```

ビルドアーティファクトを削除したい場合は `make clean` を実行してください：
```sh
make clean
```

---

## 5. ライセンス (License)

本プロジェクトは **BSD 3-Clause License** の下で公開されています。
詳細は [LICENSE](LICENSE) ファイルを参照してください。

---

## 6. 謝辞 (Acknowledgments)

本プロジェクト（StateSSA）の言語仕様策定、セルフホストコンパイラの実装、固定点到達に向けたブートストラップ検証、および各種サンプルの開発において、AI（Google Gemini）によるペアプログラミングと技術支援を活用しました。人間と AI の協調開発によって実現した成果として、ここに記します。
