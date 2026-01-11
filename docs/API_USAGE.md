# API使用ガイド

このドキュメントでは、Educeで使用している各APIの使用方法、チェックポイント、エラーハンドリングについて説明します。

## 目次

- [J-QUANTS API](#j-quants-api)
- [EDINET API](#edinet-api)

---

## J-QUANTS API

### 基本情報

- **ベースURL**: `https://api.jquants.com/v2`
- **認証方式**: APIキー認証（`x-api-key`ヘッダー）
- **APIキー取得**: [J-QUANTS Dashboard](https://jpx-jquants.com/)
- **環境変数**: `JQUANTS_API_KEY`

### 認証方法

```python
# ヘッダーにAPIキーを設定
headers = {
    "x-api-key": "your_api_key_here"
}
```

### 使用エンドポイント

#### 1. `/fins/summary` - 財務情報取得

**用途**: 財務サマリー情報（売上高、営業利益、当期純利益、純資産、営業CF、投資CF、EPS、BPS等）を取得

**パラメータ**:
- `code` (string, オプション): 銘柄コード（4桁または5桁、例: "6501"）
- `date` (string, オプション): 日付（YYYY-MM-DD または YYYYMMDD形式）
- `pagination_key` (string, オプション): ページネーション用キー

**注意点**:
- `code`または`date`のいずれかは必須
- ページネーション対応（`pagination_key`を使用）
- API側で年数制限はできないため、取得後にフィルタリングが必要

**リクエスト例**:
```python
# 銘柄コードで取得
params = {"code": "6501"}
response = client._request("/fins/summary", params)

# 日付で取得
params = {"date": "2024-01-01"}
response = client._request("/fins/summary", params)
```

**レスポンス構造**:
```json
{
  "data": [
    {
      "CurPerType": "FY",  // "FY"=年度、"1Q"、"2Q"、"3Q"、"4Q"=四半期
      "CurFYEn": "20240331",  // 年度終了日（YYYYMMDD形式）
      "DiscDate": "20240515",  // 開示日
      "Sales": 1000000000,  // 売上高（円単位）
      "OP": 100000000,  // 営業利益（円単位）
      "NP": 80000000,  // 当期純利益（円単位）
      "Eq": 500000000,  // 純資産（円単位）
      "CFO": 120000000,  // 営業CF（円単位）
      "CFI": -50000000,  // 投資CF（円単位）
      "EPS": 50.5,  // 1株当たり当期純利益（円）
      "BPS": 300.0  // 1株当たり純資産（円）
    }
  ],
  "pagination_key": "next_page_key"  // 次のページがある場合
}
```

#### 2. `/equities/bars/daily` - 日次株価データ取得

**用途**: 株価四本値データ（始値、高値、安値、終値、調整後終値）を取得

**パラメータ**:
- `code` (string, オプション): 銘柄コード（4桁または5桁）
- `date` (string, オプション): 日付（YYYYMMDD または YYYY-MM-DD形式）
- `from` (string, オプション): 期間指定の開始日
- `to` (string, オプション): 期間指定の終了日
- `pagination_key` (string, オプション): ページネーション用キー

**注意点**:
- `code`または`date`のいずれかは必須
- ページネーション対応

**リクエスト例**:
```python
# 特定日の株価を取得
params = {"code": "6501", "date": "2024-03-31"}
response = client._request("/equities/bars/daily", params)

# 期間指定で取得
params = {"code": "6501", "from": "2024-03-25", "to": "2024-03-31"}
response = client._request("/equities/bars/daily", params)
```

**レスポンス構造**:
```json
{
  "data": [
    {
      "Date": "2024-03-31",  // 日付
      "Code": "6501",  // 銘柄コード
      "Open": 1000.0,  // 始値
      "High": 1050.0,  // 高値
      "Low": 980.0,  // 安値
      "Close": 1020.0,  // 終値
      "AdjC": 1020.0  // 調整後終値（株式分割等を考慮）
    }
  ],
  "pagination_key": "next_page_key"
}
```

#### 3. `/equities/master` - 銘柄マスタ情報取得

**用途**: 上場銘柄一覧（銘柄コード、銘柄名、業種、市場区分等）を取得

**パラメータ**:
- `code` (string, オプション): 銘柄コード（4桁または5桁）
- `date` (string, オプション): 基準日（YYYYMMDD または YYYY-MM-DD形式）
- `pagination_key` (string, オプション): ページネーション用キー

**リクエスト例**:
```python
# 特定銘柄の情報を取得
params = {"code": "6501"}
response = client._request("/equities/master", params)
```

**レスポンス構造**:
```json
{
  "data": [
    {
      "Code": "6501",  // 銘柄コード
      "CompanyName": "日経平均",  // 会社名
      "Sector33Code": "5250",  // 33業種コード
      "Sector33CodeName": "情報・通信業",  // 33業種名
      "Sector17Code": "50",  // 17業種コード
      "Sector17CodeName": "情報・通信業",  // 17業種名
      "MarketCode": "1",  // 市場コード
      "MarketCodeName": "東証プライム"  // 市場名
    }
  ],
  "pagination_key": "next_page_key"
}
```

### エラーハンドリング

#### HTTPステータスコード

| ステータスコード | 意味 | 処理方法 |
|----------------|------|---------|
| 200 | 成功 | 正常処理 |
| 401 | 認証エラー | APIキーが無効。正しいAPIキーを設定 |
| 403 | 認証エラー | APIキーが正しく送信されていない可能性 |
| 429 | レート制限 | 自動的に待機してリトライ（最大5回） |
| その他 | エラー | エラーメッセージを表示 |

#### レート制限対策

- **自動リトライ**: 429エラー時に自動的に待機してリトライ
- **待機時間**: 指数バックオフ + 固定待機時間（60秒）
  - 1回目: 2秒 + 60秒 = 62秒
  - 2回目: 4秒 + 60秒 = 64秒
  - 3回目: 8秒 + 60秒 = 68秒
  - ...
- **最大リトライ回数**: 5回
- **無料プラン制限**: 1日あたりのリクエスト数制限あり

#### ネットワークエラー対策

- **タイムアウト**: 30秒
- **自動リトライ**: タイムアウト・接続エラー時に自動的にリトライ（指数バックオフ）
- **最大リトライ回数**: 5回

### ページネーション

J-QUANTS APIはページネーションに対応しています。`_get_all_pages()`メソッドを使用すると、全ページのデータを自動的に取得します。

```python
# ページネーション対応のデータ取得
all_data = client._get_all_pages("/fins/summary", {"code": "6501"})
```

**処理フロー**:
1. 最初のリクエストを送信
2. レスポンスから`pagination_key`を取得
3. `pagination_key`が存在する場合、次のページを取得
4. `pagination_key`が存在しなくなるまで繰り返し

### チェックポイント

1. **APIキーの設定**: 環境変数`JQUANTS_API_KEY`が正しく設定されているか
2. **ベースURL**: デフォルトは`https://api.jquants.com/v2`（V2 API）
3. **パラメータ形式**: 日付は`YYYY-MM-DD`または`YYYYMMDD`形式
4. **銘柄コード**: 4桁または5桁で指定可能（例: "6501"または"06501"）
5. **データ単位**: APIから取得するデータは**円単位**（百万円単位ではない）
6. **ページネーション**: 大量データ取得時は`_get_all_pages()`を使用
7. **レート制限**: 無料プランには1日あたりのリクエスト数制限あり

---

## EDINET API

### 基本情報

- **ベースURL**: `https://api.edinet-fsa.go.jp/api/v2`
- **認証方式**: APIキー認証（`Ocp-Apim-Subscription-Key`ヘッダー）
- **APIキー取得**: [EDINET API](https://disclosure2.edinet-fsa.go.jp/)
- **環境変数**: `EDINET_API_KEY`

### 認証方法

```python
# ヘッダーにAPIキーを設定（Azure API Management形式）
headers = {
    "Ocp-Apim-Subscription-Key": "your_api_key_here"
}
```

### 使用エンドポイント

#### 1. `/documents.json` - 書類一覧取得

**用途**: 指定日付に提出された書類の一覧を取得

**パラメータ**:
- `date` (string, 必須): 提出日（YYYY-MM-DD形式）
- `type` (string, 必須): 取得情報の種類
  - `"1"`: メタデータのみ
  - `"2"`: 提出書類一覧+メタデータ（推奨）
- `docTypeCode` (string, オプション): 書類種別コード（例: "030"=有価証券報告書）

**注意点**:
- `docTypeCode`でフィルタリングすると、上場企業の有価証券報告書が含まれない可能性があるため、一旦フィルタリングを外して全書類を取得し、後からフィルタリングすることを推奨

**リクエスト例**:
```python
# 書類一覧を取得
params = {
    "date": "2024-06-25",
    "type": "2"  # 書類一覧取得
}
response = client._request("/documents.json", params)
```

**レスポンス構造**:
```json
{
  "metadata": {
    "resultset": {
      "count": 100
    }
  },
  "results": [
    {
      "docID": "S100XXXX",  // 書類管理番号
      "edinetCode": "E01234",  // EDINETコード
      "secCode": "7203",  // 証券コード（銘柄コード、4桁または5桁）
      "filerName": "トヨタ自動車株式会社",  // 提出者名
      "fundCode": null,  // ファンドコード（投資信託等の場合）
      "ordinanceCode": "010",  // 法令コード（010=金融商品取引法（内国会社））
      "formCode": "030000",  // 様式コード
      "docTypeCode": "030000",  // 書類種別コード（先頭3桁が030=有価証券報告書）
      "periodStart": "2023-04-01",  // 期間開始日
      "periodEnd": "2024-03-31",  // 期間終了日（年度終了日）
      "submitDateTime": "2024-06-25 16:30:00",  // 提出日時
      "docDescription": "有価証券報告書",  // 書類名
      "issuerEdinetCode": null,  // 発行者EDINETコード
      "subjectEdinetCode": null,  // 対象EDINETコード
      "subsidiaryEdinetCode": null,  // 子会社EDINETコード
      "currentReportReason": null,  // 臨時報告書の理由
      "parentDocID": null,  // 親書類ID
      "opeDateTime": null,  // 操作日時
      "withdrawalStatus": "0",  // 取下げステータス（0=取下げなし）
      "docInfoEditStatus": "0",  // 書類情報編集ステータス
      "disclosureStatus": "0",  // 開示ステータス
      "xbrlFlag": "1",  // XBRLフラグ（1=XBRLあり）
      "pdfFlag": "1",  // PDFフラグ（1=PDFあり）
      "attachDocFlag": "1",  // 添付書類フラグ
      "englishDocFlag": "0"  // 英文書類フラグ
    }
  ]
}
```

#### 2. `/documents/{docID}` - 書類ダウンロード

**用途**: 指定された書類IDの書類（PDF/XBRL）をダウンロード

**パラメータ**:
- `docID` (string, 必須): 書類管理番号（URLパスに含める）
- `type` (int, 必須): 書類種別
  - `1`: XBRL（ZIP形式）
  - `2`: PDF

**リクエスト例**:
```python
# PDFをダウンロード
params = {"type": 2}
response = client._request(f"/documents/{doc_id}", params)

# XBRLをダウンロード
params = {"type": 1}
response = client._request(f"/documents/{doc_id}", params)
```

**レスポンス**:
- PDF: バイナリデータ（`application/pdf`）
- XBRL: ZIPファイル（`application/zip`）

**XBRLファイルの展開**:
- XBRLはZIP形式でダウンロードされるため、展開が必要です
- 展開後は`{docID}_xbrl/`ディレクトリに保存されます
- 展開されたXBRLファイルは以下の構造になります：
  - `PublicDoc/`: インラインXBRL（HTML形式）が含まれる
  - `XBRL/`: XBRLインスタンス文書（XML形式）が含まれる
    - `AuditDoc/`: 監査報告書関連
    - `PublicDoc/`: 公開文書関連

### 有価証券報告書の検索ロジック

EDINET APIでは、有価証券報告書を検索する際に以下のロジックを使用しています。

#### 検索期間の決定

有価証券報告書は通常、年度終了後3ヶ月以内（4-6月）に提出されます。検索効率を考慮し、以下の期間で検索します：

- **4-6月**: 提出が集中するため、毎日検索
- **7-9月**: 月初日、15日、月末日のみ検索

#### 書類のフィルタリング

取得した書類から、有価証券報告書のみを抽出します：

1. **法令コード（ordinanceCode）**: `"010"`（内国会社）または`"020"`（外国会社等）
2. **書類種別コード（docTypeCode）**: 先頭3桁が`"030"`（有価証券報告書）
3. **証券コード（secCode）**: 上場企業の有価証券報告書のみを対象（`secCode`が存在する）
4. **年度の一致**: `periodEnd`から年度を抽出し、検索対象年度と一致するか確認

#### 年度の抽出方法

`periodEnd`（期間終了日）から年度を抽出します：

```python
# YYYY-MM-DD形式から年度を抽出
period_date = datetime.strptime(period_end[:10], "%Y-%m-%d")
# 3月末が年度終了日の場合、その年度は前年
if period_date.month == 3:
    doc_year = period_date.year - 1
else:
    doc_year = period_date.year
```

### エラーハンドリング

#### HTTPステータスコード

| ステータスコード | 意味 | 処理方法 |
|----------------|------|---------|
| 200 | 成功 | 正常処理 |
| 404 | 書類が見つからない | エラーにしない（有報が存在しない場合があるため） |
| 429 | レート制限 | 自動的に待機してリトライ（最大3回） |
| その他 | エラー | エラーメッセージを表示 |

#### レート制限対策

- **自動リトライ**: 429エラー時に自動的に待機してリトライ
- **待機時間**: 指数バックオフ + 固定待機時間（60秒）
  - 1回目: 2秒 + 60秒 = 62秒
  - 2回目: 4秒 + 60秒 = 64秒
  - 3回目: 8秒 + 60秒 = 68秒
- **最大リトライ回数**: 3回

#### ネットワークエラー対策

- **タイムアウト**: 60秒
- **自動リトライ**: タイムアウト・接続エラー時に自動的にリトライ（指数バックオフ）
- **最大リトライ回数**: 3回

### チェックポイント

1. **APIキーの設定**: 環境変数`EDINET_API_KEY`が正しく設定されているか
2. **認証ヘッダー**: `Ocp-Apim-Subscription-Key`を使用（Azure API Management形式）
3. **検索期間**: 有価証券報告書は年度終了後3ヶ月以内（4-6月）に提出される
4. **書類のフィルタリング**: 
   - `ordinanceCode`が`"010"`または`"020"`
   - `docTypeCode`の先頭3桁が`"030"`
   - `secCode`が存在する（上場企業のみ）
5. **年度の抽出**: `periodEnd`から年度を抽出（3月末終了の場合は前年）
6. **銘柄コードのマッチング**: `secCode`と検索コードを比較（4桁・5桁の両形式に対応）
7. **404エラー**: 有報が存在しない場合は404が返されるが、エラーにしない
8. **キャッシュ**: ダウンロードしたPDF/XBRLは`reports/{code}_edinet/`に保存
9. **XBRLの展開**: XBRLはZIP形式でダウンロードされ、自動的に展開される
10. **PDFとXBRLの使い分け**: PDFはダウンロード用のみ、要約にはXBRLを使用

### 書類種別コード（docTypeCode）の説明

| 先頭3桁 | 書類種別 |
|--------|---------|
| 030 | 有価証券報告書 |
| 040 | 四半期報告書 |
| 050 | 半期報告書 |
| 070 | 臨時報告書 |

### 法令コード（ordinanceCode）の説明

| コード | 法令 |
|-------|------|
| 010 | 金融商品取引法（内国会社） |
| 020 | 金融商品取引法（外国会社等） |
| 030 | 金融商品取引法（特定有価証券） |

---

## 共通のチェックポイント

### 環境変数の設定

```bash
# .envファイルに設定
JQUANTS_API_KEY=your_jquants_api_key_here
EDINET_API_KEY=your_edinet_api_key_here
```

### エラーログの確認

エラーが発生した場合、ログを確認してください：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### キャッシュの活用

APIレスポンスは自動的にキャッシュされます。最新データが必要な場合は、キャッシュをクリアしてください。

### レート制限への対応

- 無料プランには1日あたりのリクエスト数制限があります
- レート制限に達した場合は、自動的に待機してリトライします
- 大量のデータ取得時は、適切な間隔を空けてリクエストを送信してください

---

## 参考リンク

- [J-QUANTS API ドキュメント](https://jpx-jquants.com/)
- [EDINET API ドキュメント](https://disclosure2.edinet-fsa.go.jp/)
- [プロジェクトのアーキテクチャ](ARCHITECTURE.md)
- [データ処理フロー](DATA_PROCESSING.md)

