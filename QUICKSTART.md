# クイックスタートガイド

## 1. 環境設定

### APIキーの取得
1. [J-QUANTS Dashboard](https://jpx-jquants.com/) にアクセス
2. アカウントを作成（無料プランで利用可能）
3. DashboardからAPIキーを取得

### 環境変数の設定

```bash
# .env.exampleをコピー
cp .env.example .env

# .envファイルを編集してAPIキーを設定
# JQUANTS_API_KEY=your_api_key_here の部分を実際のAPIキーに置き換える
```

または、エディタで直接編集：

```bash
# .envファイルを作成
cat > .env << EOF
JQUANTS_API_KEY=your_api_key_here
JQUANTS_API_BASE_URL=https://api.jquants.com/v1
EOF
```

## 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

または

```bash
pip3 install -r requirements.txt
```

## 3. 動作確認

### API接続テスト

```bash
python3 scripts/test_connection.py
```

正常に動作すれば、以下のような出力が表示されます：

```
============================================================
J-QUANTS API 接続テスト
============================================================

1. APIクライアントを初期化中...
   ✅ APIクライアントの初期化に成功しました

2. 銘柄マスタを取得中...
   ✅ 銘柄マスタの取得に成功しました（XXXX銘柄）

3. 業種一覧を取得中...
   ✅ 業種一覧の取得に成功しました（33業種）

4. テスト銘柄の財務データを取得中...
   ✅ 財務データの取得に成功しました
```

## 4. 実際に使ってみる

### パターンA：スクリーニング

```bash
python3 scripts/screening.py
```

詳細な使用方法は[README.md](README.md#パターンaスクリーニング)を参照してください。

### パターンB：個別分析

```bash
# ラッパースクリプトを使用（推奨）
python3 scripts/notebook_analysis.py 6501

# または、Jupyter Notebookを直接起動
jupyter notebook notebooks/individual_analysis_template.ipynb
```

詳細な使用方法は[README.md](README.md#パターンb個別詳細分析)を参照してください。

### ウォッチリスト管理

```bash
# 銘柄を追加
python3 scripts/watchlist_manager.py add 7203 "トヨタ自動車" --tags 製造業 高ROE

# リスト表示
python3 scripts/watchlist_manager.py list
```

詳細な使用方法は[README.md](README.md#ウォッチリスト管理)を参照してください。

## トラブルシューティング

### APIキーエラー

```
❌ エラー: APIキーが設定されていません
```

**解決方法**:
- `.env`ファイルが存在するか確認
- `.env`ファイル内の`JQUANTS_API_KEY`が正しく設定されているか確認
- ファイルパスが正しいか確認（プロジェクトルートに`.env`があること）

### モジュールが見つからないエラー

```
ModuleNotFoundError: No module named 'src'
```

**解決方法**:
- プロジェクトルートから実行しているか確認
- `pip install -r requirements.txt`を実行

### APIレート制限エラー

```
レート制限に達しました
```

**解決方法**:
- 無料プランには1日あたりのリクエスト数制限があります
- キャッシュ機能が有効になっているか確認
- しばらく時間をおいてから再実行

## 次のステップ

- [README.md](README.md)で詳細な機能説明を確認
- スクリーニング結果を詳しく見る
- 気になる銘柄を個別分析する
- 生成されたHTMLレポートを確認する（総合評価機能を確認）
- ウォッチリストに銘柄を追加して管理する

