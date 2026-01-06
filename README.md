# Educe - 投資判断分析ツール

Educeは、J-QUANTS API・EDINET API・ローカルLLMを使用した投資判断分析ツールです。FCFを最重視し、堅実な投資判断をサポートします。

## 機能概要

### 個別詳細分析（メイン機能）
- 特定銘柄の詳細分析（複数銘柄対応）
- 最大10年分の財務データと各種指標を表示（利用可能なデータを最大限使用）
- **レポート形式**：数値表
- **HTMLレポート生成**：プレゼンテーション品質のビジュアルレポート
  - 年度別財務データ表（年度列追加）
  - **最新の事業概要・経営方針・課題**
    - 最新年度の有価証券報告書から抽出した事業戦略・事業環境・リスク要因のLLM要約
    - マークダウン記法対応（見出し、箇条書き、強調表示）
    - 有価証券報告書PDFへのリンク
  - インタラクティブな財務グラフ（6種類）
    - **【事業の実力】**
      - 事業効率（簡易ROIC × CF変換率、総合評価付き）
      - キャッシュフロー（FCF＝営業CF＋投資CF）
    - **【株主価値と市場評価】**
      - 株主価値の蓄積（EPS × BPS × ROE、総合評価付き）
      - 配当政策と市場評価（配当性向 × ROE × PBR、総合評価付き）
      - 市場評価（PER × ROE × PBR、総合評価付き）
      - 株価とEPSの乖離
  - 総合評価（各グラフ下に表示）
    - CAGRに基づくパターン評価
    - 評価コメントの色付き表示
- **未来の年度データを自動除外**：現在日付より未来の年度データは分析対象外

### ウォッチリスト機能
- 銘柄の追加・削除
- タグ管理（1銘柄に複数タグ付与可能）
- タグによるフィルタリング
- CSV/JSON形式でのエクスポート・インポート

## セットアップ

詳細なセットアップ手順は[QUICKSTART.md](QUICKSTART.md)を参照してください。

### クイックセットアップ

1. **APIキーの取得**: 
   - J-QUANTS API: [J-QUANTS Dashboard](https://jpx-jquants.com/)からAPIキーを取得
   - EDINET API（オプション）: [EDINET API](https://disclosure2.edinet-fsa.go.jp/)からAPIキーを取得
2. **環境変数の設定**: `.env.example`を`.env`にコピーし、APIキーを設定
3. **依存パッケージのインストール**: `pip install -r requirements.txt`
4. **Ollamaのセットアップ**（定性情報分析を使用する場合）:
   ```bash
   brew install ollama  # macOSの場合
   ollama serve
   ollama pull gemma2:2b
   ```
5. **動作確認**: `python3 scripts/test_connection.py`

## 使用方法

### 動作確認（初回のみ推奨）

```bash
python3 scripts/test_connection.py
```

### 個別詳細分析

Jupyter Notebookを使用します。銘柄コードを引数として渡すことができます：

```bash
# 方法1: ラッパースクリプトを使用（推奨）
python3 scripts/notebook_analysis.py 6501
python3 scripts/notebook_analysis.py 6501 2802  # 複数銘柄

# 方法2: 直接起動（Notebook内で銘柄コードを入力）
jupyter notebook notebooks/individual_analysis_template.ipynb
```

**利用可能な表示形式：**
- **レポート形式**：数値表（年度別財務データ）
- **HTMLレポート**：プレゼンテーション品質のビジュアルレポート（詳細は上記「機能概要」を参照）
- **CSVレポート**：HTMLレポート生成時に自動出力（純粋なデータのみ）
  - ヘッダー情報（銘柄コード、会社名、セクター名、市場名、分析日）
  - 年度別財務データ（24列：基本財務指標 + グラフ用計算指標 + EDINETデータ）
    - 基本財務指標：年度、年度終了日、売上高、営業利益、当期純利益、純資産、営業CF、投資CF、FCF、ROE、EPS、BPS、PER、PBR、配当性向
    - グラフ用計算指標：簡易ROIC、CF変換率、株価、株価指数、EPS指数
    - EDINETデータ：有報書類管理番号、有報提出日、事業概要・経営方針・課題要約、有報PDF保存パス、要約生成日時

### ウォッチリスト管理

```bash
# 銘柄を追加
python3 scripts/watchlist_manager.py add 7203 "トヨタ自動車" --tags 製造業 高ROE

# ウォッチリストを表示
python3 scripts/watchlist_manager.py list

# タグでフィルタリング
python3 scripts/watchlist_manager.py list --tag 製造業

# タグを更新
python3 scripts/watchlist_manager.py tags 7203 --tags 製造業 高ROE 監視中

# CSV形式でエクスポート
python3 scripts/watchlist_manager.py export --output watchlist.csv

# CSV形式からインポート
python3 scripts/watchlist_manager.py import --input watchlist.csv
```

## プロジェクト構造

```
Educe/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── client.py          # J-QUANTS APIクライアント
│   │   └── edinet_client.py   # EDINET APIクライアント
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── individual.py      # 個別分析
│   │   ├── calculator.py      # 財務指標計算
│   │   ├── pdf_parser.py      # PDF解析モジュール
│   │   ├── xbrl_parser.py     # XBRL解析モジュール
│   │   └── llm_summarizer.py  # LLM要約モジュール
│   ├── report/
│   │   ├── __init__.py
│   │   └── html_report.py     # HTML/CSVレポート生成
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── financial_data.py  # 財務データ処理
│   │   ├── cache.py           # キャッシュ管理
│   │   ├── sectors.py         # 業種情報管理
│   │   ├── watchlist.py       # ウォッチリスト管理
│   │   └── errors.py          # カスタム例外クラス
│   └── config.py              # 設定管理
├── scripts/
│   ├── notebook_analysis.py   # 個別分析Notebook起動ラッパー
│   ├── watchlist_manager.py   # ウォッチリスト管理スクリプト
│   ├── test_connection.py     # API接続テスト
│   ├── test_api_data.py       # APIデータテスト
│   ├── test_analysis_years.py # 分析年数テスト
│   └── test_edinet.py         # EDINET統合機能テスト
├── notebooks/
│   └── individual_analysis_template.ipynb  # 個別分析テンプレート
├── templates/
│   └── report_template.html   # HTMLレポートテンプレート
├── static/
│   └── css/
│       └── report.css         # レポート用CSS
├── reports/                   # 生成されたHTMLレポートとCSVレポート保存先
│   └── {code}_edinet/         # 有価証券報告書PDF/XBRL保存先
├── cache/                     # APIレスポンスキャッシュ
│   └── edinet/                # EDINETデータキャッシュ
│       └── summaries/         # LLM要約キャッシュ
├── data/                      # データ保存先
├── watchlist.json             # ウォッチリスト（JSON形式）
├── requirements.txt
├── .env.example
└── README.md
```

## 分析指標

### 実績指標
- **FCF**: 最大10年分実数値 + CAGR（最重視）
- **ROE**: 最大10年分実数値 + CAGR
- **EPS**: 最大10年分実数値 + CAGR
- **売上高成長率**: CAGR
- **営業利益 vs 営業CF**: 各年度実数値

### 期待指標
- **PER**: 最大10年分実数値 + CAGR + 基にした株価
- **PBR**: 最大10年分実数値 + CAGR + 基にした株価

### データ処理
- **未来の年度データを自動除外**：現在日付より未来の年度データは分析対象外
- **利用可能なデータを最大限使用**：最大10年分まで（プランに応じて調整可能）
- **キャッシュ機能**：APIレスポンスをキャッシュして効率的にデータ取得

### 不適格条件
- 営業CF < 営業利益が3年中2年以上
- FCFマイナス時に営業利益 < 投資CFの絶対値

### EDINET統合機能（定性情報分析）

有価証券報告書から最新年度の事業概要・経営方針・課題を自動取得・要約します。**EDINET API**と**ローカルLLM（Ollama）**を使用して、財務データだけでは分からない定性的な情報を分析します。

#### 機能概要

有価証券報告書から以下の情報を自動抽出・要約します：
- **事業戦略の具体的な施策**（数値目標、財務指標、事業指標、M&A・投資計画など）
- **事業環境**（市場規模・成長率、競争環境、技術動向、規制・法制度の変化など）
- **リスク要因**（事業リスク、財務リスク、経営リスク、リスク対策など）
- **その他の重要な取り組み**（技術開発、組織体制、サステナビリティなど）

#### EDINET API

**EDINET API**は、金融庁の企業内容等の開示に関する内閣府令に基づく有価証券報告書などの開示書類を取得するためのAPIです。

- **APIエンドポイント**: `https://api.edinet-fsa.go.jp/api/v2`
- **認証方式**: APIキー認証（`Ocp-Apim-Subscription-Key`ヘッダー）
- **取得データ**: 有価証券報告書のPDF/XBRLファイル
- **レート制限**: レート制限エラー時は自動的に待機してリトライ
- **キャッシュ**: 取得したPDFファイルは`reports/{code}_edinet/`に保存

**必要な準備**:
1. [EDINET API](https://disclosure2.edinet-fsa.go.jp/)からAPIキーを取得
2. `.env`に`EDINET_API_KEY`を設定

#### ローカルLLM（Ollama）

**ローカルLLM**は、Ollamaを使用して有価証券報告書のテキストを要約します。データを外部に送信せず、ローカル環境で処理するため、プライバシーとセキュリティを確保できます。

- **使用モデル**: `gemma2:2b`（軽量で高速な日本語対応モデル）
- **処理内容**: PDFから抽出したテキストを日本語で要約
- **出力形式**: マークダウン記法（見出し、箇条書き、強調表示）
- **キャッシュ機能**: 要約結果を`cache/edinet/summaries/`に保存して効率化

**必要な準備**:
```bash
# Ollamaのインストール（macOSの場合）
brew install ollama

# Ollamaを起動
ollama serve

# モデルをダウンロード
ollama pull gemma2:2b
```

#### 技術仕様

**処理フロー**:
1. **EDINET API**で有価証券報告書を検索・ダウンロード
2. **PDF解析**（`pdfplumber`）でPDFからテキストを抽出
3. **ローカルLLM**（Ollama `gemma2:2b`）でテキストを要約
4. 要約結果をHTMLレポートとCSVレポートに統合

**技術スタック**:
- **PDF解析**: `pdfplumber`を使用してPDFからテキストを抽出
- **LLM要約**: Ollamaの`gemma2:2b`モデルを使用して日本語で要約生成
- **マークダウン記法**: 見出し（`##`）、箇条書き（`-`）、強調（`**text**`）に対応
- **キャッシュ機能**: LLM要約結果をキャッシュして効率化

#### 出力内容

- **HTMLレポート**: 「最新の事業概要・経営方針・課題」セクションに最新年度の要約を表示
- **CSVレポート**: 「事業概要・経営方針・課題要約」列に要約テキストを追加
- **有報PDF**: `reports/{code}_edinet/`に保存
- **要約キャッシュ**: `cache/edinet/summaries/`に保存（再実行時に高速化）

#### テスト方法

```bash
python3 scripts/test_edinet.py
```

このスクリプトは以下をテストします：
- EDINET API接続テスト
- 有報取得テスト
- XBRL解析テスト
- LLM要約テスト（Ollama起動確認含む）
- 統合テスト（HTML/CSV生成）

## 注意事項

- 投資判断は自己責任で行ってください
- このツールは「適格性判断」のための分析ツールです
- 結果が良い = 投資推奨ではありません
- 必ず複数の情報源と併用してください
- EDINET統合機能はオプションです。APIキー未設定時はスキップされます
- LLM要約は日本語で出力されますが、英語の固有名詞（例: "EBITA"、"ROIC"）が含まれる場合があります

## レート制限対策

- **自動リトライ**：レート制限エラー時に自動的に待機してリトライ
- **エラーハンドリング**：レート制限に達しても取得できた分のデータで分析を継続
- **キャッシュ活用**：既に取得済みのデータはキャッシュから読み込み（APIコール削減）

## 関連ドキュメント

- [QUICKSTART.md](QUICKSTART.md) - セットアップとクイックスタートガイド
- [ARCHITECTURE.md](ARCHITECTURE.md) - プロジェクト構造とファイル説明
- [DATA_PROCESSING.md](DATA_PROCESSING.md) - データ加工フロー説明
- [API_USAGE.md](API_USAGE.md) - API使用ガイド（エンドポイント、パラメータ、エラーハンドリング）
- [CHANGELOG.md](CHANGELOG.md) - 更新履歴

## ライセンス

このプロジェクトは個人利用を目的としています。

