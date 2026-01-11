# クイックスタートガイド

## 1. 環境設定

### APIキーの取得
1. **J-QUANTS API**: [J-QUANTS Dashboard](https://jpx-jquants.com/) にアクセス
   - アカウントを作成（無料プランで利用可能）
   - DashboardからAPIキーを取得
2. **EDINET API**（オプション、定性情報分析を使用する場合）: [EDINET API](https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1) にアクセス
   - APIキーを取得

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
JQUANTS_API_KEY=your_jquants_api_key_here
JQUANTS_API_BASE_URL=https://api.jquants.com/v2
EDINET_API_KEY=your_edinet_api_key_here
LLM_MODEL=gemma3:1b  # デフォルト（環境変数で他のモデルに変更可能）
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

## 2.5. Ollamaのセットアップ（定性情報分析を使用する場合）

定性情報分析機能を使用する場合は、Ollamaをインストールして起動する必要があります。

```bash
# macOSの場合
brew install ollama

# Ollamaを起動（バックグラウンドで実行）
ollama serve

# デフォルトモデル（gemma3:1b）をダウンロード
ollama pull gemma3:1b

# または他のモデルを使用する場合（.envでLLM_MODELを設定）
# ollama pull qwen3:8b  # より高性能なモデル
```

Ollamaが起動しているか確認：
```bash
ollama list
```

## 3. 動作確認

### API接続テスト

```bash
python3 scripts/test_connection.py
```

### EDINET統合機能テスト（オプション）

定性情報分析機能をテストする場合：

```bash
python3 scripts/test_edinet.py
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

### 個別分析

```bash
# Streamlitアプリを起動
streamlit run app.py
```

ブラウザでアプリが開いたら、検索バーに銘柄コード（例: 6501）を入力して「分析」ボタンをクリックしてください。

詳細な使用方法は[README.md](README.md#個別詳細分析)を参照してください。

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
- 気になる銘柄を個別分析する
- Streamlit UIで分析結果を確認する（総合評価機能を確認）

