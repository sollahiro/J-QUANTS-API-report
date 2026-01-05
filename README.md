# J-QUANTS API 投資判断分析ツール

J-QUANTS APIを使用した投資判断分析ツールです。FCFを最重視し、堅実な投資判断をサポートします。

## 機能概要

### 個別詳細分析（メイン機能）
- 特定銘柄の詳細分析（複数銘柄対応）
- 最大10年分の財務データと各種指標を表示（利用可能なデータを最大限使用）
- **レポート形式**：数値表
- **HTMLレポート生成**：プレゼンテーション品質のビジュアルレポート
  - 年度別財務データ表
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

1. **APIキーの取得**: [J-QUANTS Dashboard](https://jpx-jquants.com/)からAPIキーを取得
2. **環境変数の設定**: `.env.example`を`.env`にコピーし、APIキーを設定
3. **依存パッケージのインストール**: `pip install -r requirements.txt`
4. **動作確認**: `python3 scripts/test_connection.py`

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
- レポート形式：数値表（年度別財務データ）
- **HTMLレポート**：プレゼンテーション品質のビジュアルレポート
  - 年度別財務データ表
  - インタラクティブな財務グラフ（6種類）
    - **【事業の実力】**
      - 事業効率（簡易ROIC × CF変換率、総合評価付き）
      - キャッシュフロー（FCF＝営業CF＋投資CF）
    - **【株主価値と市場評価】**
      - 株主価値の蓄積（EPS × BPS × ROE、総合評価付き）
      - 配当政策と市場評価（配当性向 × ROE × PBR、総合評価付き）
      - 市場評価（PER × ROE × PBR、総合評価付き）
      - 株価とEPSの乖離
  - 総合評価：CAGRに基づくパターン評価、評価コメントは評価に応じて色付き表示
- **CSVレポート**：HTMLレポート生成時に自動出力（純粋なデータのみ）
  - ヘッダー情報（銘柄コード、会社名、セクター名、市場名、分析日）
  - 年度別財務データ（19列：基本財務指標 + グラフ用計算指標）
    - 基本財務指標：年度終了日、売上高、営業利益、当期純利益、純資産、営業CF、投資CF、FCF、ROE、EPS、BPS、PER、PBR、配当性向
    - グラフ用計算指標：簡易ROIC、CF変換率、株価、株価指数、EPS指数

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
jquants-analyzer/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   └── client.py          # J-QUANTS APIクライアント
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── individual.py      # 個別分析
│   └── utils/
│       ├── __init__.py
│       ├── financial_data.py   # 財務データ処理・指標計算
│       └── cache.py           # キャッシュ管理
├── scripts/
│   ├── notebook_analysis.py  # 個別分析Notebook起動ラッパー
│   ├── watchlist_manager.py   # ウォッチリスト管理スクリプト
│   ├── test_connection.py     # API接続テスト
│   ├── test_api_data.py       # APIデータテスト
│   └── test_analysis_years.py # 分析年数テスト
├── notebooks/
│   └── individual_analysis_template.ipynb  # 個別分析テンプレート
├── templates/
│   └── report_template.html   # HTMLレポートテンプレート
├── static/
│   └── css/
│       └── report.css         # レポート用CSS
├── reports/                    # 生成されたHTMLレポートとCSVレポート保存先
├── cache/                      # APIレスポンスキャッシュ
├── watchlist.json              # ウォッチリスト（JSON形式）
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

## 注意事項

- 投資判断は自己責任で行ってください
- このツールは「適格性判断」のための分析ツールです
- 結果が良い = 投資推奨ではありません
- 必ず複数の情報源と併用してください

## レート制限対策

- **自動リトライ**：レート制限エラー時に自動的に待機してリトライ
- **エラーハンドリング**：レート制限に達しても取得できた分のデータで分析を継続
- **キャッシュ活用**：既に取得済みのデータはキャッシュから読み込み（APIコール削減）

## ライセンス

このプロジェクトは個人利用を目的としています。

