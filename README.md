# Light Shelf AI / 軽量AI棚

ノートPCや低スペックPCでも動くことを狙った、ローカル常駐型の小型AIランチャーです。前面は普通のチャットですが、中身はファイルに保存した小型AIを必要な時だけ呼び起こす構造です。

アプリ本体は `app/`、極小AIパックは `micro_ai_shelf/default/` に分けています。

詳しい考え方は `docs/ARCHITECTURE.md` にまとめています。

このアプリでは、汎用AIを常駐させません。常駐するのは `micro_ai_shelf/default/tasks/` を読む軽い司令塔だけです。司令塔が依頼内容からタスクを選び、`micro_ai_shelf/default/agents/` に保存した超小型AIを必要な工程だけ呼び起こします。

- `micro_ai_shelf/default/tasks/file_organize.json`: 「ファイル整理」タスクの棚定義
- `micro_ai_shelf/default/tasks/pcb_design_session.json`: 基板設計の作業部屋。司令塔が必要な専門AIを1つずつ起こす
- `file_sort_planner`: 整理案を作るだけ
- `file_sort_reviewer`: 整理案をチェックするだけ
- `conductor_router`: 常駐側の司令塔。次に起こす専門AIを選ぶだけ
- `kicad_operator`: KiCad/基板設計だけ
- `document_summarizer`: 文書まとめだけ
- `vscode_operator`: VSCode/コード作業だけ
- `handoff_summarizer`: 専門AIを閉じる前に要点だけ司令塔へ渡す

各AI呼び出しでは Ollama に `keep_alive: 0` を渡し、処理後にモデルを保持しない方針にしています。

ノートPCで軽く見せるため、以下も入れています。

- 候補AIが1つに絞れた時は、司令塔LLMを呼ばず即決します。
- 専門AIの返答が短い時は、handoff要約AIを呼ばずローカルで短く圧縮します。
- 長い履歴を持たず、handoffだけを次のAIに渡します。
- デフォルトモデルは軽い `qwen2.5:0.5b` です。

## 使い方

1. Ollama を起動する
2. 軽いモデルを入れる

```powershell
ollama pull qwen2.5:0.5b
```

3. アプリを起動する

```powershell
python launch_light_ai.py
```

4. フォルダを選んで「ファイル整理して」と入力する
5. 表示された案を確認してから「確認して実行」を押す

起動時にはロード画面が出て、`agents/`、`tasks/`、セッション保存先を確認してから本画面を開きます。

Windowsでは `launch_light_ai.bat` からも起動できます。

## 軽量プロファイル

環境変数 `LIGHT_AI_PROFILE` で動作を切り替えできます。

```powershell
$env:LIGHT_AI_PROFILE="tiny"
python launch_light_ai.py
```

- `tiny`: もっと低スペック向け。0.5B固定、候補数少なめ。
- `laptop`: このPC向けの標準。
- `balanced`: 余裕がある時だけ少し高性能寄り。

小型AI共有パッケージ案は `docs/AGENT_PACKAGE.md` にあります。

## フォルダ構成

```text
app/                         アプリ本体
micro_ai_shelf/default/      極小AIパック
docs/                        仕組み・使い方・共有仕様
tests/                       テスト
runtime/                     セッションDBなど実行時ファイル
```

## 詳細ドキュメント

- [仕組み](docs/ARCHITECTURE.md)
- [使い方](docs/USAGE.md)
- [極小AIパック仕様](docs/AGENT_PACKAGE.md)
- [共有サイト・GitHub配布案](docs/SHARING_PLAN.md)
- [GitHub投稿手順](docs/GITHUB_PUBLISH.md)
- [今後の予定](docs/ROADMAP.md)

## オーバーレイ表示

- 起動時は最前面表示です。
- 「最前面」のチェックで前面固定を切り替えできます。
- 「全画面」または `F11` で全画面にできます。
- `Esc` で全画面を解除できます。
- 「− 小さく」で入力欄だけのミニ表示にできます。

## 安全ルール

- 起動直後は LLM を呼びません。
- ファイル整理っぽい依頼の時だけ Ollama を呼びます。
- 1つのタスク内で、保存済みの小型AIを順番に切り替えます。
- 小型AIは呼び出しごとに起動し、処理後に停止する方針です。
- 作業セッション型では、専門AIの長い会話履歴を持ち続けず、閉じる前に短い `handoff` だけ残します。
- 今回の流れは `runtime/sessions/*.sqlite3` に保存し、AI内部で履歴を持ち続けません。
- ログは人間が直接読む前提ではなく、正しさと読み込み速度を優先しています。
- ファイル本文は読みません。
- 削除はしません。
- 対象フォルダ外への移動は禁止です。
- AI案はプログラム側で検査します。
- 実行ログと取り消し履歴は対象フォルダ内の `.light_ai_logs` に保存します。

## 日本語パスでOllamaが困る場合

Windows の日本語パス問題が出る場合は、Ollama のモデル保存先を ASCII パスに寄せます。

```powershell
setx OLLAMA_MODELS C:\OllamaModels
```

その後、Ollama を再起動してください。
