# 棚から呼び起こす小型AI構造

このアプリの前面は普通のチャットです。  
ただし中身は、万能AIを1体置くのではなく、ファイルに保存された小型AIたちを必要な時だけ起こす構造です。

```text
ユーザーの言葉
  ↓
常駐UI
  ↓
TaskRouter
  ↓
tasks/*.json から作業の種類を選ぶ
  ↓
conductor_router
  ↓
agents/*.json から今必要な専門AIを1体だけ選ぶ
  ↓
専門AIが1回だけ仕事する
  ↓
handoff_summarizer が要点だけ残す
  ↓
専門AIは閉じる
```

## 役割

- `micro_ai_shelf/default/tasks/`: 作業部屋の定義。どのAIを棚に置くかを書く。
- `micro_ai_shelf/default/agents/`: 極限まで機能を削った専門AIの定義。
- `app/router.py`: 常駐側の軽いタスク判定器。
- `app/session_manager.py`: 司令塔、専門AI、handoff の流れを管理する。
- `app/session_store.py`: 今回の流れを `runtime/sessions/*.sqlite3` に保存する。
- `app/micro_ai.py`: 保存済みAIをOllamaで1回だけ呼び、`keep_alive: 0` で閉じる。
- `app/safety_policy.py`: 危険な要求を止め、安全レビューが必要な要求を検出する。

`micro_ai_shelf/default/agents/*.json` には `description` と `tags` を書きます。  
司令塔はコードにAI名を固定せず、ファイルの中からタグ検索して候補を作り、その中から必要なAIを選びます。

## 基本思想

- 全体としては何でもできるように拡張できる。
- でも前面にいるAIは、言葉から必要なAIを呼び起こすだけ。
- 各AIは個別チャットのように振る舞うが、長い履歴は持ち続けない。
- 使っていないAIは閉じる。
- 次のAIへ渡す情報は `runtime/sessions/*.sqlite3` に保存した短い `handoff` だけにする。

## ノートPCで軽く見せる工夫

- 棚検索で候補が1つに絞れたら、司令塔LLMを呼ばず即決する。
- 専門AIの返答が短い時は、handoff要約AIを呼ばずローカル圧縮する。
- Ollama 呼び出しは `keep_alive: 0` にして、処理後にモデルを保持しない。
- 司令塔に渡す候補AIは最大数を絞り、全AI定義を毎回長く渡さない。
- 長い会話履歴を持たず、短いhandoffだけを残す。
- セッションの流れはファイルに追記し、AI内部のメモリには保持しない。
- ログは人間の読みやすさより、SQLiteで正しさと読み込み速度を優先する。
- 削除、購入、ログイン、個人情報送信、権限変更、GitHub push などは安全レビュー対象にする。

## AIを増やす方法

1. `micro_ai_shelf/default/agents/new_specialist.json` を作る。
2. そのAIができることとできないことを `system` に短く固定する。
3. `description` と `tags` に、司令塔が見つけやすい言葉を書く。
4. 必要なら `micro_ai_shelf/default/tasks/*.json` の `pipeline` に追加する。
5. 必要なら実際の操作を行う executor を別に作る。

専門AIに直接PC操作をさせず、実行器側で安全検査する方針にする。
