# GitHub投稿手順

このリポジトリはGitHub投稿できる状態に整えています。

## 方法A: GitHub CLIを使う

GitHub CLIをインストールしてログインします。

```powershell
winget install GitHub.cli
gh auth login
```

その後、このフォルダで以下を実行します。

```powershell
git branch -M main
gh repo create light-shelf-ai --public --source . --remote origin --push
```

## 方法B: GitHubで空リポジトリを作ってpush

GitHub上で `light-shelf-ai` という空リポジトリを作ります。

その後、このフォルダで以下を実行します。

```powershell
git branch -M main
git remote add origin https://github.com/YOUR_NAME/light-shelf-ai.git
git push -u origin main
```

## 投稿内容

- `app/`: アプリ本体
- `micro_ai_shelf/default/`: 極小AIパック
- `docs/`: 仕組み、使い方、共有仕様
- `tests/`: 検証

## 公開前チェック

```powershell
python -B -m unittest discover -s tests -v
```
