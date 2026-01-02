# J-QUANTS API 投資判断分析ツール

J-QUANTS APIを使用した投資判断分析ツールです。FCFを最重視し、堅実な投資判断をサポートします。

## 機能概要

### パターンA：スクリーニング
- 全市場からFCF 3年連続プラスの銘柄をスクリーニング
- 業種フィルタ機能（33業種分類から選択可能）
- サマリービュー表示（ROE、FCF、EPS、PER、PBR等）
- 各指標でのソート機能

### パターンB：個別詳細分析
- 特定銘柄の詳細分析（複数銘柄対応）
- 最大10年分の財務データと各種指標を表示（利用可能なデータを最大限使用）
- **レポート形式**：数値表
- **HTMLレポート生成**：プレゼンテーション品質のビジュアルレポート
  - 年度別財務データ表
  - インタラクティブな財務グラフ（6種類）
    - FCF推移（営業利益 vs 営業CF）
    - ROE/EPS/BPS推移（総合評価付き）
    - PER/PBR/ROE推移（総合評価付き）
    - 売上高推移
    - 株価 vs EPS指数化比較
    - PER推移 vs EPS年次成長率
  - 総合評価（ROE/EPS/BPS推移、PER/PBR/ROE推移のグラフ下に表示）
    - CAGRに基づく8パターン評価
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

### パターンA：スクリーニング

```bash
python3 scripts/screening.py

# 業種リスト確認
python3 scripts/screening.py --list

# 業種コード指定
python3 scripts/screening.py 5050

# 表示20件（上限） → 分析25件（20 + 5）
python3 scripts/screening.py 3600 --count 20

# ランダム選択を無効化（銘柄コード順で選択）
python3 scripts/screening.py --no-random
```

全市場からFCF 3年連続プラスの銘柄をスクリーニングし、結果を表示します。

**デフォルト設定：**
- **ランダム選択**：有効（銘柄をランダムに選択して分析）
- **早期終了**：有効（合格銘柄が表示数に達したら早期終了してソート）
- **表示数**：10件（最大20件）
- **分析数**：表示数 + 5件（最大50件）

スクリプト内で業種フィルタを設定できます（デフォルトは全業種）。

### パターンB：個別詳細分析

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
    - FCF推移（営業利益 vs 営業CF）
    - ROE/EPS/BPS推移（総合評価付き：CAGRに基づく8パターン評価）
    - PER/PBR/ROE推移（総合評価付き：CAGRに基づく8パターン評価）
    - 売上高推移
    - 株価 vs EPS指数化比較（一番古い年を基準として指数化）
    - PER推移 vs EPS年次成長率（期待と実績の比較）
  - 総合評価：CAGRに基づく8パターン評価、評価コメントは評価に応じて色付き表示

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
│   │   ├── screening.py       # パターンA：スクリーニング
│   │   └── individual.py      # パターンB：個別分析
│   └── utils/
│       ├── __init__.py
│       ├── financial_data.py   # 財務データ処理・指標計算
│       └── cache.py           # キャッシュ管理
├── scripts/
│   ├── screening.py           # スクリーニング実行スクリプト
│   ├── notebook_analysis.py  # 個別分析Notebook起動ラッパー
│   └── watchlist_manager.py   # ウォッチリスト管理スクリプト
├── notebooks/
│   └── individual_analysis_template.ipynb  # 個別分析テンプレート
├── templates/
│   └── report_template.html   # HTMLレポートテンプレート
├── static/
│   └── css/
│       └── report.css         # レポート用CSS
├── reports/                    # 生成されたHTMLレポート保存先
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

## 最近の更新

- **PER/PBR/ROE推移のパターンマッピング更新**（2025-01-02）
  - パターン名、評価、評価コメントを更新
  - 評価コメントを評価に応じて色付きで表示（ROE/EPS/BPS推移と同様）
- **四半期別機能の削除**（2025-01-02）
  - 四半期別財務データの表を削除
  - 四半期別グラフ（財務グラフ（トレンド分析））を削除
  - 年度別データのみに統一
- **HTMLレポートの改善**：
  - セクションタイトルとグラフタイトルの分離表示
  - グラフごとのセクション区分け（白背景ボックス）
  - 総合評価のレイアウト改善（CAGR左側、パターンマッピング右側の白背景ボックス）
  - ページ分割の廃止（連続表示）
  - セクションタイトル・グラフタイトル・グラフの間隔を最適化
- **総合評価機能**：ROE/EPS/BPS推移とPER/PBR/ROE推移のグラフ下にCAGRに基づく8パターン評価を表示
- **株価 vs EPS指数化比較**：一番古い年を基準（100）として指数化
- **PER推移 vs EPS年次成長率**：期待（PER）と実績（EPS成長率）の比較グラフを追加
- **未来の年度データ除外**：現在日付より未来の年度データを自動除外
- **分析年数の拡張**：最大10年分のデータを分析可能（利用可能なデータを最大限使用）

## ライセンス

このプロジェクトは個人利用を目的としています。

