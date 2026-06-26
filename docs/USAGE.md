# 使い方

## 起動

```powershell
python launch_light_ai.py
```

または Windows では `launch_light_ai.bat` をダブルクリックします。

デスクトップショートカットは `scripts/start-light-ai.ps1` を呼びます。起動に失敗した場合は `runtime/logs/launcher.log` を確認してください。

起動時にロード画面が出て、`micro_ai_shelf/default/agents`、`micro_ai_shelf/default/tasks`、セッション保存先を確認します。

## オーバーレイ操作

- 起動時は最前面表示
- 「最前面」で前面固定ON/OFF
- 「全画面」または `F11` で全画面
- `Esc` で全画面解除
- 「− 小さく」でミニ表示

## ファイル整理

1. 「フォルダ選択」を押す
2. 整理したいフォルダを選ぶ
3. 「ファイル整理して」と入力する
4. 整理案を確認する
5. 「確認して実行」を押す

ファイル本文と隠しファイルは読みません。AI案は executor が対象フォルダ内の安全な相対パスだけに検査してから表示します。

## 基板設計セッション

「基板設計したい」「KiCadで設計したい」などと入力すると、基板設計セッションを開始します。

セッション中は、入力に応じて `kicad_operator`、`document_summarizer`、`vscode_operator` などの専門AIを必要な時だけ起動します。

## 安全ログ

安全判定は `runtime/security/safety_audit.sqlite3` に保存します。
全文ではなく、判定結果、リスク分類、SHA-256、短い伏字プレビューだけを残します。

詳しくは `docs/SECURITY.md` を見てください。
