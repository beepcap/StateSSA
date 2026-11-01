# StateSSA 08_midi_player アーキテクチャ設計書

本ドキュメントは、StateSSA による無制限ボイス・ピラミッド型 FM 和音合成エンジンを用いた、マルチトラック Standard MIDI File (SMF Format 1) プレイヤー `08_midi_player` の全体設計とモジュール分割仕様を定義する。

---

## 1. モジュール分割と責務定義 (5-Module Architecture)

```
projects/samples/08_midi_player/
├── ARCHITECTURE.md      # 本設計仕様書
├── midi_types.ssa       # [1] 共通データ構造体・定数定義
├── midi_parser.ssa      # [2] SMF Format 1 マルチカーソル構文解析 FSM
├── spatial_stage.ssa    # [3] 2Dステージ空間音響設計・物理パラメータ変換
├── synth_pipeline.ssa   # [4] 独立パイプライン合成計算・調停・インターリーブ
├── poly_fm_engine.ssa   # [5] 07共有 SIMD 7次 Minimax FM和音合成 & ピラミッド二分木加算コア
└── midi_player.ssa      # [6] 最上位シーケンサ、マルチカーソル進行管理 & RIFF WAV 保存
```

| モジュール | 責務・役割 | 依存関係 |
| :--- | :--- | :--- |
| **`midi_types.ssa`** | 全モジュールで共通利用する構造体（ヘッダ、トラックカーソル、イベント、空間パラメータ等） | なし |
| **`midi_parser.ssa`** | SMF Format 1 バイナリ解析、MThd/MTrk チャンク解読、VLQ デルタタイム、ランニングステータス処理 | `midi_types.ssa` |
| **`spatial_stage.ssa`** | 楽器種別やトラック番号から 2D ステージ座標 $(X, Y)$ を決定し、左右の音量・周波数デチューン・高域空気減衰を算出 | `midi_types.ssa` |
| **`synth_pipeline.ssa`** | `engine_L` と `engine_R` の 2 つの独立した `poly_fm_engine` インスタンスを保持し、空間パラメータを適用、PCM インターリーブ結合またはモノラル出力を実行 | `midi_types.ssa`, `poly_fm_engine.ssa` |
| **`poly_fm_engine.ssa`** | 07 から完全コピー配置した、4ボイス単位 $K$ ブロックの純粋な SIMD 7次 Minimax FM サイン合成 ＆ インプレース・ピラミッド二分木加算コア | なし |
| **`midi_player.ssa`** | 最上位シーケンサ。全アクティブトラックの最小待ち Tick $\Delta T$ を探してタイムラインを進行させ、WAV ファイルを生成 | 全モジュール |

---

## 2. 完全データフロー図 (DFD)

```
[Standard MIDI File (.mid) in tmp/midi/]
              |
              v
+---------------------------------------------------------------+
| 1. midi_parser.ssa (MIDI構文解析 FSM)                          |
|    - ParseMThd(file_buf)                                      |
|    - ParseTrackChunk(track_idx)                               |
|    - ReadDeltaVLQ() -> delta_ticks                            |
|    - ReadEvent() -> Note-On/Off, CC, Tempo                    |
+---------------------------------------------------------------+
              |
              | (track_id, note, vel, cc_pan, program)
              v
+---------------------------------------------------------------+
| 2. spatial_stage.ssa (空間音響・ステージング設計)              |
|    - MapTrackToStage(track_id, cc_pan) -> 2D座標 (X, Y)       |
|    - CalcSpatialParams(note, vel, X, Y)                       |
|      -> dphi_L, dphi_R                                        |
|      -> gain_L, gain_R (Mono時は gain_mono)                   |
|      -> mod_index (距離による空気減衰)                        |
+---------------------------------------------------------------+
              |
              | (SpatialVoiceParams)
              v
+---------------------------------------------------------------+
| 3. synth_pipeline.ssa (デュアルパイプライン調停・インターリーバ) |
|    - engine_L と engine_R の 2 つのインスタンスを保持・管理   |
|    - 空間パラメータを L と R に分配して各エンジンに設定       |
+---------------------------------------------------------------+
        |                                       |
        | call PolyFM_RenderStep                | call PolyFM_RenderStep
        v                                       v
+-------------------------------+       +-------------------------------+
| 4a. poly_fm_engine.ssa (L)    |       | 4b. poly_fm_engine.ssa (R)    |
|   ★【07 既存モジュール】       |       |   ★【07 既存モジュール】       |
|   - 左耳用アリーナ (K blocks)  |       |   - 右耳用アリーナ (K blocks)  |
|   - SIMD 7次 Minimax FM サイン |       |   - SIMD 7次 Minimax FM サイン |
|   - ピラミッド二分木加算 (L)   |       |   - ピラミッド二分木加算 (R)   |
|   -> pcm_L_buf (モノラルPCM)   |       |   -> pcm_R_buf (モノラルPCM)   |
+-------------------------------+       +-------------------------------+
        \                                       /
         \ (pcm_L_buf)                         / (pcm_R_buf)
          v                                   v
+---------------------------------------------------------------+
| 3. synth_pipeline.ssa (PCM結合・出力段)                       |
|    - Stereo時: Interleave [L0, R0, L1, R1, ...]               |
|    - Mono時  : pcm_L のみをそのまま直列出力                   |
+---------------------------------------------------------------+
              |
              | (out_pcm: レンダリング済みサンプルブロック)
              v
+---------------------------------------------------------------+
| 5. midi_player.ssa (最上位シーケンサ & WAVエクスポータ)        |
|    - マルチカーソル時間進行 (ΔT -> サンプル数計算 -> Render)  |
|    - CLI 引数解析 (--mono / --stereo)                         |
|    - 最終 RIFF WAV ファイル（16-bit Mono/Stereo）ヘッダ & 出力|
+---------------------------------------------------------------+
              |
              v
[Output RIFF WAV File (44.1kHz 16-bit Mono or Stereo)]
```

---

## 3. 主要データ構造体定義 (Draft for `midi_types.ssa`)

```ssa
// マルチトラック・ストリーミング用カーソル
type TrackCursor = {
    ptr:            *u8,   // 現在のトラック読み出しバイトポインタ
    end_ptr:        *u8,   // トラック終端ポインタ
    wait_ticks:     u32,   // 次回イベントまでの残り tick 数
    running_status: u8,    // 直前のランニングステータスバイト
    is_active:      u8     // 1: 演奏中, 0: トラック終了 (0xFF 0x2F)
};

// 空間音響パラメータ
type SpatialVoiceParams = {
    dphi_L:    f32,   // 左耳パイプライン用周波数位相増分
    dphi_R:    f32,   // 右耳パイプライン用周波数位相増分
    cm_ratio:  f32,   // キャリア/モジュレータ比
    base_mod:  f32,   // 距離減衰適用後のモジュレーション指数
    gain_L:    f32,   // 左耳音量ゲイン
    gain_R:    f32,   // 右耳音量ゲイン
    gain_mono: f32    // モノラル時音量ゲイン
};

// 合成パイプライン構造体
type SynthPipeline = {
    engine_L:     *PolyFMEngine,
    engine_R:     *PolyFMEngine,
    is_stereo:    i1,
    total_blocks: u32,
    pcm_L_buf:    *i16,
    pcm_R_buf:    *i16
};
```

---

## 4. 開発ロードマップ（段階的実装順序）

1. **Phase 1: `midi_types.ssa`**
   - 共通型定義の記述と単体コンパイル確認。
2. **Phase 2: `midi_parser.ssa`**
   - `MThd` / `MTrk` 読み込み、VLQ デコード、イベント解読 FSM の実装とテスト。
3. **Phase 3: `spatial_stage.ssa`**
   - トラック・楽器からステージ 2D 座標マッピング、等パワー定位、空間デチューン、高域空気減衰計算の実装。
4. **Phase 4: `synth_pipeline.ssa`**
   - `poly_fm_engine.ssa` のデュアル/モノインスタンス管理、空間パラメータ設定、ステレオ・インターリーブ結合の実装。
5. **Phase 5: `midi_player.ssa` & Makefile**
   - マルチカーソル・スケジューラ、CLI 引数処理、WAV 書き出し、`projects/Makefile` への `08_midi_player` ターゲット追加。
6. **Phase 6: 検証**
   - `tmp/midi/vivaldi_winter.mid`（3トラック）および `tmp/midi/vivaldi_winter_orchestral.mid`（15トラック）の再生検証（Mono & Stereo）。
