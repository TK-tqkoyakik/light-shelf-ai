# 小型AI共有パッケージ案

`micro_ai_shelf/*/agents/*.json` を共有できるようにするための最小仕様です。GitHub、将来の専用サイト、Steam配布版の追加パックで同じ形式を使います。

## 1 AI = 1 JSON

```json
{
  "name": "kicad_operator",
  "role": "specialist_chat",
  "description": "KiCadと基板設計だけを担当する専門AI",
  "tags": ["kicad", "基板", "pcb"],
  "model": "qwen2.5:0.5b",
  "system": "できることとできないことを短く固定する",
  "output": "短い専門チャット返答",
  "safety": {
    "can_execute": false,
    "needs_confirmation": true
  }
}
```

## 共有サイトに必要な項目

- 名前
- 説明
- タグ
- 対応モデル
- 必要な実行器
- 危険操作の有無
- 作者
- バージョン
- ライセンス
- テスト済みPC目安

## 評価指標

人気順だけにしない。小型AIは「軽い・正しい・範囲が狭い」ことが大事。

- 平均応答時間
- LLM呼び出し回数
- 失敗率
- handoffの短さ
- 対応RAM目安
- 危険操作なし

## 配布方針

最初はGitHubで十分です。  
専用サイトは、検索・評価・安全チェックが必要になってから作ります。  
Steamは一般ユーザー向けアプリとして見せやすいですが、AIパック共有の中心にはしにくいので後回しが安全です。
