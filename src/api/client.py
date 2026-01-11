"""
J-QUANTS API クライアント

APIキー認証とデータ取得機能を提供します。
データ取得期間を設定可能にしています。
"""

import time
from typing import Optional, Dict, List, Any
from datetime import datetime

import requests
from ..config import config


class JQuantsAPIClient:
    """J-QUANTS API クライアントクラス"""

    BASE_URL = "https://api.jquants.com/v2"  # V2に移行
    MAX_RETRIES = 5  # レート制限対応のため増加
    RETRY_DELAY = 2.0  # 秒（レート制限対応のため増加）
    RATE_LIMIT_WAIT = 60  # レート制限時の待機時間（秒）

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        初期化

        Args:
            api_key: APIキー。Noneの場合はconfigから取得
            base_url: APIベースURL。Noneの場合はconfigまたはデフォルト値を使用
        """
        self.api_key = api_key or config.api_key
        
        if not self.api_key:
            raise ValueError(
                "APIキーが設定されていません。"
                "環境変数JQUANTS_API_KEYを設定するか、"
                "コンストラクタでapi_keyを指定してください。"
            )
        
        # ベースURLをconfigから取得、なければデフォルト値
        self.base_url = base_url or config.api_base_url
        
        # APIキーの前後の空白を削除
        self.api_key = self.api_key.strip()

        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": self.api_key
        })

    def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        APIリクエストを実行（リトライ機能付き）

        Args:
            endpoint: エンドポイントパス（例: "/fins/summary"）
            params: クエリパラメータ
            retry_count: 現在のリトライ回数

        Returns:
            APIレスポンスのJSONデータ

        Raises:
            requests.RequestException: リクエストエラー
            ValueError: APIキーが無効な場合
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise ValueError("APIキーが無効です。正しいAPIキーを設定してください。")
            elif response.status_code == 403:
                error_msg = f"認証エラー (403): {response.text}"
                if "Missing Authentication Token" in response.text:
                    error_msg += "\nAPIキーが正しく送信されていない可能性があります。"
                    error_msg += f"\n使用中のベースURL: {self.base_url}"
                    error_msg += f"\nエンドポイント: {endpoint}"
                raise ValueError(error_msg)
            elif response.status_code == 429:
                # レート制限エラー
                if retry_count < self.MAX_RETRIES:
                    # レート制限時は長めに待機（指数バックオフ + 固定待機時間）
                    wait_time = self.RETRY_DELAY * (2 ** retry_count) + self.RATE_LIMIT_WAIT
                    print(f"⚠️  レート制限に達しました。{wait_time:.0f}秒待機してからリトライします...")
                    time.sleep(wait_time)
                    return self._request(endpoint, params, retry_count + 1)
                else:
                    raise requests.RequestException(
                        f"レート制限に達しました。リトライ回数上限に達しました。"
                        f"\nしばらく時間をおいてから再試行してください。"
                        f"\n（無料プランには1日あたりのリクエスト数制限があります）"
                    )
            else:
                raise requests.RequestException(
                    f"APIリクエストエラー: {response.status_code} - {response.text}"
                )
        
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            # 一時的なネットワークエラー
            if retry_count < self.MAX_RETRIES:
                wait_time = self.RETRY_DELAY * (2 ** retry_count)
                time.sleep(wait_time)
                return self._request(endpoint, params, retry_count + 1)
            else:
                raise requests.RequestException(
                    f"ネットワークエラー: {str(e)}"
                )

    def _get_all_pages(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        ページネーション対応のデータ取得

        Args:
            endpoint: エンドポイントパス
            params: クエリパラメータ

        Returns:
            全ページのデータを結合したリスト
        """
        all_data = []
        current_params = params.copy() if params else {}
        pagination_key = None

        while True:
            if pagination_key:
                current_params["pagination_key"] = pagination_key
            
            response = self._request(endpoint, current_params)
            
            # レスポンス構造: {"data": [...], "pagination_key": "..."}
            if "data" in response:
                all_data.extend(response["data"])
            
            # ページネーションキーが存在する場合は次のページを取得
            pagination_key = response.get("pagination_key")
            if not pagination_key:
                break

        return all_data

    def get_financial_summary(
        self,
        code: Optional[str] = None,
        date: Optional[str] = None,
        max_years: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        財務情報を取得

        Args:
            code: 銘柄コード（5桁、例: "27800"）。4桁指定も可能
            date: 日付（YYYY-MM-DD または YYYYMMDD）
                  codeまたはdateのいずれかは必須
            max_years: 取得する最大年数（Noneの場合は設定から取得、API側では制限不可）

        Returns:
            財務情報のリスト
        """
        if not code and not date:
            raise ValueError("codeまたはdateのいずれかを指定してください。")

        params = {}
        if code:
            params["code"] = code
        if date:
            params["date"] = date

        # 全データを取得（フィルタリングは後で行う）
        all_data = self._get_all_pages("/fins/summary", params)
        
        # max_yearsが指定されている場合、年度データを制限
        # 注意: API側で年数制限はできないため、取得後にフィルタリング
        # 実際の年数制限は extract_annual_data と calculate_metrics で行う
        
        return all_data

    def get_daily_bars(
        self,
        code: Optional[str] = None,
        date: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        株価四本値データを取得

        Args:
            code: 銘柄コード（5桁、例: "27800"）。4桁指定も可能
            date: 日付（YYYYMMDD または YYYY-MM-DD）
            from_date: 期間指定の開始日
            to_date: 期間指定の終了日
            codeまたはdateのいずれかは必須

        Returns:
            株価データのリスト
        """
        if not code and not date:
            raise ValueError("codeまたはdateのいずれかを指定してください。")

        params = {}
        if code:
            params["code"] = code
        if date:
            params["date"] = date
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        return self._get_all_pages("/equities/bars/daily", params)

    def get_equity_master(
        self,
        code: Optional[str] = None,
        date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        上場銘柄一覧を取得

        Args:
            code: 銘柄コード（5桁、例: "27800"）。4桁指定も可能
            date: 基準日（YYYYMMDD または YYYY-MM-DD）

        Returns:
            銘柄情報のリスト
        """
        params = {}
        if code:
            params["code"] = code
        if date:
            params["date"] = date

        return self._get_all_pages("/equities/master", params)

    def get_price_at_date(
        self,
        code: str,
        date: str,
        use_nearest_trading_day: bool = True
    ) -> Optional[float]:
        """
        指定日付の終値を取得（年度末株価取得用）
        
        指定日が休日の場合は、直前の営業日の終値を取得します。

        Args:
            code: 銘柄コード（5桁、例: "27800"）
            date: 日付（YYYYMMDD または YYYY-MM-DD）
            use_nearest_trading_day: 指定日が休日の場合は直前の営業日を使用（デフォルト: True）

        Returns:
            終値（AdjC）。データが存在しない場合はNone
        """
        # まず指定日付で取得を試みる
        bars = self.get_daily_bars(code=code, date=date)
        
        if bars:
            # 指定日付のデータを取得（通常は1件のみ）
            for bar in bars:
                bar_date = bar.get("Date")
                if bar_date == date or bar_date == date.replace("-", ""):
                    return bar.get("AdjC") or bar.get("C")
        
        # 指定日が休日の場合、直前の営業日を探す
        if use_nearest_trading_day:
            # 日付をパース
            if "-" in date:
                year, month, day = date.split("-")
            else:
                year = date[:4]
                month = date[4:6]
                day = date[6:8]
            
            # 年度末の前後数日間のデータを取得（最大10営業日前まで）
            from datetime import datetime, timedelta
            try:
                target_date = datetime(int(year), int(month), int(day))
                # 年度末の前後1週間のデータを取得
                start_date = (target_date - timedelta(days=10)).strftime("%Y-%m-%d")
                end_date = target_date.strftime("%Y-%m-%d")
                
                bars = self.get_daily_bars(
                    code=code,
                    from_date=start_date,
                    to_date=end_date
                )
                
                if bars:
                    # 日付でソート（新しい順）
                    bars.sort(key=lambda x: x.get("Date", ""), reverse=True)
                    # 最初のデータ（最も近い営業日）の終値を返す
                    for bar in bars:
                        price = bar.get("AdjC") or bar.get("C")
                        if price is not None:
                            return price
            except (ValueError, TypeError):
                pass
        
        return None

