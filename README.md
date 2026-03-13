# Moltbook Watcher

Moltbook APIを定期ポーリングし、新着投稿をAIが自動分析するWebダッシュボード。

## セットアップ

pip install flask requests
python app.py

ブラウザで http://localhost:5000 を開く。

## 設定

watcher.py の上部で変更できます。
INTERVAL=60（秒）、LIMIT=20（件数）、KEYWORDS=[]（全件取得）

## 作者

とむ @tomu_ai_dev
https://tomu-ai963.github.io/portfolio/
