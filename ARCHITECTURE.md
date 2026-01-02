# プロジェクト構造とファイル説明

このドキュメントでは、J-QUANTS投資判断分析ツールのプロジェクト構造と各ファイルの役割を説明します。

## プロジェクト構造

```
jquants-analyzer/
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

#### `src/api/` - J-QUANTS API関連

**`src/api/client.py`**
- **役割**: J-QUANTS APIとの通信を担当
- **主要機能**:
  - API認証（リフレッシュトークンの取得・更新）
  - 各種エンドポイントへのリクエスト送信
  - レート制限の管理
  - エラーハンドリングとリトライ処理
- **主要クラス**: `JQuantsAPIClient`

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
  - 四半期データ取得機能は削除済み（年度別データのみ）
- **主要クラス**: `IndividualAnalyzer`

**`src/analysis/calculator.py`**
- **役割**: 財務指標の計算ロジック
- **主要機能**:
  - CAGR（年平均成長率）の計算
  - ROE、EPS、PER、PBR等の計算
  - FCF（フリーキャッシュフロー）の計算
  - 各種比率の算出
- **主要関数**: `calculate_metrics_flexible()`


**`src/analysis/screening.py`**
- **役割**: 銘柄スクリーニングロジック
- **主要機能**:
  - 条件に基づく銘柄のフィルタリング
  - スクリーニング結果の評価
- **主要クラス**: `Screener`

**`src/analysis/__init__.py`**
- 分析モジュールの公開インターフェースを定義

---

#### `src/report/` - レポート生成

**`src/report/html_report.py`**
- **役割**: HTMLレポートの生成
- **主要機能**:
  - 分析結果からHTMLレポートを生成
  - PlotlyグラフのインタラクティブHTMLへの変換
  - 総合評価の計算（ROE/EPS/BPS推移、PER/PBR/ROE推移用）
  - CAGR（年平均成長率）の計算
  - Jinja2テンプレートを使用したレンダリング
- **主要クラス**: `HTMLReportGenerator`
- **主要関数**: `calculate_cagr()` - CAGR計算関数

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

**`scripts/screening.py`**
- **役割**: 銘柄スクリーニングの実行
- **機能**: FCF 3年連続プラスなどの条件で銘柄をスクリーニング
- **使用方法**: `python3 scripts/screening.py [業種コード] [--count N] [--no-random]`

**`scripts/notebook_analysis.py`**
- **役割**: Jupyter Notebookを実行するラッパースクリプト
- **機能**: 銘柄コードを引数として受け取り、Notebookを実行
- **使用方法**: `python3 scripts/notebook_analysis.py 6501 [2802 ...]`

**`scripts/analyze_stock.py`**
- **役割**: 個別銘柄の分析を実行（CLI版）
- **機能**: 銘柄コードを指定して分析を実行し、結果を表示

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

**`scripts/debug_api.py`**
- **役割**: APIデバッグ用スクリプト
- **機能**: API呼び出しの詳細なログ出力とデバッグ

---

### `notebooks/` - Jupyter Notebook

**`notebooks/individual_analysis_template.ipynb`**
- **役割**: 個別銘柄の詳細分析用Notebook
- **主要セクション**:
  1. 分析対象銘柄の設定
  2. データ取得と分析（年度別データのみ、四半期データ取得機能は削除済み）
  3. ビジュアルHTMLレポート生成（プレゼンテーション品質のレポート）
- **使用方法**: Jupyter Notebookで開いて実行、または`scripts/notebook_analysis.py`から実行

---

### `templates/` - HTMLテンプレート

**`templates/report_template.html`**
- **役割**: HTMLレポートのJinja2テンプレート
- **主要セクション**:
  - ヘッダー（銘柄情報、業種・市場区分・取得年月）
  - 年度別財務データテーブル
  - 財務グラフ（Plotlyインタラクティブグラフ）
    - FCF推移（営業利益 vs 営業CF）
    - ROE/EPS/BPS推移（総合評価付き：CAGRに基づく8パターン評価、評価コメント色付き表示）
    - PER/PBR/ROE推移（総合評価付き：CAGRに基づく8パターン評価、評価コメント色付き表示）
    - 売上高推移
    - 株価 vs EPS指数化比較（一番古い年を基準として指数化）
    - PER推移 vs EPS年次成長率（期待と実績の比較）

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
  - 印刷用スタイル（ページ分割なし）

---

### その他のディレクトリ

**`reports/`**
- 生成されたHTMLレポートを保存

**`cache/`**
- APIレスポンスのキャッシュファイル（`.pkl`形式）を保存

---

## データフロー

### 個別分析の流れ

1. **`scripts/notebook_analysis.py`** または **`notebooks/individual_analysis_template.ipynb`**
   ↓
2. **`src/analysis/individual.py`** (`IndividualAnalyzer`)
   - `src/api/client.py` (`JQuantsAPIClient`) を使用してデータ取得
   - `src/utils/cache.py` (`CacheManager`) でキャッシュ管理
   ↓
3. **`src/analysis/calculator.py`** で指標計算
   ↓
4. **`src/report/html_report.py`** (`HTMLReportGenerator`) でレポート生成
   - 総合評価の計算（CAGRに基づく8パターン評価）
   - Plotlyグラフの生成
   - `templates/report_template.html` を使用
   - `static/css/report.css` でスタイリング
   

### スクリーニングの流れ

1. **`scripts/screening.py`**
   ↓
2. **`src/analysis/screening.py`** (`Screener`)
   - `src/api/client.py` で全銘柄データ取得
   - 条件でフィルタリング
   ↓
3. 結果を表示

---

## 主要な依存関係

- **`requests`**: HTTPリクエスト
- **`pandas`**: データ処理
- **`plotly`**: グラフ生成
- **`jinja2`**: テンプレートエンジン
- **`python-dotenv`**: 環境変数管理
- **`jupyter`**: Notebook実行環境

---

## 拡張ポイント

### 新しい分析指標を追加する場合

1. **`src/analysis/calculator.py`** に計算ロジックを追加
2. **`src/report/html_report.py`** にグラフ生成ロジックを追加（必要に応じて）
3. **`templates/report_template.html`** に表示を追加

### 新しいレポート形式を追加する場合

1. **`src/report/`** に新しいレポート生成クラスを追加
2. **`templates/`** に新しいテンプレートを追加（必要に応じて）

### 新しいスクリーニング条件を追加する場合

1. **`src/analysis/screening.py`** にフィルタリングロジックを追加
2. **`scripts/screening.py`** にコマンドライン引数を追加（必要に応じて）

---

## 注意事項

- **キャッシュ**: API呼び出しは自動的にキャッシュされます。最新データが必要な場合はキャッシュをクリアしてください。
- **レート制限**: J-QUANTS APIにはレート制限があります。大量のデータ取得時は適切な待機時間が設定されています。
- **未来の年度データ**: 現在日付より未来の年度データは自動的に除外されます。

---

## 更新履歴

- 2025-01-02: PER/PBR/ROE推移のパターンマッピングを更新
  - パターン名、評価、評価コメントを更新
  - 評価コメントを評価に応じて色付きで表示（ROE/EPS/BPS推移と同様）
  - 「妙味」評価のCSSクラスを追加
- 2025-01-02: 四半期別過熱感分析機能を削除
  - 四半期別財務データの表を削除
  - 四半期別グラフ（財務グラフ（トレンド分析））を削除
  - 財務グラフ（長期分析）の括弧を削除（「財務グラフ」に統一）
  - 四半期データ取得・計算時のログ出力を削除
- 2025-01-02: HTMLレポートのレイアウト改善
  - セクションタイトルとグラフタイトルの分離表示
  - グラフごとのセクション区分け（白背景ボックス）
  - 総合評価のレイアウト改善（CAGR左側、パターンマッピング右側の白背景ボックス）
  - ページ分割の廃止（連続表示）
  - セクションタイトル・グラフタイトル・グラフの間隔を最適化
- 2025-01-XX: 総合評価機能を追加（ROE/EPS/BPS推移、PER/PBR/ROE推移のグラフ下にCAGRに基づく8パターン評価を表示）
- 2025-01-XX: 株価 vs EPS指数化比較を追加（一番古い年を基準として指数化）
- 2025-01-XX: PER推移 vs EPS年次成長率グラフを追加（期待と実績の比較）
- 2025-01-XX: HTMLレポートからメトリクスカードを削除、グラフと総合評価に焦点を当てた構成に変更
- 2025-01-XX: レポート形式表示からアラート処理を削除
- 2025-01-XX: HTMLレポートのヘッダーから適格判定を削除、業種・市場区分・取得年月を2段目に表示
- 2025-01-01: PDF生成機能を削除し、HTMLレポートのみに統一
- 2025-01-01: グラフレイアウトを全て1列表示に変更
- 2025-01-01: ファイル名を`pdf_report.py`から`html_report.py`に変更

