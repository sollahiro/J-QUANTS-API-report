# Educe - 投資判断分析ツール

Educeは、J-QUANTS API・EDINET API・ローカルLLMを使用した投資判断分析ツールです。FCFを最重視し、**投資すべきでない銘柄を特定する**ことに重点を置いています。このツールは投資推奨ではなく、投資回避の判断をサポートします。

## 機能概要

### 個別詳細分析（メイン機能）
- 特定銘柄の詳細分析
- 最大10年分の財務データと各種指標を表示（利用可能なデータを最大限使用）
- **Streamlit UIでの表示**
  - 年度別財務データ表（年度列固定、横スクロール対応）
  - **最新の事業概要・経営方針・課題**
    - 最新年度の有価証券報告書から抽出した事業戦略・事業環境・リスク要因のLLM要約
    - マークダウン記法対応（見出し、箇条書き、強調表示）
    - 有価証券報告書PDFダウンロード機能
  - インタラクティブな財務グラフ（6種類、Plotlyグラフをタブ形式で表示）
    - **【事業の実力】**
      - 事業効率（簡易ROIC × CF変換率）
      - キャッシュフロー（FCF＝営業CF＋投資CF）
    - **【株主価値と市場評価】**
      - 株主価値の蓄積（EPS × BPS × ROE）
      - 配当政策と市場評価（配当性向 × ROE × PBR）
      - 市場評価（PER × ROE × PBR）
      - 株価とEPSの乖離
- **未来の年度データを自動除外**：現在日付より未来の年度データは分析対象外

## セットアップ

詳細なセットアップ手順は[QUICKSTART.md](docs/QUICKSTART.md)を参照してください。

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
   ollama pull gemma3:1b  # デフォルトモデル
   ```
5. **動作確認**: `python3 scripts/test_connection.py`

## 使用方法

### 動作確認（初回のみ推奨）

```bash
python3 scripts/test_connection.py
```

### 個別詳細分析

Streamlitアプリを使用します：

```bash
# Streamlitアプリを起動
streamlit run app.py
```

ブラウザでアプリが開いたら、検索バーに銘柄コード（例: 6501）を入力して「分析」ボタンをクリックしてください。

**表示内容：**
- **年度別財務データ表**：年度列固定、横スクロール対応のテーブル表示
- **有価証券報告書の要約**：最新年度の事業概要・経営方針・課題のLLM要約（マークダウン記法対応）
- **インタラクティブな財務グラフ**：Plotlyグラフをタブ形式で表示
  - 事業効率（簡易ROIC × CF変換率）
  - キャッシュフロー（FCF）
  - 株主価値の蓄積（EPS × BPS × ROE）
  - 配当政策と市場評価（配当性向 × ROE × PBR）
  - 市場評価（PER × ROE × PBR）
  - 株価とEPSの乖離
- **有報PDFダウンロード**：最新年度の有価証券報告書PDFをダウンロード可能

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
│   │   ├── xbrl_parser.py     # XBRL解析モジュール
│   │   └── llm_summarizer.py  # LLM要約モジュール
│   ├── report/
│   │   ├── __init__.py
│   │   └── graph_generator.py  # グラフ生成（PlotlyグラフのHTML変換）
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── financial_data.py  # 財務データ処理
│   │   ├── cache.py           # キャッシュ管理
│   │   ├── sectors.py         # 業種情報管理
│   │   └── errors.py          # カスタム例外クラス
│   └── config.py              # 設定管理
├── scripts/
│   ├── test_connection.py     # API接続テスト
│   ├── test_api_data.py       # APIデータテスト
│   ├── test_analysis_years.py # 分析年数テスト
│   └── test_edinet.py         # EDINET統合機能テスト
├── app.py                     # Streamlitアプリ（メインUI）
├── reports/                   # 有価証券報告書PDF保存先
│   └── {code}_edinet/         # 各銘柄の有価証券報告書PDF
├── cache/                     # APIレスポンスキャッシュ
│   └── edinet/                # EDINETデータキャッシュ
│       └── summaries/         # LLM要約キャッシュ
├── data/                      # データ保存先
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

### EDINET統合機能（定性情報分析）

有価証券報告書から最新年度の事業概要・経営方針・課題を自動取得・要約します。**EDINET API**と**ローカルLLM（Ollama）**を使用して、財務データだけでは分からない定性的な情報を分析します。

#### 機能概要

有価証券報告書から以下の情報を自動抽出・要約します：
- **事業戦略の具体的な施策**（数値目標、財務指標、事業指標、M&A・投資計画など）
- **事業環境**（市場規模・成長率、競争環境、技術動向、規制・法制度の変化など）
- **リスク要因**（事業リスク、財務リスク、経営リスク、リスク対策など）
- **その他の重要な取り組み**（技術開発、組織体制、サステナビリティなど）

#### 抽出対象セクション

XBRL解析では、有価証券報告書から以下の6つのセクションを抽出します：

1. **事業の内容** (`DescriptionOfBusinessTextBlock`)
   - 会社の事業内容、主要製品・サービス、事業の特徴など

2. **経営方針、経営環境及び対処すべき課題等** (`BusinessPolicyTextBlock`)
   - 経営方針、経営環境の変化、対処すべき課題、事業戦略など

3. **事業等のリスク** (`BusinessRisksTextBlock`)
   - 事業リスク、財務リスク、経営リスク、リスク対策など

4. **経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析** (`ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock`)
   - 経営成績の分析、財政状態の分析、キャッシュ・フロー状況の分析など

5. **重要な契約等** (`ImportantContractsTextBlock`)
   - 重要な契約、取引先との関係、関連会社との取引など

6. **設備投資等の概要** (`OverviewOfCapitalInvestmentTextBlock`)
   - 設備投資計画、研究開発投資、M&A計画など

これらのセクションから抽出したテキストを結合し、LLMで要約します。

#### EDINET API

**EDINET API**は、金融庁の企業内容等の開示に関する内閣府令に基づく有価証券報告書などの開示書類を取得するためのAPIです。

- **APIエンドポイント**: `https://api.edinet-fsa.go.jp/api/v2`
- **認証方式**: APIキー認証（`Ocp-Apim-Subscription-Key`ヘッダー）
- **取得データ**: 有価証券報告書のPDF/XBRLファイル（PDFはダウンロード用、XBRLは要約用）
- **レート制限**: レート制限エラー時は自動的に待機してリトライ
- **キャッシュ**: 取得したPDFファイルは`reports/{code}_edinet/`に保存

**必要な準備**:
1. [EDINET API](https://disclosure2.edinet-fsa.go.jp/)からAPIキーを取得
2. `.env`に`EDINET_API_KEY`を設定

#### ローカルLLM（Ollama）

**ローカルLLM**は、Ollamaを使用して有価証券報告書のテキストを要約します。データを外部に送信せず、ローカル環境で処理するため、プライバシーとセキュリティを確保できます。

- **使用モデル**: `gemma3:1b`（デフォルト、軽量で高速な日本語対応モデル）
- **モデル切り替え**: 環境変数`LLM_MODEL`でモデルを指定可能（例: `LLM_MODEL=qwen3:8b`）
- **処理内容**: XBRLから抽出したテキストを日本語で要約
- **出力形式**: マークダウン記法（見出し、箇条書き、強調表示）
- **キャッシュ機能**: 要約結果を`cache/edinet/summaries/`に保存して効率化

**必要な準備**:
   ```bash
# Ollamaのインストール（macOSの場合）
brew install ollama

# Ollamaを起動
   ollama serve

# モデルをダウンロード（使用するモデルを選択）
   ollama pull gemma3:1b  # デフォルトモデル
   # または他のモデル
   ollama pull qwen3:8b
   ollama pull gemma2:2b
   ```

**モデルの切り替え**:
`.env`ファイルに`LLM_MODEL`を設定することで、使用するモデルを切り替えられます：
```bash
# .envファイルに追加
LLM_MODEL=gemma3:1b  # デフォルト（軽量で高速）
# または他のモデル
LLM_MODEL=qwen3:8b   # より高性能なモデル
LLM_MODEL=gemma2:2b
LLM_MODEL=llama3:8b
```

**注意**: モデルを変更した場合は、Ollamaでそのモデルをダウンロードしておく必要があります（例: `ollama pull qwen3:8b`）。

#### 技術仕様

**処理フロー**:
1. **EDINET API**で有価証券報告書を検索・ダウンロード（PDFとXBRLの両方を取得）
2. **XBRL解析**（`beautifulsoup4`と`xml.etree.ElementTree`）でXBRLからテキストを抽出
3. **ローカルLLM**（Ollama `gemma3:1b`、デフォルト）でテキストを要約
4. 要約結果をStreamlit UIに表示

**技術スタック**:
- **XBRL解析**: 
  - `beautifulsoup4`を使用してインラインXBRL（HTML形式）からセクションを抽出
  - `xml.etree.ElementTree`を使用してXBRLインスタンス文書（XML形式）からテキストブロックを抽出
- **LLM要約**: Ollamaの`gemma3:1b`モデル（デフォルト）を使用して日本語で要約生成。環境変数`LLM_MODEL`で他のモデルに切り替え可能
- **マークダウン記法**: 見出し（`##`）、箇条書き（`-`）、強調（`**text**`）に対応
- **キャッシュ機能**: LLM要約結果をキャッシュして効率化
- **PDFとXBRLの使い分け**: PDFはダウンロード用のみ、要約にはXBRLを使用

#### 出力内容

- **Streamlit UI**: 「有価証券報告書の要約」セクションに最新年度の要約を表示（マークダウン記法対応）
- **有報PDF**: `reports/{code}_edinet/`に保存
- **要約キャッシュ**: `cache/edinet/summaries/`に保存（再実行時に高速化）

#### テスト方法

```bash
python3 scripts/test_edinet.py
```

このスクリプトは以下をテストします：
- EDINET API接続テスト
- 有報取得テスト（PDFとXBRLの両方）
- XBRL解析テスト
- LLM要約テスト（Ollama起動確認含む）
- 統合テスト

## 注意事項

- **投資判断は自己責任で行ってください**
- **このツールの目的**: 投資すべきでない銘柄を特定することに重点を置いています
- **結果の解釈**:
- 結果が良い = 投資推奨ではありません
  - 結果が悪い = 投資回避の判断材料となります
  - 本ツールは「投資すべきか」ではなく「投資すべきでないか」を判断するためのツールです
- **必ず複数の情報源と併用してください**
- EDINET統合機能はオプションです。APIキー未設定時はスキップされます
- LLM要約は日本語で出力されますが、英語の固有名詞（例: "EBITA"、"ROIC"）が含まれる場合があります

## レート制限対策

- **自動リトライ**：レート制限エラー時に自動的に待機してリトライ
- **エラーハンドリング**：レート制限に達しても取得できた分のデータで分析を継続
- **キャッシュ活用**：既に取得済みのデータはキャッシュから読み込み（APIコール削減）

## 関連ドキュメント

- [QUICKSTART.md](docs/QUICKSTART.md) - セットアップとクイックスタートガイド
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - プロジェクト構造とファイル説明
- [DATA_PROCESSING.md](docs/DATA_PROCESSING.md) - データ加工フロー説明
- [API_USAGE.md](docs/API_USAGE.md) - API使用ガイド（エンドポイント、パラメータ、エラーハンドリング）
- [CHANGELOG.md](docs/CHANGELOG.md) - 更新履歴

## ライセンス

このプロジェクトは個人利用を目的としています。

