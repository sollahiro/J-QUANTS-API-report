"""
パターンA：スクリーニング分析モジュール
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from ..api.client import JQuantsAPIClient
from ..utils.financial_data import extract_annual_data, check_screening_criteria
from ..analysis.calculator import calculate_metrics_flexible
from ..utils.cache import CacheManager
from ..config import config


class ScreeningAnalyzer:
    """スクリーニング分析クラス"""
    
    def __init__(
        self,
        api_client: Optional[JQuantsAPIClient] = None,
        use_cache: bool = True
    ):
        """
        初期化
        
        Args:
            api_client: J-QUANTS APIクライアント。Noneの場合は新規作成
            use_cache: キャッシュを使用するか
        """
        self.api_client = api_client or JQuantsAPIClient()
        self.cache = CacheManager() if use_cache else None
    
    def analyze_stock(
        self,
        code: str,
        name: Optional[str] = None,
        sector: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        個別銘柄を分析
        
        Args:
            code: 銘柄コード（5桁）
            name: 銘柄名（オプション）
            sector: 業種コード（オプション）
            
        Returns:
            分析結果の辞書。エラー時はNone
        """
        cache_key = f"stock_analysis_{code}"
        
        # キャッシュから取得を試みる
        if self.cache:
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                return cached_result
        
        try:
            # 財務データ取得
            financial_data = self.api_client.get_financial_summary(code=code)
            
            if not financial_data:
                return None
            
            # 年度データ抽出
            annual_data = extract_annual_data(financial_data)
            
            if not annual_data:
                return None
            
            # 年度末株価を取得（利用可能なデータを最大限使用）
            # 休日の場合は直前の営業日を使用
            prices = {}
            # 利用可能なデータを最大限使用（最大10年まで）
            available_years = len(annual_data)
            max_years = config.get_max_analysis_years()
            analysis_years = min(available_years, max_years)
            for year_data in annual_data[:analysis_years]:
                fy_end = year_data.get("CurFYEn")
                if fy_end:
                    # 年度終了日の形式を統一（YYYY-MM-DD）
                    if len(fy_end) == 8:  # YYYYMMDD形式
                        fy_end_formatted = f"{fy_end[:4]}-{fy_end[4:6]}-{fy_end[6:8]}"
                    else:
                        fy_end_formatted = fy_end
                    
                    # 休日の場合は直前の営業日を使用
                    price = self.api_client.get_price_at_date(
                        code,
                        fy_end_formatted,
                        use_nearest_trading_day=True
                    )
                    if price:
                        prices[fy_end_formatted] = price
                        prices[fy_end.replace("-", "")] = price  # YYYYMMDD形式も保存
            
            # 指標計算（柔軟な年数対応）
            metrics = calculate_metrics_flexible(annual_data, prices, analysis_years)
            
            # スクリーニング条件チェック（FCF連続プラス条件）
            # 無料プラン（2年）の場合は2年連続、有料プラン（3年以上）の場合は3年連続
            required_years = 3 if analysis_years >= 3 else 2
            passed, reason = check_screening_criteria(metrics, required_years)
            
            result = {
                "code": code,
                "name": name,
                "sector": sector,
                "metrics": metrics,
                "passed": passed,
                "reason": reason,
                "analyzed_at": datetime.now().isoformat(),
            }
            
            # キャッシュに保存
            if self.cache:
                self.cache.set(cache_key, result)
            
            return result
        
        except Exception as e:
            # エラーは呼び出し元で処理
            return {
                "code": code,
                "name": name,
                "sector": sector,
                "error": str(e),
                "passed": False,
                "reason": f"エラー: {str(e)}",
            }
    
    def screen_all_stocks(
        self,
        sector_filter: Optional[List[str]] = None,
        max_stocks: Optional[int] = None,
        request_delay: float = 1.0,
        random_sample: bool = False,
        early_exit_count: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        全市場をスクリーニング
        
        Args:
            sector_filter: 業種コードのリスト（33業種分類）。Noneの場合は全業種
            max_stocks: 最大分析銘柄数（テスト用）。Noneの場合は全銘柄
            request_delay: 各リクエスト間の待機時間（秒）。レート制限を避けるため
            random_sample: Trueの場合、ランダムに銘柄を選択（デフォルト: False）
            early_exit_count: 早期終了する合格銘柄数。指定した数に達したら分析を停止（Noneの場合は全分析）
            
        Returns:
            (合格銘柄リスト, スキップ銘柄リスト)
        """
        print("銘柄マスタを取得中...")
        master_data = self.api_client.get_equity_master()
        
        if not master_data:
            return [], []
        
        # 業種フィルタ適用
        if sector_filter:
            master_data = [
                stock for stock in master_data
                if stock.get("S33") in sector_filter
            ]
        
        # 最大銘柄数制限（テスト用）
        if max_stocks:
            if random_sample:
                # ランダムに選択
                import random
                if len(master_data) > max_stocks:
                    master_data = random.sample(master_data, max_stocks)
                    print(f"ランダムに{max_stocks}銘柄を選択しました")
            else:
                # 先頭から順番に選択（デフォルト）
                master_data = master_data[:max_stocks]
        
        print(f"分析対象: {len(master_data)}銘柄")
        
        passed_stocks = []
        skipped_stocks = []
        
        import time
        
        for i, stock in enumerate(master_data, 1):
            code = stock.get("Code")
            name = stock.get("CoName")
            sector = stock.get("S33")
            
            if not code:
                continue
            
            print(f"[{i}/{len(master_data)}] {code} {name or ''} を分析中...")
            
            try:
                result = self.analyze_stock(code, name, sector)
            except Exception as e:
                error_msg = str(e)
                if "レート制限" in error_msg or "429" in error_msg:
                    print(f"  ⚠️  レート制限に達しました。処理を中断します。")
                    print(f"  現在までに分析した銘柄: {i-1}銘柄")
                    print(f"  合格銘柄: {len(passed_stocks)}銘柄")
                    print(f"  スキップ銘柄: {len(skipped_stocks)}銘柄")
                    print(f"\n  しばらく時間をおいてから再試行してください。")
                    print(f"  キャッシュを活用することで、既に分析済みの銘柄はスキップされます。")
                    break
                else:
                    # その他のエラーはスキップ
                    skipped_stocks.append({
                        "code": code,
                        "name": name,
                        "reason": f"エラー: {error_msg}",
                    })
                    continue
            
            # レート制限を避けるため、各リクエスト間に待機時間を追加
            if i < len(master_data):  # 最後の銘柄以外は待機
                time.sleep(request_delay)
            
            if result is None:
                skipped_stocks.append({
                    "code": code,
                    "name": name,
                    "reason": "データ取得失敗",
                })
                continue
            
            if "error" in result:
                skipped_stocks.append({
                    "code": code,
                    "name": name,
                    "reason": result.get("error", "不明なエラー"),
                })
                continue
            
            if result.get("passed"):
                passed_stocks.append(result)
                
                # 早期終了チェック
                if early_exit_count and len(passed_stocks) >= early_exit_count:
                    print(f"\n早期終了: 合格銘柄が{early_exit_count}件に達したため、分析を停止しました")
                    print(f"分析済み: {i}/{len(master_data)}銘柄")
                    break
            else:
                # 不合格でもスキップリストには含めない（正常な分析結果）
                pass
        
        print(f"\n分析完了: 合格 {len(passed_stocks)}銘柄, スキップ {len(skipped_stocks)}銘柄")
        
        return passed_stocks, skipped_stocks
    
    def get_summary_view(
        self,
        stocks: List[Dict[str, Any]],
        sort_by: Optional[str] = "roe"
    ) -> List[Dict[str, Any]]:
        """
        サマリービューを生成
        
        Args:
            stocks: 分析結果のリスト
            sort_by: ソート基準（"roe", "fcf", "eps", "per", "pbr"）。Noneの場合はソートしない
            
        Returns:
            サマリービューのリスト
        """
        summaries = []
        
        for stock in stocks:
            metrics = stock.get("metrics", {})
            years = metrics.get("years", [])
            
            if not years:
                continue
            
            latest = years[0]
            
            # 決算時期を取得（年度終了日から）
            fiscal_period = None
            fy_end = latest.get("fy_end")
            if fy_end:
                try:
                    if len(fy_end) == 10:  # YYYY-MM-DD
                        year, month, _ = fy_end.split("-")
                        fiscal_period = f"{year}年{int(month)}月決算時点"
                    elif len(fy_end) == 8:  # YYYYMMDD
                        year = fy_end[:4]
                        month = fy_end[4:6]
                        fiscal_period = f"{year}年{int(month)}月決算時点"
                except:
                    pass
            
            summary = {
                "code": stock.get("code"),
                "name": stock.get("name"),
                "sector": stock.get("sector"),
                "fcf": latest.get("fcf"),
                "roe": latest.get("roe"),
                "eps": latest.get("eps"),
                "per": latest.get("per"),
                "pbr": latest.get("pbr"),
                "fiscal_period": fiscal_period,  # 決算時期（○年○月決算時点）
            }
            summaries.append(summary)
        
        # ソート（sort_byがNoneの場合はソートしない）
        if sort_by:
            sort_key_map = {
                "roe": lambda x: x.get("roe") or 0,
                "fcf": lambda x: x.get("fcf") or 0,
                "eps": lambda x: x.get("eps") or 0,
                "per": lambda x: x.get("per") or float("inf"),
                "pbr": lambda x: x.get("pbr") or float("inf"),
            }
            
            sort_key = sort_key_map.get(sort_by, sort_key_map["roe"])
            summaries.sort(key=sort_key, reverse=(sort_by != "per" and sort_by != "pbr"))
        
        return summaries

