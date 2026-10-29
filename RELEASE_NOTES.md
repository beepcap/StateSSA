# StateSSA Release Notes

## Version 0.12.0 (2026-10-29)

StateSSA v0.12.0 は、言語仕様の厳密化（Zero-Magic Coercion & 静的型バリデータ）、セルフホストコンパイラの固定点到達、および StateSSA によるネイティブ自立実行環境を整備したリリースです。

### 主な変更点

1. **Zero-Magic Coercion ＆ 静的型バリデータ**
   * 暗黙の型変換（ビット拡張・切り詰め）を廃止し、明示的キャスト（`cast(T)`）を必須化。
   * 関数呼び出し引数、メモリストア（`<-`）、レジスタラッチ代入（`<=`）、戻り値（`return`）の 4 つの境界において静的型検査エンジンを実装。

2. **セルフホスト ＆ Stage-3 固定点到達 (Fixed-Point Reached)**
   * Python 製 Stage-0 ブートストラップコンパイラから Stage-1、Stage-2、Stage-3 へのブートストラップパイプラインを整備。
   * Stage-2 コンパイラが出力した LLVM IR と Stage-3 コンパイラが出力した LLVM IR が完全一致（Fixed Point）することを確認。
   * CLI 引数解析とファイル I/O を担う `driver.ssa` を実装し、単一バイナリ `bin/ssac` として生成可能に。

3. **POSIX 準拠 `./configure` スクリプトの導入**
   * ツールチェイン（`clang`, `python3`, `cmp`）の存在確認。
   * `bin/ssac` が存在しない場合は Stage-0 から Stage-3 までの自動ブートストラップおよび固定点照合を実行。
   * 全サンプルのビルド＆テストを実行可能なルート `Makefile` を自動生成。

4. **Pure StateSSA によるサンプルの同梱**
   * C 言語ファイルを用いず、StateSSA（`.ssa`）のみで自立実行可能なサンプル（01〜05）を整備：
     * `01_hello_world`: 最小構成のエントリーポイント
     * `02_simple_loop`: ループ FSM とレジスタラッチ
     * `03_parallel_sum`: POSIX `pthread` を呼び出す並行処理
     * `04_xz`: XZ コンテナおよび LZMA2 圧縮・解凍ラウンドトリップ
     * `05_web_server`: Linux `io_uring` による非同期 HTTP/1.1 Web サーバー
