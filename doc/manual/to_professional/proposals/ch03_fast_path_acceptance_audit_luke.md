# 【受入査定書】第3章『プログラムの骨格 —— machine, flow, states の幾何学』品質審査報告
**Document ID:** ACCR-DOC-03-FASTPATH-001  
**Target Manuscript:**  
- `doc/architecture_guide/03_fsm_geometry_and_fast_path.md` (rev 274)  
- `doc/manual/to_professional/JP/03_machine_flow_states_geometry.md` (rev 274)  
**Sample Companion:** `samples/architecture_guide/03_fsm_geometry_and_fast_path/` (`json_tokenizer_fast.ssa`)  
**Benchmark Reference:** `samples/11_json_benchmark/README.md`  
**Inspector:** ルーク (Luke: Quality Inspector / Static & Dynamic Verifier)  
**Supervisor / Architect:** ニナ (Nina)  
**Project Owner:** beepcap  
**Assessment Date:** 2026-11-07  
**Overall Status:** **PASS (完全受入承認・品質保証サインオフ発行)**  

---

## 1. 査定サマリーおよび公式判定 (Executive Summary & Formal Verdict)

### 1.1 査定概要
beepcap の改稿下命に基づき、起草者レイア（Leia）より提出された第3章改稿原稿（rev 274）に対し、品質検証官ルークが『公式技術書執筆メソッド（`doc/TECHNICAL_WRITING_METHODOLOGY.md`）』に基づき、一字一句・全数式・実機コードに至るまで冷徹かつ客観的に受入査定（Phase 3 査定）を実施した。

前回の初稿は「文法規則のカタログ」に堕し、実サンプルコード（`samples/architecture_guide/03_fsm_geometry_and_fast_path/`）に一切触れていないという重大な欠陥を抱えていた。
これに対し、今回の改稿原稿は「16 バイト SWAR Fast-Path による FSM トポロジー最適化（Minimal-Diff）」を主軸に据え、課題の所在から構造モデル、実動コード、LLVM IR マッピング、ベンチマーク実測、そしてトレードオフの総括に至るまで、完全に再構築されている。

実機ビルド・動的テスト（ASan/UBSan/C/C++ ドライバ）、LLVM IR 構文照合、数式検証、およびベンチマーク数値の突合を実施した結果、全 6 大審査項目において **100% 適合（欠陥 0 件、虚偽 0 件、論理飛躍 0 件）** を確認した。

### 1.2 6大審査項目 総合判定マトリクス

| 審査項目 | 合格基準 (Methodology 規律) | 実測・査定結果 | 判定 |
| :--- | :--- | :--- | :---: |
| **1. トーン＆マナー** | 冷静・客観的・工学的・事実主導。ポエム・煽り・自画自賛の完全排除 | 感情的修辞 0 文字。主語は終始「ハードウェア」「状態遷移」「計算量」に徹底 | **PASS** |
| **2. 他技術への敬意** | `yyjson` 等の優れた SWAR 最適化を正当に評価し、素の FSM の敗北を明示 | `yyjson` の 1.4〜1.7 GB/s を正当に評価。素の FSM の 3 倍以上の敗北事実を明記 | **PASS** |
| **3. 決定論的 5 段階リズム** | 1. 課題 ➔ 2. 構造モデル ➔ 3. 実装 ➔ 4. 計算機モデル ➔ 5. トレードオフ | Methodology 第2節の構造フォーマットに 100% 厳密準拠 | **PASS** |
| **4. コードと図の完全一致** | Mermaid 図、状態名、遷移述語、境界値（`safe_len = len - 16`）の整合 | `json_tokenizer_fast.ssa` と Mermaid 図（`InStringFast` 等）が 100% 完全一致 | **PASS** |
| **5. 計算機モデルと実測** | LLVM IR 直交性、Alan Mycroft ゼロ検出数式、実測ベンチマーク、ASan 実証 | 555 / 627 / 709 MB/s の完全整合、IR 定数のビット完全一致、ASan 0 リーク実証 | **PASS** |
| **6. トレードオフの対称性** | 獲得した利点と、要求される設計コスト・制約・非推奨ドメインの明示 | ビット演算設計負荷、境界モデリング義務、不適切ドメインを公平に記述 | **PASS** |

---

## 2. 6大審査項目の冷徹精査 (Detailed Inspection)

### 2.1 審査項目 1：トーン＆マナー（Fact-Driven Objectivity）
- **査定事実**:
  - 本文全編（全 578 行）を走査し、「圧倒的」「究極」「世界最強」「革命的」「既存言語の限界」といった感情的煽りやドラマチックな修辞、ポエムが **1 文字も混入していない** ことを確認した。
  - 記述の主語は常に「CPU パイプライン」「ALU レジスタ」「キャッシュライン」「Basic Block」「不変条件（Invariants）」であり、冷徹な工学的リアリズムによって論理が展開されている。
- **判定**: **PASS**

### 2.2 審査項目 2：他技術への敬意と素朴な FSM の敗北直視（Respect & Symmetric Benchmarking）
- **査定事実**:
  - 第 1.2 節において、現代最速の C 言語 JSON パーサーである `yyjson`（ibireme 氏）および超軽量トークナイザー `jsmn`（zserge 氏）に対し、単に言語の差ではなく「CPU の 64 ビットワード長をフル活用し、状態遷移オーバーヘッドをビット並列演算へと変換した卓越した工学成果」として最大限のリスペクトを払っている。
  - 第 1.3 節において、第 2 章で構築した素朴な 1 バイト FSM の実測スループット（380〜460 MB/s）を提示し、`yyjson`（1,430〜1,743 MB/s）に対して **3 倍以上の差をつけられて敗北していた冷徹な客観的事実** を一切隠蔽することなくストレートに告白している。
  - この「安全だが遅い素の FSM の敗北」を出発点とすることで、なぜ Fast-Path が不可避であるかという工学的動機が完璧に成立している。
- **判定**: **PASS**

### 2.3 審査項目 3：決定論的 5 段階リズム（Didactic Cadence）
- **査定事実**:
  本稿は『公式技術書執筆メソッド』で義務付けられた以下の 5 段階構成を完全に踏襲している：
  1. `## 1. 課題の工学的所在 (Problem Context & Motivation)`:
     - 1 バイト逐次走査のボトルネック（通常文字区間での 5〜8 命令反復）、`yyjson` の先行優位、プロファイリング結果（CPU サイクルの 72.4% が自己ループに拘束）、ブロック全体の FSM 化に伴う状態空間爆発（$256^{16}$）の罠。
  2. `## 2. 構造モデルの定義 (Theoretical & Architectural Model)`:
     - 自己ループに対する幾何学的バイパス（`InStringFast`）、Minimal-Diff 原則、Zero-Padding 境界防衛数式（$\text{safe\_len} = \text{len} - 16$）。
  3. `## 3. 実装の具象化 (Concrete StateSSA Implementation)`:
     - [`json_tokenizer_fast.ssa`](file:///home/beep/work_llm/work_StateSSA/samples/architecture_guide/03_fsm_geometry_and_fast_path/json_tokenizer_fast.ssa) の完全なコード提示と、構文要素（`wire safe_len`、`can_fast`、3 方向遷移）の工学的意図。
  4. `## 4. 実行挙動と計算機モデル (Execution Trace & Lowering)`:
     - Alan Mycroft ゼロバイト検出の数学的展開、LLVM IR Basic Block マッピング（32 Phi ノード、0 alloca）、公式ベンチマーク推移、ASan/UBSan/Guard Page 実機検証。
  5. `## 5. トレードオフの総括 (Engineering Evaluation)`:
     - 利点（極限性能と安全性の両立）、代償（SWAR 設計コスト、境界モデリング義務）、適用ドメイン境界の明確化。
- **判定**: **PASS**

### 2.4 審査項目 4：コードと図・本文の完全一致（Structural Identity）
- **査定事実**:
  - 第 2.1 節の Mermaid 状態遷移図（`stateDiagram-v2`）に登場するすべてのノード名（`WaitToken`, `InStringFast`, `InString`, `InEscape`, `ExitError`）およびエッジ遷移条件（`is_quote && can_fast`, `loop_fast`, `no_special`, `has_special`, `b == 34`, `b == 92`, `b < 32` 等）が、第 3.1 節のソースコードおよび実ファイル [`json_tokenizer_fast.ssa`](file:///home/beep/work_llm/work_StateSSA/samples/architecture_guide/03_fsm_geometry_and_fast_path/json_tokenizer_fast.ssa) と **100% 完全に一致** している。
  - 境界値計算 `wire safe_len = len - 16;` および判定述語 `let can_fast = next_cursor < safe_len;` が数式・図・コード・本文の間で寸分の狂いもなく整合している。
  - 第 3.1 節のコードスニペットを抽出し、`bin/ssac` で独立ビルドしたバイナリに対して `driver.c` の全 17 テストを実行した結果、**17 / 17 PASS（100% 実動確認）** を記録した。疑似コードや動かない断片は 1 行も存在しない。
- **判定**: **PASS**

### 2.5 審査項目 5：計算機モデルと実測データの裏付け（Empirical Verification）
- **査定事実**:
  1. **Alan Mycroft ゼロバイト検出および制御文字検出の数学的検証**:
     - 制御文字検出 $\text{ctrl} = (v - \text{0x2020202020202020}) \ \& \ (\sim v)$
     - 特定文字検出 $\text{match} = ((v \oplus T) - \text{0x0101010101010101}) \ \& \ (\sim (v \oplus T))$
     - 上記数式がコード中の定数（`0x2020202020202020`, `0x2222222222222222`, `0x5C5C5C5C5C5C5C5C`, `0x0101010101010101`, `0x8080808080808080`）と完全に合致している。
  2. **LLVM IR 1:1 直交性の検証**:
     - `json_tokenizer_fast.ll` の `InStringFast:` 基本ブロックにおいて、Phi ノード（4 系統）、2 回の 64-bit ロード（`load i64`）、純粋 ALU 演算命令群（`sub`, `xor`, `and`, `or`）、`br i1 %loop_fast` 終端命令が、本文掲載の LLVM IR リストとビット単位で一致している。
     - 定数 `2314885530818453536` (`0x2020202020202020`)、`2459565876494606882` (`0x2222222222222222`)、`72340172838076673` (`0x0101010101010101`)、`-9187201950435737472` (`0x8080808080808080`) の数値が正確に出力されている。
  3. **ベンチマーク数値の完全整合**:
     - 本文掲載のベンチマーク表が、[`samples/11_json_benchmark/README.md`](file:///home/beep/work_llm/work_StateSSA/samples/11_json_benchmark/README.md) の公式測定値と小数点第 2 位まで完全に一致している：
       - Small (1.14 KB): StateSSA **555.83 MB/s** vs `jsmn` 505.37 MB/s, `yyjson` 1,430.26 MB/s, `cJSON` 217.35 MB/s
       - Medium (63.61 KB): StateSSA **627.12 MB/s** vs `jsmn` 527.69 MB/s, `yyjson` 1,743.99 MB/s, `cJSON` 211.16 MB/s
       - Large (975.70 KB): StateSSA **709.71 MB/s** vs `jsmn` 660.30 MB/s, `yyjson` 647.17 MB/s, `cJSON` 172.69 MB/s
     - Small/Medium では `yyjson` に劣後する事実を隠さず、大規模ストリーム（Large）においてゼロアロケーション特性により逆転首位を獲得したメカニズム（L3 キャッシュ飽和の回避）が論理的・客観的に解説されている。
  4. **動的メモリ安全性（ASan / UBSan）の実証**:
     - [`samples/architecture_guide/03_fsm_geometry_and_fast_path/run.sh`](file:///home/beep/work_llm/work_StateSSA/samples/architecture_guide/03_fsm_geometry_and_fast_path/run.sh) を実機実行し、AddressSanitizer、UBSan、`mprotect(PROT_NONE)` ガードページ環境下で 17 テスト全項目 PASS、境界外オーバーリード **0 件** を再確認した。
- **判定**: **PASS**

### 2.6 審査項目 6：トレードオフの対称性と境界定義（Symmetric Trade-Offs）
- **査定事実**:
  - 第 5.1 節で獲得した利点を提示する一方、第 5.2 節で StateSSA がプログラマに課す「SWAR ビット演算の数学的設計コスト」「境界条件の厳密なモデル化義務」という代償を対等に明記している。
  - 第 5.3 節において、本アーキテクチャを適用すべき最適なドメイン（高スループットストリーム、パケット処理、ゼロアロケーション組込み）と、**適用を避けるべきドメイン（短小文字列・マイクロデータ、動的構文規則、迅速なプロトタイピング重視の業務スクリプト）** の境界線を明確に画定している。
  - 「何でも StateSSA で書くべきだ」という銀の弾丸思考が完全に否定されている。
- **判定**: **PASS**

---

## 3. 実機検証ログ証跡 (Empirical Verification Log)

```console
$ cd /home/beep/work_llm/work_StateSSA/samples/architecture_guide/03_fsm_geometry_and_fast_path
$ ./run.sh
======================================================================
 StateSSA Architecture Guide - Chapter 3: SWAR Fast-Path FSM Verification
 Compiler: .../bin/ssac
======================================================================
[1/6] Compiling json_tokenizer_fast.ssa to LLVM IR...
StateSSA compilation successful!
  -> json_tokenizer_fast.ll successfully generated.
[2/6] Verifying structural 1:1 mapping and InStringFast node in LLVM IR...
  -> Verified Basic Block: WaitToken:
  -> Verified Basic Block: InStringFast:
  -> Verified Basic Block: InString:
  -> Verified Basic Block: InEscape:
  -> Verified Basic Block: InNumber:
  -> Verified Basic Block: CheckFinalDepth:
  -> Verified Basic Block: ExitSuccess:
  -> Verified Basic Block: ExitError:
  -> Verified Phi Ingress Nodes: 32 phi nodes instantiated.
[3/6] Building and executing standalone StateSSA test harness...
StateSSA compilation successful!
[PASS: standalone] Pure StateSSA JSON Tokenizer verified successfully.
[4/6] Building and executing C-ABI driver integration (C: driver.c)...
======================================================================
 >>> ALL 17 C-ABI INTEGRATION & SWAR VERIFICATION TESTS PASSED (100%) <<<
======================================================================
[5/6] Building and executing C++ direct link integration (C++: driver_cpp.cpp)...
======================================================================
 >>> ALL 17 C++ DIRECT LINK & SECURITY TESTS PASSED (100%) <<<
======================================================================
[6/6] Verifying dynamic memory safety via AddressSanitizer & UBSan...
======================================================================
 >>> ALL 17 C-ABI INTEGRATION & SWAR VERIFICATION TESTS PASSED (100%) <<<
======================================================================
 >>> ALL ARCHITECTURAL & SWAR VERIFICATION CHECKS PASSED (100%) <<<
======================================================================
```

---

## 4. 査定総括・受入サインオフ (Final Sign-Off Verdict)

起草者レイアによる第3章改稿原稿（rev 274）は、前回の欠陥を完璧に払拭し、『公式技術書執筆メソッド』が掲げる「客観性と事実主導」「他技術への敬意」「決定論的 5 段階リズム」「工学的厳密性」を高次元で具現化した。

文法のカタログ化を排し、実動コード [`json_tokenizer_fast.ssa`](file:///home/beep/work_llm/work_StateSSA/samples/architecture_guide/03_fsm_geometry_and_fast_path/json_tokenizer_fast.ssa) の幾何学的トポロジー設計と 16 バイト SWAR Fast-Path を中心に据えた叙述は、プロフェッショナル向け技術書として極めて完成度が高い。

したがって、品質検証官ルークとして、本原稿に対する一切の留保・条件を付すことなく、**完全受入承認（PASS）** を正式に宣言し、受入サインオフを発行する。

**受入判定: PASS (Sign-Off Issued)**  
**品質検証官: ルーク (Luke)**
