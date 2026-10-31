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
│   ├── parser.ssa      # 構文解析 FSM (extern マージ・include パス解決)
│   ├── codegen.ssa     # LLVM IR コード生成 FSM (SIMD・型チェック・q64/C-ABI自動変換)
│   ├── llvm_backend.ssa# LLVM C-API オブジェクトファイル生成モジュール
│   └── driver.ssa      # CLI 引数解析・ファイルローダー・アリーナメモリ管理
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
    ├── 06_fixed_math/  # q64 固定小数点数による実数計算と C-ABI 境界自動変換
    └── 07_simd_vivaldi_winter/ # f32x4 SIMD 4ボイス FM 弦楽合奏音響合成 (ヴィヴァルディ「冬」)
```

---

## 2. ビルドと環境構築 (Setup & Build)

### 前提要件
* `clang` (LLVM C/IR コンパイラ)
* `llvm-config` (LLVM 開発パッケージ / C-API 連携)
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

StateSSA に同梱されているサンプルプログラムは、すべて C 言語ラッパーや中間ファイルを用いず、**100% 純粋な StateSSA（`.ssa`）** のみで実装されています。

### ① 全サンプルの一括ビルド＆自動検証 (`make test`)

リポジトリルートで以下のコマンドを実行すると、全 7 サンプルのコンパイルと自己検証テストが一括で実行されます：

```sh
make test
```

実行結果の例：
```text
============================================================
Running All StateSSA Sample Verifications
============================================================
--- [Test 1/7] 01_hello_world ---
Hello, StateSSA World!

--- [Test 2/7] 02_simple_loop ---
simple_loop(10) = 45: SUCCESS!

--- [Test 3/7] 03_parallel_sum ---
ParallelSum([1..8]) = 36: SUCCESS!

--- [Test 4/7] 04_xz ---
XZ Clone (Compress -> Decompress Roundtrip): 100% SUCCESS!

--- [Test 5/7] 05_web_server (Self-Test) ---
StateSSA io_uring Web Server listening on 0.0.0.0:18080...
GET / -> 200 OK & Hello verified!
GET /baseline11 -> 200 OK & Sum 100 verified!
POST /echo -> 200 OK & Echo verified!
web_server verification passed.

--- [Test 6/7] 06_fixed_math ---
=== StateSSA Sample 06: Deterministic Math (q64) ===
a + b (expected 3.500000): 3.500000
b - a (expected 0.500000): 0.500000
a * b (expected 3.000000): 3.000000
a / b (expected 0.750000): 0.750000
altitude at t=1.0s (expected 15.100000): 15.100000
sin(0.0) (expected 0.000000): 0.000000
cos(0.0) (expected 1.000000): 1.000000
sqrt(4.0) (expected 2.000000): 2.000000

--- [Test 7/7] 07_simd_vivaldi_winter ---
StateSSA SIMD 4-Voice FM Synthesizer: Vivaldi Winter RV297
Rendering 704 measures/steps (~71.4s) using f32x4 SIMD...
Vivaldi Winter rendered successfully to WAV file.
WAV audio output generated successfully!

============================================================
>>> ALL SAMPLES PASSED 100% ON STAGE-3 BINARY COMPILER! <<<
============================================================
```

### ② サンプル一覧と詳細解説リンク

| # | サンプル名 | ディレクトリ | 主な特徴・検証内容 |
| :---: | :--- | :--- | :--- |
| **01** | **Hello World** | `samples/01_hello_world/` | 最小構成のエントリーポイント、文字列リテラル、C-ABI `puts` 呼び出し |
| **02** | **Simple Loop** | `samples/02_simple_loop/` | レジスタラッチ更新（`res <= ...`）、1-bit ガードによる状態遷移ループ |
| **03** | **Parallel Sum** | `samples/03_parallel_sum/` | POSIX `pthread` システムコール連携、2スレッド並行タスクと同期合算 |
| **04** | **XZ Clone** | `samples/04_xz/` | LZMA2、CRC32、マッチファインダ、XZ コンテナの圧縮・解凍往復検証 |
| **05** | **io_uring Web Server** | `samples/05_web_server/` | Linux `io_uring` 非同期システムコール直結、Zero-copy HTTP Web サーバー |
| **06** | **Fixed-Point Math** | `samples/06_fixed_math/` | `q64` (Q32.32) 固定小数点実数計算、C 数学ライブラリ（`libm`）境界自動変換 |
| **07** | **SIMD Vivaldi Winter** | `samples/07_simd_vivaldi_winter/` | `f32x4` SIMD 演算、4ボイス FM 弦楽合奏音響合成、44.1kHz 16bit WAV 出力 |

> [!TIP]
> 各サンプルの詳細な解説、ソースコードの設計思想、および個別手動ビルド・実行手順については、**[SAMPLES.md](SAMPLES.md)** を参照してください。

---

## 4. コンパイラ `bin/ssac` の直接利用方法

Stage-3 コンパイラバイナリ `bin/ssac` を直接使って StateSSA ソースコードをコンパイルできます。
v0.14.0 より、従来の LLVM IR テキスト出力（`-o <file>.ll`）に加えて、コンパイラ単体で直接最適化済みオブジェクトファイルを出力する `-o <file>.o` オプションが追加されました。

### ① オブジェクトファイル直接出力（推奨）
コンパイラがホストマシンの CPU 機能を自動認識して最適なネイティブオブジェクトを直接生成します：

```sh
# 1. オブジェクトファイル (.o) を生成
./bin/ssac my_program.ssa -o my_program.o

# 2. システムの C コンパイラ / リンカで実行可能バイナリへリンク
clang my_program.o -o my_program

# 3. 実行
./my_program
```

### ② LLVM IR テキスト経由でのビルド
中間表現である LLVM IR（`.ll`）を出力し、Clang 等でビルドすることも可能です：

```sh
# 1. LLVM IR テキスト (.ll) を生成
./bin/ssac my_program.ssa -o my_program.ll

# 2. Clang でネイティブバイナリへビルド
clang -O2 my_program.ll -o my_program

# 3. 実行
./my_program
```

> [!IMPORTANT]
> **SIMD ベクトル型（AVX / AVX2 等）を使用する場合の注意点**:
> - SIMD ベクトル型は、整列されたメモリ領域へのポインタ（`*f32x4` 等）を介して一括ロード（`*ptr`）、並列演算、一括ストア（`*ptr <- val`）を行います。
> - `.o` 直接出力時は、コンパイラがホストマシンの CPU 拡張命令（AVX2 等）を自動認識してコードを生成するため、追加の命令セットフラグは不要です。
> - 一方、**LLVM IR（`.ll`）を経由して `clang` でビルドする場合**、Clang はデフォルトで保守的なベースライン CPU を想定するため、SIMD 命令をハードウェアのネイティブベクトル命令へ正しく変換・リンクするために、**`-mavx2`** や **`-march=native`**（および必要に応じて数学ライブラリ **`-lm`**）を `clang` に明示的に指定する必要があります：
>   ```sh
>   clang -O2 -march=native my_simd_prog.ll -lm -o my_simd_prog
>   ```

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
