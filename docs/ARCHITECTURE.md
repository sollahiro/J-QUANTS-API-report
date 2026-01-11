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
├── data/                   # データ保存先
├── reports/                # 有価証券報告書PDF保存先
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
- **設定管理**:
  - `src/config.py`の`config`オブジェクトから設定を取得
  - 環境変数の直接読み込みは行わない（設定の一元管理）

**`src/api/edinet_client.py`**
- **役割**: EDINET APIとの通信を担当
- **主要機能**:
  - 有価証券報告書の検索（銘柄コードと年度から検索）
  - 書類のダウンロード（PDF形式とXBRL形式の両方に対応）
  - レート制限の管理（429エラー時の自動リトライ）
  - エラーハンドリングとリトライ処理
  - キャッシュディレクトリの管理
- **主要クラス**: `EdinetAPIClient`
- **設定管理**:
  - `src/config.py`の`config`オブジェクトから設定を取得
  - 環境変数の直接読み込みは行わない（設定の一元管理）
- **主要メソッド**:
  - `search_documents()` - 有報を検索（銘柄コード、年度、書類種別で検索）
  - `download_document()` - 書類をダウンロード（PDF形式とXBRL形式の両方に対応）
  - `fetch_reports()` - 指定年度の有報を取得（複数年度対応、PDFとXBRLの両方を取得）
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
  - グラフデータの生成（Plotlyグラフ用）
- **主要クラス**: `IndividualAnalyzer`

**`src/analysis/calculator.py`**
- **役割**: 財務指標の計算ロジック
- **主要機能**:
  - CAGR（年平均成長率）の計算
  - ROE、EPS、PER、PBR等の計算
  - FCF（フリーキャッシュフロー）の計算
  - 各種比率の算出
- **主要関数**: `calculate_metrics_flexible()`

**`src/analysis/xbrl_parser.py`**
- **役割**: XBRLファイルの解析（有価証券報告書からテキスト抽出）
- **主要機能**:
  - インラインXBRL（HTML形式）からセクションを抽出
  - XBRLインスタンス文書（XML形式）からテキストブロックを抽出
  - 報告書タイプの自動判定（有価証券報告書と半期報告書）
  - セクション抽出（事業の内容、経営方針、リスク要因など）
- **主要クラス**: `XBRLParser`
- **主要メソッド**:
  - `extract_section()` - 指定セクションを抽出
  - `extract_sections_by_type()` - 報告書タイプに応じたセクションを抽出
  - `extract_management_policy()` - 経営方針・課題を抽出
  - `extract_mda()` - 経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析を抽出
  - `_detect_report_type()` - 報告書タイプを判定
- **技術仕様**:
  - **使用ライブラリ**: 
    - `beautifulsoup4`（インラインXBRL（HTML形式）の解析）
    - `xml.etree.ElementTree`（XBRLインスタンス文書（XML形式）の解析）
  - **処理対象**: 有価証券報告書と半期報告書のXBRLファイル
  - **抽出セクション**（`COMMON_SECTIONS`で定義）:
    1. **事業の内容** (`A` - `DescriptionOfBusinessTextBlock`)
       - 会社の事業内容、主要製品・サービス、事業の特徴など
    2. **経営方針、経営環境及び対処すべき課題等** (`B` - `BusinessPolicyTextBlock`)
       - 経営方針、経営環境の変化、対処すべき課題、事業戦略など
    3. **事業等のリスク** (`C` - `BusinessRisksTextBlock`)
       - 事業リスク、財務リスク、経営リスク、リスク対策など
    4. **経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析** (`D` - `ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock`)
       - 経営成績の分析、財政状態の分析、キャッシュ・フロー状況の分析など
    5. **重要な契約等** (`E` - `ImportantContractsTextBlock`)
       - 重要な契約、取引先との関係、関連会社との取引など
    6. **設備投資等の概要** (`F` - `OverviewOfCapitalInvestmentTextBlock`)
       - 設備投資計画、研究開発投資、M&A計画など
  - **セクション抽出の順序**: A→B→C→D→E→Fの順で抽出し、結合してLLMに渡す
  - **報告書タイプの自動判定**: ファイル名やXML内容から有価証券報告書と半期報告書を自動判定

**`src/analysis/llm_summarizer.py`**
- **役割**: ローカルLLM（Ollama）を使用したテキスト要約
- **主要機能**:
  - Ollamaを使用した要約生成（`gemma3:1b`モデル、デフォルト）
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
  - **使用モデル**: `gemma3:1b`（デフォルト、環境変数`LLM_MODEL`で変更可能）
  - **モデル切り替え**: `.env`ファイルに`LLM_MODEL=モデル名`を設定することで、使用するモデルを変更可能（例: `LLM_MODEL=qwen3:8b`）
  - **タイムアウト**: 60秒（デフォルト）
  - **キャッシュ保存先**: `cache/edinet/summaries/{docID}_{section}.txt`
  - **プロンプト**: セクション名に応じて最適化されたプロンプトを使用
  - **設定管理**: `src/config.py`の`config.llm_model`からモデル名を取得

**`src/analysis/__init__.py`**
- 分析モジュールの公開インターフェースを定義

---

#### `src/report/` - グラフ生成

**`src/report/graph_generator.py`**
- **役割**: Plotlyグラフの生成
- **主要機能**:
  - PlotlyグラフのインタラクティブHTMLへの変換（Streamlit UIで表示用）
- **主要クラス**: `GraphGenerator`
- **主要メソッド**:
  - `_create_interactive_graphs()` - Plotlyグラフを生成（Streamlit UIで表示用）

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

**`src/utils/errors.py`**
- **役割**: カスタム例外クラスの定義とデータ可用性チェック
- **主要クラス**: 
  - `AnalysisError`: 分析処理関連のエラーの基底クラス
  - `InsufficientDataError`: データ不足エラー
- **主要関数**:
  - `check_data_availability()` - データ取得状況をチェック
  - `validate_metrics_for_analysis()` - 分析に必要なデータが揃っているか検証

**`src/utils/formatters.py`**
- **役割**: 数値や日付のフォーマット関数を提供
- **主要関数**:
  - `format_currency()` - 数値を百万円単位で表示
  - `extract_fiscal_year_from_fy_end()` - 年度終了日から年度を抽出

**`src/utils/__init__.py`**
- ユーティリティモジュールの公開インターフェースを定義

---

#### `src/ui/` - UIコンポーネント

**`src/ui/components.py`**
- **役割**: 分析結果の表示コンポーネントを提供
- **主要機能**:
  - 分析結果の表示（銘柄情報、財務データ、グラフ）
  - 有価証券報告書の要約表示
  - グラフのタブ形式表示
- **主要関数**:
  - `display_analysis_results()` - 分析結果を表示
  - `_display_business_overview()` - 事業概要・課題を表示
  - `_display_graphs()` - グラフをタブ形式で表示

**`src/ui/sidebar.py`**
- **役割**: StreamlitアプリケーションのサイドバーUIを提供
- **主要機能**:
  - 銘柄コード入力フォーム
  - 分析ボタン
  - キャッシュ削除機能
- **主要関数**:
  - `render_sidebar()` - サイドバーをレンダリング
  - `_clear_cache()` - キャッシュを削除

**`src/ui/table.py`**
- **役割**: 年度別財務データテーブルの生成を提供
- **主要機能**:
  - HTMLテーブルの生成（年度列固定、横スクロール対応）
  - ダークモード対応
- **主要関数**:
  - `create_financial_data_table()` - 年度別財務データのHTMLテーブルを生成

**`src/ui/styles.py`**
- **役割**: StreamlitアプリケーションのカスタムCSSを提供
- **主要機能**:
  - カラムレイアウトのスタイル定義
  - テーブルのスタイル定義
  - スクロールバーのスタイル定義
- **主要関数**:
  - `get_custom_css()` - カスタムCSSを取得

**`src/ui/analysis_handler.py`**
- **役割**: 銘柄分析の実行と進捗管理を提供
- **主要機能**:
  - 分析実行の統合処理
  - 進捗表示の管理
  - エラーハンドリング
- **主要関数**:
  - `run_analysis()` - 銘柄分析を実行

**`src/ui/__init__.py`**
- UIモジュールの公開インターフェースを定義

---

#### `src/config.py`
- **役割**: アプリケーション設定の一元管理
- **主要機能**:
  - 環境変数の読み込み（`dotenv`を使用）
  - 設定値のデフォルト値の定義
  - 設定の検証
  - プラン別の設定管理（J-QUANTS APIプランに応じた最大分析年数）
- **主要クラス**: `Config`
- **設計方針**:
  - 環境変数の直接読み込みを禁止し、このモジュール経由でアクセス
  - グローバル設定インスタンス（`config`）を提供し、アプリケーション全体で共有
- **設定項目**:
  - J-QUANTS API設定（APIキー、ベースURL）
  - EDINET API設定（APIキー）
  - LLM設定（モデル名、デフォルト: `gemma3:1b`、環境変数`LLM_MODEL`で変更可能）
  - 分析設定（分析年数、プラン設定）
  - キャッシュ設定（キャッシュディレクトリ、有効/無効）
  - データ保存設定（データディレクトリ）

---

### `scripts/` - 実行スクリプト

**`scripts/test_connection.py`**
- **役割**: API接続のテスト
- **機能**: J-QUANTS APIへの接続と認証をテスト

**`scripts/test_api_data.py`**
- **役割**: APIデータ取得のテスト
- **機能**: 各種エンドポイントからのデータ取得をテスト

**`scripts/test_analysis_years.py`**
- **役割**: 分析年数のテスト
- **機能**: 異なる年数での分析結果をテスト

**`scripts/test_edinet.py`**
- **役割**: EDINET統合機能のテスト
- **機能**: 
  - EDINET API接続テスト
  - 有報取得テスト（PDFとXBRLの両方）
  - XBRL解析テスト
  - LLM要約テスト（Ollama起動確認含む）
  - 統合テスト

---

### `app.py` - Streamlitアプリケーション

**`app.py`**
- **役割**: メインのWebインターフェース（Bento UIスタイル）
- **主要機能**:
  - 銘柄コード検索と分析実行
  - 分析結果の表示（左右独立スクロール）
  - 年度別財務データの表示
  - 最新の事業概要・課題の表示
  - インタラクティブな財務グラフの表示
  - 有報PDFダウンロード機能
  - キャッシュ管理機能
- **使用方法**: `streamlit run app.py`

---

### その他のディレクトリ

**`reports/`**
- 有価証券報告書PDFとXBRLの保存先
- **`reports/{code}_edinet/`**
  - 各銘柄の有価証券報告書PDF（`{docID}.pdf`）
  - 各銘柄の有価証券報告書XBRL（`{docID}_xbrl/`ディレクトリに展開）
  - Streamlit UIからPDFダウンロード可能

**`cache/`**
- APIレスポンスのキャッシュファイル（`.pkl`形式）を保存
- **`cache/edinet/`**（新規）
  - EDINETデータキャッシュ
  - **`cache/edinet/summaries/`**（新規）
    - LLM要約キャッシュ（`{docID}_{section}.txt`形式）

---

## データフロー

### 個別分析の流れ

1. **`app.py`** (Streamlitアプリ)
   - ユーザーが銘柄コードを入力して「分析」ボタンをクリック
   ↓
2. **`src/analysis/individual.py`** (`IndividualAnalyzer`)
   - **J-QUANTS API統合**:
     - `src/api/client.py` (`JQuantsAPIClient`) を使用して財務データ取得
     - `src/utils/cache.py` (`CacheManager`) でキャッシュ管理
   - **EDINET API統合**（オプション）:
     - `src/api/edinet_client.py` (`EdinetAPIClient`) で有価証券報告書を検索・ダウンロード
       - 銘柄コードと年度から有報を検索
       - PDFファイルとXBRLファイルをダウンロード（`reports/{code}_edinet/`に保存）
     - `src/analysis/xbrl_parser.py` (`XBRLParser`) でXBRLからテキストを抽出
       - `beautifulsoup4`を使用してインラインXBRL（HTML形式）からセクションを抽出
       - `xml.etree.ElementTree`を使用してXBRLインスタンス文書（XML形式）からテキストブロックを抽出
       - 事業の内容、経営方針、リスク要因などのセクションを抽出
     - `src/analysis/llm_summarizer.py` (`LLMSummarizer`) でローカルLLM要約生成
       - Ollama（`gemma3:1b`モデル、デフォルト）を使用してテキストを要約。環境変数`LLM_MODEL`で他のモデルに切り替え可能
       - 日本語出力を強制し、マークダウン記法で出力
       - 要約結果をキャッシュ（`cache/edinet/summaries/`に保存）
     - **注意**: PDFはダウンロード用のみで、要約にはXBRLを使用
   ↓
3. **`src/analysis/calculator.py`** で指標計算
   - 財務指標の計算（FCF、ROE、EPS、PER、PBR等）
   - CAGR（年平均成長率）の計算
   ↓
4. **`src/report/graph_generator.py`** (`GraphGenerator`) でグラフ生成
   - Plotlyグラフの生成（Streamlit UIで表示用）
   ↓
5. **`src/ui/components.py`** (`display_analysis_results`) でStreamlit UIに表示
   - 年度別財務データテーブルの表示
   - 有価証券報告書の要約表示（マークダウン記法対応）
   - Plotlyグラフのタブ形式表示
   - 有報PDFダウンロード機能

---

## 主要な依存関係

### 基本ライブラリ
- **`requests`**: HTTPリクエスト（J-QUANTS API、EDINET API）
- **`pandas`**: データ処理
- **`plotly`**: グラフ生成
- **`python-dotenv`**: 環境変数管理
- **`streamlit`**: Webアプリケーションフレームワーク

### EDINET統合機能関連
- **`ollama`**: ローカルLLM要約（Ollamaクライアントライブラリ）
- **`beautifulsoup4`**: XBRL解析（インラインXBRL（HTML形式）からセクション抽出）
- **`xml.etree.ElementTree`**: XBRL解析（XBRLインスタンス文書（XML形式）からテキストブロック抽出、標準ライブラリ）
- **`tqdm`**: プログレスバー表示（有報解析進捗表示）

### 外部サービス
- **J-QUANTS API**: 財務データ取得（必須）
- **EDINET API**: 有価証券報告書取得（オプション）
- **Ollama**: ローカルLLM実行環境（オプション、EDINET統合機能使用時）

---

## 拡張ポイント

### 新しい分析指標を追加する場合

1. **`src/analysis/calculator.py`** に計算ロジックを追加
2. **`src/report/graph_generator.py`** にグラフ生成ロジックを追加（必要に応じて）
3. **`src/ui/components.py`** に表示ロジックを追加（Streamlit UIで表示）

### 新しいグラフを追加する場合

1. **`src/report/graph_generator.py`** にグラフ生成ロジックを追加
2. **`src/ui/components.py`** に表示ロジックを追加（タブ形式で表示）

---


## コード品質と設計原則

### 設定管理の統一化

- **一元管理**: すべての環境変数は`src/config.py`の`Config`クラスで一元管理されます
- **直接読み込みの禁止**: モジュール内で`os.getenv()`や`load_dotenv()`を直接呼び出すことは禁止されています
- **設定の取得**: 各モジュールは`from src.config import config`で設定にアクセスします

### 型ヒントとdocstring

- **型ヒント**: すべての関数とメソッドに型ヒントを付与しています
- **docstring**: モジュール、クラス、関数にはdocstringを記述しています
- **docstring形式**: Google形式のdocstringを使用しています

### エラーハンドリング

- **カスタム例外**: `src/utils/errors.py`で定義されたカスタム例外クラスを使用します
- **エラーメッセージ**: ユーザーに分かりやすいエラーメッセージを提供します
- **ログ出力**: 重要なエラーはログに記録します

### インポートの整理

- **標準ライブラリ**: 標準ライブラリのインポートを最初に記述
- **サードパーティ**: サードパーティライブラリのインポートを次に記述
- **ローカルモジュール**: ローカルモジュールのインポートを最後に記述
- **不要なインポート**: 使用していないインポートは削除します

## 注意事項

- **キャッシュ**: API呼び出しは自動的にキャッシュされます。最新データが必要な場合はキャッシュをクリアしてください。
- **レート制限**: J-QUANTS APIにはレート制限があります。大量のデータ取得時は適切な待機時間が設定されています。
- **未来の年度データ**: 現在日付より未来の年度データは自動的に除外されます。
- **設定管理**: 環境変数の変更後は、アプリケーションを再起動してください。

---