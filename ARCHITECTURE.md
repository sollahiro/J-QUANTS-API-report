# プロジェクト構造とファイル説明

このドキュメントでは、投資判断分析ツールのプロジェクト構造と各ファイルの役割を説明します。

## プロジェクト構造

```
Educe/
├── src/                    # メインソースコード
│   ├── api/                # J-QUANTS API関連
│   ├── analysis/           # 分析ロジック
│   ├── report/             # レポート生成
│   ├── utils/              # ユーティリティ
│   └── config.py              # 設定管理
├── scripts/                # 実行スクリプト
├── notebooks/              # Jupyter Notebook
├── templates/              # HTMLテンプレート
├── static/                 # 静的ファイル（CSS等）
├── data/                   # データ保存先
├── reports/                # レポート出力先
└── cache/                  # キャッシュ保存先
```

---

## ディレクトリ別説明

### `src/` - メインソースコード

#### `src/api/` - API関連

**`src/api/client.py`**
- **役割**: J-QUANTS APIとの通信を担当
- **主要機能**:
  - API認証（リフレッシュトークンの取得・更新）
  - 各種エンドポイントへのリクエスト送信
  - レート制限の管理
  - エラーハンドリングとリトライ処理
- **主要クラス**: `JQuantsAPIClient`

**`src/api/edinet_client.py`**
- **役割**: EDINET APIとの通信を担当
- **主要機能**:
  - 有価証券報告書の検索（銘柄コードと年度から検索）
  - 書類のダウンロード（PDF/XBRL形式）
  - レート制限の管理（429エラー時の自動リトライ）
  - エラーハンドリングとリトライ処理
  - キャッシュディレクトリの管理
- **主要クラス**: `EdinetAPIClient`
- **主要メソッド**:
  - `search_documents()` - 有報を検索（銘柄コード、年度、書類種別で検索）
  - `download_document()` - 書類をダウンロード（PDF/XBRL形式）
  - `fetch_reports()` - 指定年度の有報を取得（複数年度対応）
- **API仕様**:
  - **ベースURL**: `https://api.edinet-fsa.go.jp/api/v2`
  - **認証方式**: APIキー認証（`Ocp-Apim-Subscription-Key`ヘッダー）
  - **レート制限**: 429エラー時に自動的に待機してリトライ（最大3回）
  - **タイムアウト**: 60秒

**`src/api/__init__.py`**
- APIモジュールの公開インターフェースを定義

---

#### `src/analysis/` - 分析ロジック

**`src/analysis/individual.py`**
- **役割**: 個別銘柄の詳細分析を実行
- **主要機能**:
  - 財務データの取得と整理
  - 年度別データの抽出
  - 各種財務指標の計算
  - 分析結果の統合
  - HTMLレポートデータの生成
- **主要クラス**: `IndividualAnalyzer`

**`src/analysis/calculator.py`**
- **役割**: 財務指標の計算ロジック
- **主要機能**:
  - CAGR（年平均成長率）の計算
  - ROE、EPS、PER、PBR等の計算
  - FCF（フリーキャッシュフロー）の計算
  - 各種比率の算出
- **主要関数**: `calculate_metrics_flexible()`

**`src/analysis/pdf_parser.py`**
- **役割**: PDFファイルの解析（有価証券報告書からテキスト抽出）
- **主要機能**:
  - 有価証券報告書PDFからテキストを抽出（`pdfplumber`を使用）
  - セクション抽出（経営方針・課題等）
  - テキスト整形（不要な改行や空白の除去）
- **主要クラス**: `PDFParser`
- **主要メソッド**:
  - `extract_section()` - 指定セクションを抽出
  - `extract_management_policy()` - 経営方針・課題を抽出
- **技術仕様**:
  - **使用ライブラリ**: `pdfplumber`（PDFからテキストを抽出）
  - **処理対象**: 有価証券報告書のPDFファイル
  - **抽出セクション**: 経営方針・課題セクション（事業戦略、事業環境、リスク要因など）

**`src/analysis/llm_summarizer.py`**
- **役割**: ローカルLLM（Ollama）を使用したテキスト要約
- **主要機能**:
  - Ollamaを使用した要約生成（`gemma2:2b`モデル）
  - 日本語出力の強制（英語の固有名詞も日本語に翻訳）
  - マークダウン記法での出力（見出し、箇条書き、強調）
  - キャッシュ機能（要約結果をファイルに保存）
  - エラーハンドリング（Ollama未起動時の適切な処理）
- **主要クラス**: `LLMSummarizer`
- **主要メソッド**:
  - `summarize_text()` - テキストを要約（マークダウン記法で出力）
  - `_check_ollama_available()` - Ollamaが利用可能かチェック
  - `_get_cache_path()` - キャッシュファイルのパスを取得
- **技術仕様**:
  - **使用モデル**: `gemma2:2b`（軽量で高速な日本語対応モデル）
  - **タイムアウト**: 60秒（デフォルト）
  - **キャッシュ保存先**: `cache/edinet/summaries/{docID}_{section}.txt`
  - **プロンプト**: セクション名に応じて最適化されたプロンプトを使用

**`src/analysis/__init__.py`**
- 分析モジュールの公開インターフェースを定義

---

#### `src/report/` - レポート生成

**`src/report/html_report.py`**
- **役割**: HTMLレポートとCSVレポートの生成
- **主要機能**:
  - 分析結果からHTMLレポートを生成
  - CSVレポートの自動生成（HTMLレポートと同じデータをCSV形式で出力）
  - PlotlyグラフのインタラクティブHTMLへの変換
  - 総合評価の計算（事業効率、株主価値、配当政策、市場評価用）
  - CAGR（年平均成長率）の計算
  - Jinja2テンプレートを使用したレンダリング
  - EDINETデータの統合（定性情報分析セクション）
- **主要クラス**: `HTMLReportGenerator`
- **主要メソッド**:
  - `generate()` - HTMLレポートとCSVレポートを生成（EDINETデータを含む）
  - `_create_interactive_graphs()` - グラフ生成
  - `_generate_csv()` - CSVレポート生成（純粋なデータのみ、グラフ評価情報は含まない、EDINETデータ列を含む）
- **主要関数**: 
  - `calculate_cagr()` - CAGR計算関数
  - `evaluate_business_efficiency_pattern()` - 事業効率パターン評価（4パターン）
  - `evaluate_shareholder_value_pattern()` - 株主価値パターン評価（5類型）
  - `evaluate_dividend_policy_pattern()` - 配当政策パターン評価（8パターン）
  - `evaluate_market_valuation_pattern()` - 市場評価パターン評価（8パターン）

**`src/report/__init__.py`**
- レポートモジュールの公開インターフェースを定義

---

#### `src/utils/` - ユーティリティ

**`src/utils/cache.py`**
- **役割**: データキャッシュの管理
- **主要機能**:
  - APIレスポンスのキャッシュ保存・読み込み
  - キャッシュの有効期限管理
  - キャッシュのクリア機能
- **主要クラス**: `CacheManager`

**`src/utils/financial_data.py`**
- **役割**: 財務データの処理と変換
- **主要機能**:
  - 年度別データの抽出
  - データの整形と正規化
  - 未来の年度データの除外
  - 四半期データ抽出機能（現在は未使用）
- **主要関数**: `extract_annual_data()`

**`src/utils/sectors.py`**
- **役割**: 業種情報の管理
- **主要機能**:
  - 業種コードと名称のマッピング
  - 業種情報の取得
- **主要関数**: `get_sector_name()`

**`src/utils/watchlist.py`**
- **役割**: ウォッチリストの管理
- **主要機能**:
  - 銘柄の追加・削除
  - タグ管理
  - CSV/JSON形式でのエクスポート・インポート
- **主要クラス**: `WatchlistManager`

**`src/utils/errors.py`**
- **役割**: カスタム例外クラスの定義
- **主要クラス**: 
  - `JQuantsAPIError`: API関連のエラー
  - `AnalysisError`: 分析処理関連のエラー
  - `CacheError`: キャッシュ関連のエラー

**`src/utils/__init__.py`**
- ユーティリティモジュールの公開インターフェースを定義

---

#### `src/config.py`
- **役割**: アプリケーション設定の管理
- **主要機能**:
  - 環境変数の読み込み
  - 設定値のデフォルト値の定義
  - 設定の検証

---

### `scripts/` - 実行スクリプト

**`scripts/notebook_analysis.py`**
- **役割**: Jupyter Notebookを実行するラッパースクリプト
- **機能**: 銘柄コードを引数として受け取り、Notebookを実行
- **使用方法**: `python3 scripts/notebook_analysis.py 6501 [2802 ...]`

**`scripts/watchlist_manager.py`**
- **役割**: ウォッチリストの管理
- **機能**: 銘柄の追加・削除、タグ管理、エクスポート・インポート
- **使用方法**: `python3 scripts/watchlist_manager.py [add|remove|list|export|import] ...`

**`scripts/test_connection.py`**
- **役割**: API接続のテスト
- **機能**: J-QUANTS APIへの接続と認証をテスト

**`scripts/test_api_data.py`**
- **役割**: APIデータ取得のテスト
- **機能**: 各種エンドポイントからのデータ取得をテスト

**`scripts/test_analysis_years.py`**
- **役割**: 分析年数のテスト
- **機能**: 異なる年数での分析結果をテスト

**`scripts/test_edinet.py`**（新規）
- **役割**: EDINET統合機能のテスト
- **機能**: 
  - EDINET API接続テスト
  - 有報取得テスト
  - XBRL解析テスト
  - LLM要約テスト
  - 統合テスト（HTML/CSV生成）

---

### `notebooks/` - Jupyter Notebook

**`notebooks/individual_analysis_template.ipynb`**
- **役割**: 個別銘柄の詳細分析用Notebook
- **主要セクション**:
  1. 分析対象銘柄の設定
  2. データ取得と分析（年度別データのみ）
  3. ビジュアルHTMLレポート生成（プレゼンテーション品質のレポート）
- **使用方法**: Jupyter Notebookで開いて実行、または`scripts/notebook_analysis.py`から実行

---

### `templates/` - HTMLテンプレート

**`templates/report_template.html`**
- **役割**: HTMLレポートのJinja2テンプレート
- **主要セクション**:
  - ヘッダー（銘柄情報、業種・市場区分・取得年月）
  - 年度別財務データテーブル
  - **最新の事業概要・経営方針・課題**（新規）
    - 最新年度の有価証券報告書から抽出した要約を表示
    - マークダウン記法対応（見出し、箇条書き、強調表示）
    - 有報PDFへのリンク
  - 財務グラフ（Plotlyインタラクティブグラフ）
    - **【事業の実力】**
      - 事業効率（簡易ROIC × CF変換率、総合評価付き）
      - キャッシュフロー（FCF＝営業CF＋投資CF）
    - **【株主価値と市場評価】**
      - 株主価値の蓄積（EPS × BPS × ROE、総合評価付き）
      - 配当政策と市場評価（配当性向 × ROE × PBR、総合評価付き）
      - 市場評価（PER × ROE × PBR、総合評価付き）
      - 株価とEPSの乖離

---

### `static/` - 静的ファイル

**`static/css/report.css`**
- **役割**: HTMLレポートのスタイルシート
- **主要スタイル**:
  - ページレイアウト（ページ分割なし、連続表示）
  - グラフコンテナのスタイル（白背景ボックスでセクション区分け）
  - セクションタイトル・グラフタイトルのスタイル（中央揃え）
  - テーブルのスタイル
  - 総合評価セクションのスタイル（CAGR左、パターンマッピング右）
  - 評価バッジの色分け（最良、良い、注意、危険、回避、要精査、妙味）
  - 評価コメントの色付き表示（評価に応じた色分け）
  - **最新の事業概要・経営方針・課題セクションのスタイル**（新規）
    - マークダウン記法のHTML変換スタイル（見出し、箇条書き、強調表示）
    - 数字付き箇条書き（`ol`）と通常の箇条書き（`ul`）のネスト構造に対応
  - 印刷用スタイル（ページ分割なし）

---

### その他のディレクトリ

**`reports/`**
- 生成されたHTMLレポート（`.html`）とCSVレポート（`.csv`）を保存
- ファイル名形式: `visual_report_{銘柄コード}_{タイムスタンプ}.html` / `.csv`
- **`reports/{code}_edinet/`**（新規）
  - 有価証券報告書PDF（`{docID}.pdf`）
  - XBRL展開ディレクトリ（`{docID}_xbrl/`）

**`cache/`**
- APIレスポンスのキャッシュファイル（`.pkl`形式）を保存
- **`cache/edinet/`**（新規）
  - EDINETデータキャッシュ
  - **`cache/edinet/summaries/`**（新規）
    - LLM要約キャッシュ（`{docID}_{section}.txt`形式）

---

## データフロー

### 個別分析の流れ

1. **`scripts/notebook_analysis.py`** または **`notebooks/individual_analysis_template.ipynb`**
   ↓
2. **`src/analysis/individual.py`** (`IndividualAnalyzer`)
   - **J-QUANTS API統合**:
     - `src/api/client.py` (`JQuantsAPIClient`) を使用して財務データ取得
     - `src/utils/cache.py` (`CacheManager`) でキャッシュ管理
   - **EDINET API統合**（オプション）:
     - `src/api/edinet_client.py` (`EdinetAPIClient`) で有価証券報告書を検索・ダウンロード
       - 銘柄コードと年度から有報を検索
       - PDF/XBRLファイルをダウンロード（`reports/{code}_edinet/`に保存）
     - `src/analysis/pdf_parser.py` (`PDFParser`) でPDFからテキストを抽出
       - `pdfplumber`を使用してPDFからテキストを抽出
       - 経営方針・課題セクションを抽出
     - `src/analysis/llm_summarizer.py` (`LLMSummarizer`) でローカルLLM要約生成
       - Ollama（`gemma2:2b`モデル）を使用してテキストを要約
       - 日本語出力を強制し、マークダウン記法で出力
       - 要約結果をキャッシュ（`cache/edinet/summaries/`に保存）
   ↓
3. **`src/analysis/calculator.py`** で指標計算
   - 財務指標の計算（FCF、ROE、EPS、PER、PBR等）
   - CAGR（年平均成長率）の計算
   ↓
4. **`src/report/html_report.py`** (`HTMLReportGenerator`) でレポート生成
   - 総合評価の計算（CAGRに基づくパターン評価）
   - Plotlyグラフの生成
   - `templates/report_template.html` を使用してHTMLレポート生成
   - `static/css/report.css` でスタイリング
   - CSVレポートの自動生成（HTMLレポートと同じデータをCSV形式で出力、EDINETデータ列を含む）
   - EDINET統合データの統合（事業概要・経営方針・課題要約をHTML/CSVに追加）

---

## 主要な依存関係

### 基本ライブラリ
- **`requests`**: HTTPリクエスト（J-QUANTS API、EDINET API）
- **`pandas`**: データ処理
- **`plotly`**: グラフ生成
- **`jinja2`**: テンプレートエンジン
- **`python-dotenv`**: 環境変数管理
- **`jupyter`**: Notebook実行環境

### EDINET統合機能関連
- **`ollama`**: ローカルLLM要約（Ollamaクライアントライブラリ）
- **`pdfplumber`**: PDF解析（有価証券報告書からテキスト抽出）
- **`tqdm`**: プログレスバー表示（有報解析進捗表示）

### 外部サービス
- **J-QUANTS API**: 財務データ取得（必須）
- **EDINET API**: 有価証券報告書取得（オプション）
- **Ollama**: ローカルLLM実行環境（オプション、EDINET統合機能使用時）

---

## 拡張ポイント

### 新しい分析指標を追加する場合

1. **`src/analysis/calculator.py`** に計算ロジックを追加
2. **`src/report/html_report.py`** にグラフ生成ロジックを追加（必要に応じて）
3. **`templates/report_template.html`** に表示を追加

### 新しいレポート形式を追加する場合

1. **`src/report/`** に新しいレポート生成クラスを追加
2. **`templates/`** に新しいテンプレートを追加（必要に応じて）

---

## 総合評価パターン一覧

HTMLレポートでは、CAGR（年平均成長率）に基づいて各グラフの総合評価を表示します。

### グラフ1：事業効率（簡易ROIC × CF変換率）

| パターン | 簡易ROIC | CF変換率 | 状態 | 評価 | 投資視点 |
|---------|---------|---------|------|------|---------|
| ① | + | + | 質量拡大 | 最良 | 効率も質も向上 |
| ② | + | − | 効率↑質↓ | 要注意 | 短期的要因か投資増加の可能性 |
| ③ | − | + | 効率↓質↑ | 注意 | 利益効率低下だが現金創出力は確保 |
| ④ | − | − | 質量劣化 | 回避 | 効率・現金創出ともに悪化 |

### グラフ3：株主価値の蓄積（EPS × BPS × ROE）

| 類型 | EPS | BPS | ROE | 状態 | 評価 | 投資視点 |
|------|-----|-----|-----|------|------|---------|
| A | + | + | + | 王道成長 | 最良 | 利益と資本効率が同時拡大。長期保有。 |
| B | + | − | + | 資本回収型 | 良い | 成長余地低下・キャッシュ創出型 |
| C | − | + | − | 失敗拡張 | 悪い | 増資・低収益投資。原則回避。 |
| D | − | − | ± | 縮小・撤退 | 注意 | 清算価値・再編期待の有無を確認。 |
| E | ± | + | − | 非効率膨張 | 要精査 | 遊休資産・過剰内部留保の可能性 |

注: ±はCAGRの推移を問わず（他のプラスマイナスに従う）という意味

### グラフ4：配当政策と市場評価（ROE × PBR × 配当性向）

| パターン | ROE | PBR | 配当性向 | 状態 | 評価 | 投資視点 |
|---------|-----|-----|---------|------|------|---------|
| ① | + | + | + | 理想型 | 最良 | 稼いで評価されて返す |
| ② | + | + | − | 成長投資型 | 良い | 稼いで評価、内部留保で成長 |
| ③ | + | − | + | 割安還元型 | 割安 | 稼いで返すも過小評価 |
| ④ | + | − | − | 評価されず | 割安 | 稼ぐ力はあるが市場評価低め |
| ⑤ | − | + | + | 還元で延命 | 注意 | ROE低いが配当高で市場評価は維持 |
| ⑥ | − | + | − | 謎の高評価 | 警戒 | ROE低いがPBR高。市場期待先行の可能性 |
| ⑦ | − | − | + | 悪化中還元 | 悪い | 還元強化も評価下落 |
| ⑧ | − | − | − | 全面悪化 | 回避 | 全て悪化 |

### グラフ5：市場評価（PER × ROE × PBR）

| パターン | PER | ROE | PBR | 状態 | 評価 | 投資視点 |
|---------|-----|-----|-----|------|------|---------|
| ① | + | + | + | 成長再評価 | 注意 | 実力↑ × 期待↑ |
| ② | + | + | − | 質疑義 | 要精査 | ROE改善の質に疑問 |
| ③ | + | − | + | 期待先行 | 危険 | 実力悪化でも評価↑ |
| ④ | + | − | − | 期待乖離 | 要精査 | 期待↑だが実体↓ |
| ⑤ | − | + | + | 静かな改善 | 妙味 | 実力↑なのに評価控えめ |
| ⑥ | − | + | − | 割安候補 | 妙味 | 実力↑・市場未評価 |
| ⑦ | − | − | + | 見せかけ | 危険 | 実体↓だが評価↑ |
| ⑧ | − | − | − | 崩壊 | 回避 | 全部悪化 |

---

## 注意事項

- **キャッシュ**: API呼び出しは自動的にキャッシュされます。最新データが必要な場合はキャッシュをクリアしてください。
- **レート制限**: J-QUANTS APIにはレート制限があります。大量のデータ取得時は適切な待機時間が設定されています。
- **未来の年度データ**: 現在日付より未来の年度データは自動的に除外されます。

---