# StateSSA サンプル集 (SAMPLES.md)

StateSSA に同梱されているサンプルプログラムは、すべて C 言語ラッパーや中間ファイルを用いず、**100% 純粋な StateSSA（`.ssa`）** のみで実装されています。

高水準言語の AST やランタイムに依存せず、FSM（有限状態遷移）と SSA データフロー（ワイヤー）のみで、Hello World からシステムプログラミング、並行処理、圧縮解凍、非同期 I/O、SIMD 音響合成までを記述できる表現力を実証しています。

---

## 目次

1. [全サンプルの一括ビルドと自動検証 (`make test`)](#1-全サンプルの一括ビルドと自動検証-make-test)
2. [サンプル一覧](#2-サンプル一覧)
3. [個別サンプルの詳細と実行手順](#3-個別サンプルの詳細と実行手順)
   - [01. Hello World (`samples/01_hello_world/`)](#01-hello-world-samples01_hello_world)
   - [02. Simple Loop (`samples/02_simple_loop/`)](#02-simple-loop-samples02_simple_loop)
   - [03. Parallel Sum (`samples/03_parallel_sum/`)](#03-parallel-sum-samples03_parallel_sum)
   - [04. XZ Clone (`samples/04_xz/`)](#04-xz-clone-samples04_xz)
   - [05. io_uring Web Server (`samples/05_web_server/`)](#05-io_uring-web-server-samples05_web_server)
   - [06. Fixed-Point Math (`samples/06_fixed_math/`)](#06-fixed-point-math-samples06_fixed_math)
   - [07. SIMD Vivaldi Winter (`samples/07_simd_vivaldi_winter/`)](#07-simd-vivaldi-winter-samples07_simd_vivaldi_winter)
   - [08. FM MIDI Player (`samples/08_midi_player/`)](#08-fm-midi-player-samples08_midi_player)

---

## 1. 全サンプルの一括ビルドと自動検証 (`make test`)

リポジトリルートで以下のコマンドを実行すると、全 8 サンプルのコンパイルと自己検証テストが一括で実行されます：

```sh
make test
```

実行結果の例：
```text
============================================================
Running All StateSSA Sample Verifications
============================================================
--- [Test 1/8] 01_hello_world ---
Hello, StateSSA World!

--- [Test 2/8] 02_simple_loop ---
simple_loop(10) = 45: SUCCESS!

--- [Test 3/8] 03_parallel_sum ---
ParallelSum([1..8]) = 36: SUCCESS!

--- [Test 4/8] 04_xz ---
XZ Clone (Compress -> Decompress Roundtrip): 100% SUCCESS!

--- [Test 5/8] 05_web_server (Self-Test) ---
StateSSA io_uring Web Server listening on 0.0.0.0:18080...
GET / -> 200 OK & Hello verified!
GET /baseline11 -> 200 OK & Sum 100 verified!
POST /echo -> 200 OK & Echo verified!
web_server verification passed.

--- [Test 6/8] 06_fixed_math ---
=== StateSSA Sample 06: Deterministic Math (q64) ===
a + b (expected 3.500000): 3.500000
b - a (expected 0.500000): 0.500000
a * b (expected 3.000000): 3.000000
a / b (expected 0.750000): 0.750000
altitude at t=1.0s (expected 15.100000): 15.100000
sin(0.0) (expected 0.000000): 0.000000
cos(0.0) (expected 1.000000): 1.000000
sqrt(4.0) (expected 2.000000): 2.000000

--- [Test 7/8] 07_simd_vivaldi_winter ---
StateSSA SIMD 4-Voice FM Synthesizer: Vivaldi Winter RV297
Rendering 704 measures/steps (~71.4s) using f32x4 SIMD...
Vivaldi Winter rendered successfully to WAV file.
WAV audio output generated successfully!

--- [Test 8/8] 08_midi_player ---
StateSSA Multi-Track MIDI Synthesizer Player
Starting multi-track timeline synthesis...
MIDI stereo synthesis complete! WAV rendered successfully.
08_midi_player Stereo WAV generated successfully!
[Mode] Mono Output Selected
StateSSA Multi-Track MIDI Synthesizer Player
Starting multi-track timeline synthesis...
MIDI mono synthesis complete! WAV rendered successfully.
08_midi_player Mono WAV generated successfully!

============================================================
>>> ALL SAMPLES PASSED 100% ON STAGE-3 BINARY COMPILER! <<<
============================================================
```

---

## 2. サンプル一覧

| # | サンプル名 | ディレクトリ | 主な特徴・検証内容 |
| :---: | :--- | :--- | :--- |
| **01** | **Hello World** | `samples/01_hello_world/` | 最小構成のエントリーポイント、文字列リテラル、C-ABI `puts` 呼び出し |
| **02** | **Simple Loop** | `samples/02_simple_loop/` | レジスタラッチ更新（`res <= ...`）、1-bit ガードによる状態遷移ループ |
| **03** | **Parallel Sum** | `samples/03_parallel_sum/` | POSIX `pthread` システムコール連携、2スレッド並行タスクと同期合算 |
| **04** | **XZ Clone** | `samples/04_xz/` | LZMA2、CRC32、マッチファインダ、XZ コンテナの圧縮・解凍往復検証 |
| **05** | **io_uring Web Server** | `samples/05_web_server/` | Linux `io_uring` 非同期システムコール直結、Zero-copy HTTP Web サーバー |
| **06** | **Fixed-Point Math** | `samples/06_fixed_math/` | `q64` (Q32.32) 固定小数点実数計算、C 数学ライブラリ（`libm`）境界自動変換 |
| **07** | **SIMD Vivaldi Winter** | `samples/07_simd_vivaldi_winter/` | `f32x4` SIMD 演算、4ボイス FM 弦楽合奏音響合成、44.1kHz 16bit WAV 出力 |
| **08** | **FM MIDI Player** | `samples/08_midi_player/` | SMF Format 0/1 並行パース、事前スキャン動的ポリフォニー、純粋FM合成、リアルタイムUNIXパイプ再生 |

---

## 3. 個別サンプルの詳細と実行手順

### 01. Hello World (`samples/01_hello_world/`)
最小限のエントリーポイントと文字列出力のサンプルです。
`main` マシンから標準 C ライブラリの `puts` を呼び出し、ターミナルに文字列を出力します。

```sh
# ビルド
make 01_hello_world

# 実行
./build/01/hello
# 出力: Hello, StateSSA World!
```

---

### 02. Simple Loop (`samples/02_simple_loop/`)
レジスタラッチ代入（`res <= ...`）と 1-bit predicate ガードによる純粋な有限状態ループです。
高水準言語の `while` や `for` を用いず、離散的な状態遷移（`Entry -> Loop -> Exit`）で 1 から 10 までの総和（45）を計算します。

```sh
# ビルド
make 02_simple_loop

# 実行
./build/02/simple_loop
# 出力: simple_loop(10) = 45: SUCCESS!
```

---

### 03. Parallel Sum (`samples/03_parallel_sum/`)
StateSSA から直接 POSIX `pthread`（`pthread_create`, `pthread_join`）を呼び出し、2つのスレッドで並列に配列要素を合算して同期・回収します。
C 中間層を一切介さず、StateSSA のマシンポインタ（`&thread_trampoline`, `&worker_task`）を関数ポインタとして渡す並行処理パターンを実証しています。

```sh
# ビルド
make 03_parallel_sum

# 実行
./build/03/parallel_sum
# 出力: ParallelSum([1..8]) = 36: SUCCESS!
```

---

### 04. XZ Clone (`samples/04_xz/`)
LZMA2、CRC32、マッチファインダ、レンジエンコーダ/デコーダ、XZ コンテナ形式による完全な圧縮および解凍パイプラインです。
テスト文字列をメモリ上で圧縮し、続いて解凍して原本データと 1 バイトの狂いもなく完全一致することを検証します。

```sh
# ビルド
make 04_xz

# 実行
./build/04/xz_sample
# 出力: XZ Clone (Compress -> Decompress Roundtrip): 100% SUCCESS!
```

---

### 05. io_uring Web Server (`samples/05_web_server/`)
Linux カーネルの最新非同期 I/O インターフェース `io_uring` システムコールを直接呼び出す高性能非同期 HTTP Web サーバーです。
エポックタイムアウト、URL ルーティング、クエリパラメータ計算、POST エコーバックをノンブロッキングに処理します。

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

---

### 06. Fixed-Point Math (`samples/06_fixed_math/`)
固定小数点数 `q64` (Q32.32) による決定論的実数計算と、外部 C 数学ライブラリ（`libm` の `sin`, `cos`, `sqrt`）との自動型変換境界のサンプルです。
浮動小数点数の環境依存ブレを排除したい物理シミュレーションや金融計算に適した設計を示します。

```sh
# ビルド
make 06_fixed_math

# 実行
./build/06/fixed_math
```

---

### 07. SIMD Vivaldi Winter (`samples/07_simd_vivaldi_winter/`)
`f32x4` SIMD ベクトル演算を駆使したヴィヴァルディ「四季」より『冬』第1楽章（RV 297）の 4ボイス FM 弦楽合奏音響合成エンジンです。
52 本のレジスタを持つ大規模マシン定義により、各ボイスの周波数・変調指数・ADSR エンベロープ・波形生成を 128bit ベクトルレジスタ上で 1 サイクル並列計算します。

コンパイラのオブジェクトファイル出力オプション（`-o output.o`）を用いてビルドされます。

```sh
# ビルド (オブジェクトファイル出力経由)
make 07_simd_vivaldi_winter

# 実行 (71.4 秒の WAV 音声ファイルを生成)
./build/07/simd_vivaldi_winter vivaldi_winter.wav
```
生成された `vivaldi_winter.wav` は、標準的なメディアプレイヤー（`aplay`, `vlc`, `ffplay` 等）で再生可能です。

---

### 08. FM MIDI Player (`samples/08_midi_player/`)
スタンダード MIDI ファイル（SMF Format 0 および Format 1）を直接パースし、80年代〜90年代の黄金期を彷彿とさせる純粋な FM 音響合成によってリアルタイム再生・WAV 書き出しを行うフルスペック・シンセサイザープレイヤーです。
外部の波形テーブルや SoundFont、C 言語中間ライブラリを一切使わず、**100% 純粋な StateSSA（`.ssa`）** のみで実装されています。

#### 主なアーキテクチャと特徴
1. **ストリーミング型 Multi-Track FSM パーサー (`midi_parser.ssa`)**:
   - 7-bit 可変長数値（VLQ）、デルタタイム、ランニングステータス、テンポ変更（Set-Tempo）、トラック末尾イベントを有限状態機械で逐次デコード。
2. **高速事前スキャンと決定論的無制限ポリフォニー**:
   - ファイルロード直後にオーディオ合成なしの高速ドライラン（事前解析）を実行し、曲全体の最大同時発音数 $N_{peak}$ を数ミリ秒で確定。
   - 演奏ループ中の動的再確保（`realloc`）を完全排除し、必要な SIMD アリーナ（$K = \lceil N_{peak}/4 \rceil$ ブロック）を 1 回だけジャストサイズ確保。小編成（8ボイス）から大編成オーケストラ（44ボイス以上）までボイス落ち 0 で決定論的に再生。
3. **3D 空間音響ステージ (`spatial_stage.ssa`)**:
   - トラック・チャンネルごとの幾何学的空間配置に基づき、左右の到達時間差・距離減衰・空気による高域吸収（変調指数の距離減衰）をリアルタイム計算。
4. **デュアル FM 合成パイプライン (`synth_pipeline.ssa`, `poly_fm_engine.ssa`)**:
   - 左右独立のステレオパイプライン。7次 Minimax 多項式による正確な正弦波発振と、In-Place ツリー縮約（ピラミッドトーナメント加算）による低ジッターなベクトルミキシング。
5. **8KB 逐次ストリーミングと UNIX パイプライン即時再生**:
   - 16MB などの巨大バッファを廃止し、8KB（2048 サンプル）の安全な作業チャンクで逐次出力。
   - 長大な大曲（10分〜1時間以上）でもメモリ数十 KB のまま完走可能。
   - 標準出力モード（`"-"`）により、UNIX パイプを通じてサウンドデバイスへ即時ストリーミング再生。

#### ビルドと実行

```sh
# 1. ビルド
make 08_midi_player

# 2. リアルタイム・ストリーミング再生 (UNIX パイプライン、デフォルト stdout)
./build/08/midi_player your_song.mid | aplay -f cd

# 3. 複数曲の連続ジュークボックス再生 (ワイルドカード対応)
./build/08/midi_player *.mid | aplay -f cd

# 4. ステレオ WAV ファイルへの高速レンダリング (-o オプション)
./build/08/midi_player your_song.mid -o output_stereo.wav

# 5. モノラル WAV ファイルへのレンダリング (--mono)
./build/08/midi_player your_song.mid -o output_mono.wav --mono
```

> [!NOTE]
> 生成されるバイナリは strip 適用時で **わずか 23KB**。外部ライブラリ（`libc`, `libm` 以外）への依存は一切ありません。
