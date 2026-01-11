# EDINET検索ロジック

## 概要

EDINET APIを使用して、有価証券報告書と半期報告書を検索・取得するロジックの説明です。

## 実行環境

このEDINET検索ロジックは、Streamlitアプリケーション（`app.py`）から呼び出されます。
- **エントリーポイント**: `app.py`（Streamlitアプリケーション）
- **分析実行**: `src/ui/analysis_handler.py`の`run_analysis()`関数
- **分析ロジック**: `src/analysis/individual.py`の`IndividualAnalyzer`クラス
- **EDINET検索**: `src/analysis/individual.py`の`fetch_edinet_reports()`メソッド
- **EDINET APIクライアント**: `src/api/edinet_client.py`の`EdinetAPIClient`クラス

## 検索対象の書類

### 対象書類種別

1. **有価証券報告書**
   - `docTypeCode`の先頭3桁が`"030"`
   - 書類名（`docDescription`）に「有価証券報告書」が含まれる

2. **半期報告書**
   - `docTypeCode`の先頭3桁が`"050"`
   - 書類名（`docDescription`）に「半期報告書」が含まれる

### 法令コード（ordinanceCode）

- `"010"`: 金融商品取引法（内国会社）
- `"020"`: 金融商品取引法（外国会社等）

上記のいずれかに該当する書類のみを対象とします。

### 除外条件

- **訂正・補正報告書**: `docDescription`に「訂正」または「補正」が含まれる書類は除外
- **証券コードなし**: `secCode`が`None`の書類は除外（投資信託など）

## 検索期間の決定

### 1. J-QUANTSデータがある場合（最適化検索）

J-QUANTS APIから取得した年度終了日（`CurFYEn`）と開示日（`DiscDate`）を使用して、検索範囲を最適化します。

#### 年度の計算

```python
# 年度終了日から年度を計算
period_date = datetime.strptime(fy_end, "%Y-%m-%d")
if period_date.month == 3:  # 3月末が年度終了日の場合
    fiscal_year = period_date.year - 1  # その年度は前年
else:
    fiscal_year = period_date.year
```

#### 検索範囲の決定

- **検索開始日**: `max(開示日 - 7日, 年度終了日)`
  - 開示日の7日前から開始（有報は開示日の前後で提出されることが多い）
  - ただし、年度終了日より前の場合は年度終了日から開始

- **検索終了日**: `min(年度終了日 + 90日, 現在日時)`
  - 年度終了日から3ヶ月以内
  - 現在日時を超えない範囲

- **検索日数**: 検索開始日から終了日まで、1日ごとに検索

#### 例

```
年度終了日: 2025-03-31
開示日: 2025-05-08
検索開始日: max(2025-05-01, 2025-03-31) = 2025-05-01
検索終了日: min(2025-06-30, 現在日時) = 2025-06-30
検索期間: 2025-05-01 ～ 2025-06-30（約60日間）
```

### 2. J-QUANTSデータがない場合（フォールバック検索）

年度終了後の提出期間を推定して検索します。

- **検索期間**: 年度終了後の4-6月
- **検索日**: 各月の1日、15日、月末日のみ
  - 4月: 1日、15日、30日
  - 5月: 1日、15日、31日
  - 6月: 1日、15日、30日

#### 例

```
年度: 2023年度（2024-03-31終了）
検索日: 
  - 2024-04-01, 2024-04-15, 2024-04-30
  - 2024-05-01, 2024-05-15, 2024-05-31
  - 2024-06-01, 2024-06-15, 2024-06-30
合計: 9日間
```

## フィルタリング条件

### 1. 書類種別の判定

```python
is_target_report = False
if ordinance_code in ["010", "020"]:
    # docTypeCodeで判定
    if doc_type and len(doc_type) >= 3:
        if doc_type[:3] == "030":  # 有価証券報告書
            is_target_report = True
        elif doc_type[:3] == "050":  # 半期報告書
            is_target_report = True
    
    # docDescriptionで判定（フォールバック）
    if doc_description:
        if "有価証券報告書" in doc_description:
            is_target_report = True
        elif "半期報告書" in doc_description:
            is_target_report = True
```

### 2. 訂正・補正報告書の除外

```python
if doc_description and ("訂正" in doc_description or "補正" in doc_description):
    continue  # 除外
```

### 3. 証券コードの確認

```python
if sec_code is None:
    continue  # 除外（投資信託など）
```

## 銘柄コードマッチング

### マッチング条件

検索対象の銘柄コード（`code`）と、EDINET APIのレスポンスの`secCode`を比較します。

#### 正規化

```python
code_4digit = code[:4]  # 4桁コード
code_5digit = code.zfill(5)  # 5桁コード
sec_code_str = str(sec_code).strip()
sec_code_normalized = sec_code_str.zfill(5)  # 5桁に正規化
code_normalized = code.zfill(5)  # 5桁に正規化
```

#### マッチング判定

以下のいずれかの条件で一致と判定します：

1. `sec_code_str == code_4digit`（完全一致、4桁）
2. `sec_code_str == code_5digit`（完全一致、5桁）
3. `sec_code_str == code`（完全一致、そのまま）
4. `sec_code_normalized == code_normalized`（正規化後の完全一致）
5. `sec_code_str.startswith(code_4digit)`（先頭一致）
6. `sec_code_normalized[:4] == code_normalized[:4]`（先頭4桁一致）
7. `len(sec_code_str) == 5 and sec_code_str[:4] == code_4digit`（5桁で先頭4桁一致）

#### 例

```
code = "7203"
secCode = "72030"  → 一致（先頭4桁が一致）
secCode = "7203"   → 一致（完全一致）
secCode = "07203"  → 一致（正規化後一致）
```

## 年度の判定

### periodEndから年度を抽出

```python
period_date = datetime.strptime(period_end[:10], "%Y-%m-%d")
if period_date.month == 3:  # 3月末が年度終了日の場合
    doc_year = period_date.year - 1  # その年度は前年
else:
    doc_year = period_date.year
```

### 年度の一致確認

- `periodEnd`が存在する場合: 検索対象年度と一致するか確認
- `periodEnd`が`None`の場合: 年度チェックをスキップし、`secCode`でマッチングできれば取得

### 年度の許容範囲

検索対象年度に含まれていない場合でも、±1年以内の場合は取得します。

```python
if year not in years:
    year_diff = min([abs(year - y) for y in years])
    if year_diff <= 1:  # ±1年以内
        # 最も近い年度にマッピング
        closest_year = min(years, key=lambda y: abs(year - y))
        year = closest_year
```

## 検索フロー

### 呼び出しフロー

```
Streamlitアプリ（app.py）
  ↓
分析ハンドラー（src/ui/analysis_handler.py::run_analysis）
  ↓
個別分析（src/analysis/individual.py::analyze_stock）
  ↓
EDINET検索（src/analysis/individual.py::fetch_edinet_reports）
  ↓
EDINET APIクライアント（src/api/edinet_client.py::EdinetAPIClient）
```

### 1. 年度ごとの検索

```python
for year in years:  # 年度のリスト（降順、最新年度が最初）
    # 検索期間を決定
    search_dates = determine_search_dates(year, jquants_data)
    
    # 各日付でEDINET APIを呼び出し
    for search_date in search_dates:
        documents = edinet_api.get_documents(date=search_date)
        
        # フィルタリング
        filtered = filter_documents(documents, code, year)
        
        if filtered:
            all_documents.extend(filtered)
```

### 2. 最新年度優先

`src/analysis/individual.py`の`fetch_edinet_reports()`メソッドでは、最新年度から順に検索し、見つかったら次の年度は検索しません。

```python
for year in years:  # 降順（最新年度が最初）
    reports = edinet_client.fetch_reports(code, [year])
    if reports:
        all_reports.update(reports)
        break  # 最新年度が見つかったら終了
```

**呼び出し元**: Streamlitアプリケーション（`app.py`）→ `src/ui/analysis_handler.py`の`run_analysis()` → `src/analysis/individual.py`の`analyze_stock()` → `fetch_edinet_reports()`

## 取得結果

### 返却される情報

```python
{
    year: {
        "docID": "S100XXXX",
        "submitDate": "2025-05-08",
        "pdf_path": "/path/to/report.pdf",
        "xbrl_path": "/path/to/report_xbrl/",
        "docType": "有価証券報告書" or "半期報告書",
        "docTypeCode": "030000" or "050000",
        "docDescription": "有価証券報告書" or "半期報告書",
        "management_policy": "LLM要約テキスト"
    }
}
```

### Streamlit UIでの表示

取得したEDINETデータは、Streamlitアプリケーション（`app.py`）のUIで以下のように表示されます：

- **事業概要セクション**: `src/ui/components.py`の`_display_business_overview()`関数で表示
  - 最新年度の有価証券報告書から抽出した事業概要・経営方針・課題のLLM要約を表示
  - マークダウン記法対応（見出し、箇条書き、強調表示）
  - 年度と提出日を表示
  - 有報PDFダウンロードボタンを表示（`src/ui/components.py`の`display_analysis_results()`関数内）

- **PDF保存先**: `reports/{code}_edinet/`ディレクトリ
- **XBRL保存先**: `reports/{code}_edinet/{docID}_xbrl/`ディレクトリ（展開済み）
- **LLM要約キャッシュ**: `cache/edinet/summaries/`ディレクトリ

## XBRL解析機能

### XBRL解析の処理フロー

1. **XBRLファイルの取得**:
   - EDINET APIからXBRLファイル（ZIP形式）をダウンロード
   - ZIPファイルを展開して`{docID}_xbrl/`ディレクトリに保存

2. **XBRL解析**:
   - `src/analysis/xbrl_parser.py`の`XBRLParser`クラスを使用
   - インラインXBRL（HTML形式）とXBRLインスタンス文書（XML形式）の両方に対応
   - `beautifulsoup4`を使用してHTMLからセクションを抽出
   - `xml.etree.ElementTree`を使用してXMLからテキストブロックを抽出

3. **セクション抽出**（`COMMON_SECTIONS`で定義）:
   XBRL解析では、有価証券報告書から以下の6つのセクションを抽出します：
   
   - **A: 事業の内容** (`DescriptionOfBusinessTextBlock`)
     - 会社の事業内容、主要製品・サービス、事業の特徴など
   
   - **B: 経営方針、経営環境及び対処すべき課題等** (`BusinessPolicyTextBlock`)
     - 経営方針、経営環境の変化、対処すべき課題、事業戦略など
   
   - **C: 事業等のリスク** (`BusinessRisksTextBlock`)
     - 事業リスク、財務リスク、経営リスク、リスク対策など
   
   - **D: 経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析** (`ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock`)
     - 経営成績の分析、財政状態の分析、キャッシュ・フロー状況の分析など
   
   - **E: 重要な契約等** (`ImportantContractsTextBlock`)
     - 重要な契約、取引先との関係、関連会社との取引など
   
   - **F: 設備投資等の概要** (`OverviewOfCapitalInvestmentTextBlock`)
     - 設備投資計画、研究開発投資、M&A計画など
   
   これらのセクションは、A→B→C→D→E→Fの順で抽出され、結合されてLLMに渡されます。

4. **LLM要約**:
   - 抽出したセクションを結合してテキストを作成
   - `src/analysis/llm_summarizer.py`の`LLMSummarizer`クラスを使用
   - Ollama（`gemma3:1b`モデル、デフォルト）で要約生成。環境変数`LLM_MODEL`で他のモデルに切り替え可能
   - マークダウン記法で出力

### PDFとXBRLの使い分け

- **PDF**: ダウンロード用のみ（ユーザーが手動で確認するためのファイル）
- **XBRL**: 要約用（LLM要約のためのテキスト抽出に使用）

XBRLは構造化されたデータ形式のため、PDFよりも正確にテキストを抽出できます。そのため、LLM要約にはXBRLを使用し、PDFはユーザーが手動で確認するためのダウンロード用として保存されます。

## エラーハンドリング

### HTTPステータスコード

- **200**: 正常処理
- **404**: 該当日付に書類なし（スキップ）
- **その他**: エラーログを出力してスキップ

### エラーレスポンス

```json
{
    "statusCode": 400,
    "message": "エラーメッセージ"
}
```

この場合もエラーログを出力してスキップします。

## 最適化のポイント

1. **J-QUANTSデータの活用**: 開示日と年度終了日を使用して検索範囲を最適化
2. **最新年度優先**: 最新年度から順に検索し、見つかったら終了
3. **検索日数の削減**: フォールバック検索では主要日のみを検索
4. **重複除去**: `docID`で重複を除去

## 注意事項

1. **未来の日付**: 開示日が未来の場合は除外
2. **訂正報告書**: 訂正・補正報告書は除外（メイン報告書のみ取得）
3. **証券コード**: `secCode`が`None`の書類は除外（上場企業のみ対象）
4. **年度の判定**: 3月末が年度終了日の場合、その年度は前年として扱う

