"""
財務データ処理と指標計算モジュール
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import math


def extract_annual_data(
    quarterly_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    四半期データから年度データを抽出

    Args:
        quarterly_data: fin-summaryから取得した四半期データ

    Returns:
        年度データ（CurPerType="FY"）のリスト、年度終了日でソート（重複除去済み、未来の年度は除外）
    """
    from datetime import datetime
    
    # 現在日付を取得
    today = datetime.now()
    current_year = today.year
    current_month = today.month
    
    annual_data = []
    for record in quarterly_data:
        if record.get("CurPerType") != "FY":
            continue
        
        # 未来の年度データを除外
        fy_end = record.get("CurFYEn", "")
        if fy_end:
            # YYYYMMDD形式またはYYYY-MM-DD形式を想定
            if len(fy_end) == 8:  # YYYYMMDD
                year = int(fy_end[:4])
                month = int(fy_end[4:6])
            elif len(fy_end) == 10:  # YYYY-MM-DD
                year = int(fy_end[:4])
                month = int(fy_end[5:7])
            else:
                # 形式が不明な場合は含める
                annual_data.append(record)
                continue
            
            # 現在日付より未来の年度は除外
            # 例: 2025/12/31時点で2026年3月のデータは除外
            if year > current_year or (year == current_year and month > current_month):
                continue
        
        # 主要財務データが全てN/Aの場合は除外
        # 売上高、営業利益、当期純利益、純資産の全てがNone、NaN、0、または空文字列の場合
        sales = record.get("Sales")
        op = record.get("OP")
        np = record.get("NP")
        eq = record.get("Eq")
        
        # 値を数値に変換してチェック（NaN、None、空文字列、0は無効）
        def is_valid_value(value):
            if value is None:
                return False
            if value == "":
                return False
            # NaNチェック（float('nan')やnumpy.nanなど）
            try:
                import math
                if isinstance(value, float) and math.isnan(value):
                    return False
            except (ImportError, TypeError):
                pass
            # pandasのNaNチェック
            try:
                import pandas as pd
                if pd.isna(value):
                    return False
            except (ImportError, TypeError, AttributeError):
                pass
            try:
                num_value = float(value)
                if math.isnan(num_value):
                    return False
                return num_value != 0
            except (ValueError, TypeError):
                return False
        
        # 全ての主要データが無効な場合、このレコードを除外
        has_valid_data = (
            is_valid_value(sales) or
            is_valid_value(op) or
            is_valid_value(np) or
            is_valid_value(eq)
        )
        
        if not has_valid_data:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"主要財務データが全てN/Aのため除外: fy_end={fy_end}, sales={sales}, op={op}, np={np}, eq={eq}")
            continue
        
        annual_data.append(record)
    
    # 年度終了日（CurFYEn）でソート（新しい順）
    annual_data.sort(
        key=lambda x: (x.get("CurFYEn", ""), x.get("DiscDate", "")),
        reverse=True
    )
    
    # 同じ年度終了日のデータが複数ある場合、最新の開示日で主要データがあるものを残す（重複除去）
    seen_years = {}
    unique_annual_data = []
    for record in annual_data:
        fy_end = record.get("CurFYEn")
        if not fy_end:
            continue
            
        if fy_end not in seen_years:
            seen_years[fy_end] = record
            unique_annual_data.append(record)
        else:
            # 既に存在する場合は、主要データ（売上高）があるもの、またはより新しい開示日を優先
            existing_record = seen_years[fy_end]
            existing_disc_date = existing_record.get("DiscDate", "") or ""
            current_disc_date = record.get("DiscDate", "") or ""
            
            # 主要データ（売上高）の有無を確認
            existing_has_data = existing_record.get("Sales") is not None
            current_has_data = record.get("Sales") is not None
            
            # データがあるものを優先、同じなら新しい開示日を優先
            should_replace = False
            if current_has_data and not existing_has_data:
                should_replace = True
            elif current_has_data == existing_has_data and current_disc_date > existing_disc_date:
                should_replace = True
            
            if should_replace:
                # 既存のレコードを置き換え
                idx = unique_annual_data.index(existing_record)
                unique_annual_data[idx] = record
                seen_years[fy_end] = record
    
    return unique_annual_data


def calculate_cagr(
    latest_value: float,
    oldest_value: float,
    years: int = 2
) -> Optional[float]:
    """
    CAGR（年平均成長率）を計算

    Args:
        latest_value: 最新年の値
        oldest_value: 最古の値（3年前）
        years: 年数（デフォルト: 2年 = 3年分のデータ）

    Returns:
        CAGR（パーセント）。計算不可能な場合はNone
    """
    if oldest_value is None or latest_value is None:
        return None
    
    if oldest_value <= 0:
        return None
    
    if latest_value <= 0:
        return None
    
    if years <= 0:
        return None
    
    try:
        cagr = (math.pow(latest_value / oldest_value, 1.0 / years) - 1.0) * 100
        return cagr
    except (ValueError, ZeroDivisionError):
        return None


def calculate_metrics(
    annual_data: List[Dict[str, Any]],
    prices: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    年度データから各種指標を計算（未来の年度データは除外済み）

    Args:
        annual_data: 年度データのリスト（新しい順、最大3年分、未来の年度は除外済み）
        prices: 年度終了日をキーとした株価の辞書（YYYY-MM-DD形式）

    Returns:
        計算済み指標の辞書
    """
    if not annual_data:
        return {}
    
    # 最新3年分のデータを取得（重複除去済みのデータから、年度終了日が異なる年度のみ）
    # extract_annual_dataで既に重複除去されているので、そのまま使用
    years_data = annual_data[:3]
    
    if len(years_data) < 1:
        return {}
    
    # 最新年度のデータ
    latest = years_data[0]
    
    # 指標計算用のデータを準備
    metrics = {
        "code": latest.get("Code"),
        "latest_fy_end": latest.get("CurFYEn"),  # 最新年度終了日
    }
    
    # 各年度の指標を計算
    years_metrics = []
    for i, year_data in enumerate(years_data):
        fy_end = year_data.get("CurFYEn")
        
        # 基本財務データ（数値に変換）
        def to_float(value):
            """値をfloatに変換（Noneや文字列の場合も処理）"""
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
            return None
        
        sales = to_float(year_data.get("Sales"))
        op = to_float(year_data.get("OP"))  # 営業利益
        np = to_float(year_data.get("NP"))  # 当期純利益
        eq = to_float(year_data.get("Eq"))  # 純資産
        cfo = to_float(year_data.get("CFO"))  # 営業CF
        cfi = to_float(year_data.get("CFI"))  # 投資CF
        eps = to_float(year_data.get("EPS"))
        bps = to_float(year_data.get("BPS"))
        # 配当性向（APIからは小数で返ってくるので100倍してパーセント値に変換）
        payout_ratio_raw = to_float(year_data.get("PayoutRatioAnn"))
        payout_ratio = payout_ratio_raw * 100 if payout_ratio_raw is not None else None
        
        # FCF計算
        fcf = None
        if cfo is not None and cfi is not None:
            fcf = cfo + cfi
        
        # ROE計算
        roe = None
        if np is not None and eq is not None:
            try:
                eq_float = float(eq) if not isinstance(eq, (int, float)) else eq
                if eq_float != 0:
                    np_float = float(np) if not isinstance(np, (int, float)) else np
                    roe = (np_float / eq_float) * 100
            except (ValueError, TypeError, ZeroDivisionError):
                roe = None
        
        # 株価取得
        price = None
        if prices and fy_end:
            # 年度終了日の形式を確認（YYYY-MM-DD または YYYYMMDD）
            price_key = fy_end
            if price_key in prices:
                price = prices[price_key]
            else:
                # YYYYMMDD形式で試す
                price_key_alt = fy_end.replace("-", "")
                if price_key_alt in prices:
                    price = prices[price_key_alt]
        
        # PER計算
        per = None
        if price is not None and eps is not None:
            try:
                eps_float = float(eps) if not isinstance(eps, (int, float)) else eps
                if eps_float > 0:
                    per = float(price) / eps_float
            except (ValueError, TypeError, ZeroDivisionError):
                per = None
        
        # PBR計算
        pbr = None
        if price is not None and bps is not None:
            try:
                bps_float = float(bps) if not isinstance(bps, (int, float)) else bps
                if bps_float > 0:
                    pbr = float(price) / bps_float
            except (ValueError, TypeError, ZeroDivisionError):
                pbr = None
        
        year_metric = {
            "fy_end": fy_end,
            "sales": sales,
            "op": op,
            "np": np,
            "eq": eq,
            "cfo": cfo,
            "cfi": cfi,
            "fcf": fcf,
            "roe": roe,
            "eps": eps,
            "bps": bps,
            "price": price,
            "per": per,
            "pbr": pbr,
            "payout_ratio": payout_ratio,  # 配当性向
        }
        years_metrics.append(year_metric)
    
    metrics["years"] = years_metrics
    
    # CAGR計算（3年分のデータがある場合）
    if len(years_metrics) >= 3:
        latest_year = years_metrics[0]
        oldest_year = years_metrics[2]
        
        # FCF CAGR
        if latest_year["fcf"] is not None and oldest_year["fcf"] is not None:
            metrics["fcf_cagr"] = calculate_cagr(
                latest_year["fcf"],
                oldest_year["fcf"]
            )
        else:
            metrics["fcf_cagr"] = None
        
        # ROE CAGR
        if latest_year["roe"] is not None and oldest_year["roe"] is not None:
            metrics["roe_cagr"] = calculate_cagr(
                latest_year["roe"],
                oldest_year["roe"]
            )
        else:
            metrics["roe_cagr"] = None
        
        # EPS CAGR
        if latest_year["eps"] is not None and oldest_year["eps"] is not None:
            metrics["eps_cagr"] = calculate_cagr(
                latest_year["eps"],
                oldest_year["eps"]
            )
        else:
            metrics["eps_cagr"] = None
        
        # 売上高成長率 CAGR
        if latest_year["sales"] is not None and oldest_year["sales"] is not None:
            metrics["sales_cagr"] = calculate_cagr(
                latest_year["sales"],
                oldest_year["sales"]
            )
        else:
            metrics["sales_cagr"] = None
        
        # PER CAGR
        if latest_year["per"] is not None and oldest_year["per"] is not None:
            metrics["per_cagr"] = calculate_cagr(
                latest_year["per"],
                oldest_year["per"]
            )
        else:
            metrics["per_cagr"] = None
        
        # PBR CAGR
        if latest_year["pbr"] is not None and oldest_year["pbr"] is not None:
            metrics["pbr_cagr"] = calculate_cagr(
                latest_year["pbr"],
                oldest_year["pbr"]
            )
        else:
            metrics["pbr_cagr"] = None
        
        # 配当性向 CAGR
        if latest_year["payout_ratio"] is not None and oldest_year["payout_ratio"] is not None:
            metrics["payout_cagr"] = calculate_cagr(
                latest_year["payout_ratio"],
                oldest_year["payout_ratio"]
            )
        else:
            metrics["payout_cagr"] = None
    else:
        # 3年分のデータがない場合はCAGRをNoneに
        metrics["fcf_cagr"] = None
        metrics["roe_cagr"] = None
        metrics["eps_cagr"] = None
        metrics["sales_cagr"] = None
        metrics["per_cagr"] = None
        metrics["pbr_cagr"] = None
        metrics["payout_cagr"] = None
    
    # 最新年度の値をメトリクスに追加（表示用）
    if years_metrics:
        latest = years_metrics[0]
        metrics["latest_fcf"] = latest.get("fcf")
        metrics["latest_roe"] = latest.get("roe")
        metrics["latest_eps"] = latest.get("eps")
        metrics["latest_per"] = latest.get("per")
        metrics["latest_pbr"] = latest.get("pbr")
        metrics["latest_sales"] = latest.get("sales")
    
    return metrics


def get_monthly_avg_stock_price(
    api_client,
    code: str,
    fiscal_year: str,
    fy_end_month: int = 3
) -> Optional[float]:
    """
    指定した会計年度の月次平均株価を取得
    
    Args:
        api_client: JQuantsAPIClientインスタンス
        code: 銘柄コード（4桁または5桁）
        fiscal_year: 会計年度（YYYY形式、例: "2024"）
        fy_end_month: 会計年度末の月（デフォルト: 3月）
    
    Returns:
        月次平均株価（調整後終値ベース）
        取得できない場合はNone
    """
    try:
        # 会計年度の期間を計算
        # 例: 2024年度（3月決算）→ 2024-04-01 ～ 2025-03-31
        year = int(fiscal_year)
        start_date = datetime(year, fy_end_month + 1 if fy_end_month < 12 else 1, 1)
        if fy_end_month == 12:
            start_date = datetime(year + 1, 1, 1)
        end_date = datetime(year + 1, fy_end_month, 1)
        
        # 月末日を取得
        if end_date.month == 12:
            end_date = datetime(end_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(end_date.year, end_date.month + 1, 1) - timedelta(days=1)
        
        # 日付を文字列に変換（YYYY-MM-DD形式）
        from_date_str = start_date.strftime("%Y-%m-%d")
        to_date_str = end_date.strftime("%Y-%m-%d")
        
        # 株価データを取得
        bars = api_client.get_daily_bars(
            code=code,
            from_date=from_date_str,
            to_date=to_date_str
        )
        
        if not bars:
            return None
        
        # 調整後終値（AdjC）を使用して月次平均を計算
        adj_close_values = []
        for bar in bars:
            adj_close = bar.get("AdjC") or bar.get("C")  # AdjCがなければC（終値）を使用
            if adj_close is not None:
                adj_close_values.append(float(adj_close))
        
        if not adj_close_values:
            return None
        
        # 月次平均を計算
        monthly_avg = sum(adj_close_values) / len(adj_close_values)
        return monthly_avg
        
    except Exception:
        # エラーが発生した場合はNoneを返す
        return None


def get_fiscal_year_end_price(
    api_client,
    code: str,
    fiscal_year_end: str
) -> Optional[float]:
    """
    会計年度末の株価（終値）を取得
    休日の場合は直前の営業日を使用
    
    Args:
        api_client: JQuantsAPIClientインスタンス
        code: 銘柄コード（4桁または5桁）
        fiscal_year_end: 会計年度終了日（YYYY-MM-DD形式またはYYYYMMDD形式）
    
    Returns:
        調整後終値（AdjC）
        取得できない場合はNone
    """
    try:
        # 日付形式を統一（YYYY-MM-DD形式に変換）
        if len(fiscal_year_end) == 8:  # YYYYMMDD形式
            date_str = f"{fiscal_year_end[:4]}-{fiscal_year_end[4:6]}-{fiscal_year_end[6:8]}"
        elif len(fiscal_year_end) == 10:  # YYYY-MM-DD形式
            date_str = fiscal_year_end
        else:
            return None
        
        # get_price_at_dateを使用（休日対応）
        # これにより、休日の場合は直前の営業日を自動的に取得
        price = api_client.get_price_at_date(
            code=code,
            date=date_str,
            use_nearest_trading_day=True
        )
        
        return price
        
    except Exception as e:
        # エラーが発生した場合はNoneを返す
        return None


def _calculate_quarter_end_date(fy_end: str, per_type: str) -> Optional[str]:
    """
    CurFYEn（年度終了日）とCurPerType（四半期タイプ）から、実際の四半期末日を計算
    
    Args:
        fy_end: 年度終了日（YYYYMMDD形式またはYYYY-MM-DD形式）
        per_type: 四半期タイプ（"1Q", "2Q", "3Q", "4Q", "Q1", "Q2", "Q3", "Q4"）
    
    Returns:
        四半期末日（YYYY-MM-DD形式）、計算できない場合はNone
    """
    from datetime import datetime
    
    try:
        # 日付形式を統一
        if len(fy_end) == 8:  # YYYYMMDD
            fy_year = int(fy_end[:4])
            fy_month = int(fy_end[4:6])
            fy_day = int(fy_end[6:8])
        elif len(fy_end) == 10:  # YYYY-MM-DD
            fy_year = int(fy_end[:4])
            fy_month = int(fy_end[5:7])
            fy_day = int(fy_end[8:10])
        else:
            return None
        
        # 四半期タイプを正規化（"1Q" -> 1, "Q1" -> 1）
        quarter_num = None
        if per_type in ["1Q", "Q1"]:
            quarter_num = 1
        elif per_type in ["2Q", "Q2"]:
            quarter_num = 2
        elif per_type in ["3Q", "Q3"]:
            quarter_num = 3
        elif per_type in ["4Q", "Q4"]:
            quarter_num = 4
        
        if quarter_num is None:
            return None
        
        # 年度終了月から四半期末日を計算
        # 3月決算の場合: 1Q=6月(前年), 2Q=9月(前年), 3Q=12月(前年), 4Q=3月(年度終了日)
        # 12月決算の場合: 1Q=3月, 2Q=6月, 3Q=9月, 4Q=12月(年度終了日)
        # 6月決算の場合: 1Q=9月(前年), 2Q=12月(前年), 3Q=3月, 4Q=6月(年度終了日)
        # 9月決算の場合: 1Q=12月(前年), 2Q=3月, 3Q=6月, 4Q=9月(年度終了日)
        
        if quarter_num == 4:
            # 4Q: 年度終了日（CurFYEnそのもの）
            quarter_end = datetime(fy_year, fy_month, fy_day)
        else:
            # 1Q, 2Q, 3Qの計算
            if fy_month == 3:  # 3月決算（年度: 前年4月～当年3月）
                if quarter_num == 1:
                    quarter_end = datetime(fy_year - 1, 6, 30)  # 前年6月
                elif quarter_num == 2:
                    quarter_end = datetime(fy_year - 1, 9, 30)  # 前年9月
                else:  # quarter_num == 3
                    quarter_end = datetime(fy_year - 1, 12, 31)  # 前年12月
            elif fy_month == 12:  # 12月決算（年度: 当年1月～12月）
                if quarter_num == 1:
                    quarter_end = datetime(fy_year, 3, 31)
                elif quarter_num == 2:
                    quarter_end = datetime(fy_year, 6, 30)
                else:  # quarter_num == 3
                    quarter_end = datetime(fy_year, 9, 30)
            elif fy_month == 6:  # 6月決算（年度: 前年7月～当年6月）
                if quarter_num == 1:
                    quarter_end = datetime(fy_year - 1, 9, 30)  # 前年9月
                elif quarter_num == 2:
                    quarter_end = datetime(fy_year - 1, 12, 31)  # 前年12月
                else:  # quarter_num == 3
                    quarter_end = datetime(fy_year, 3, 31)  # 当年3月
            elif fy_month == 9:  # 9月決算（年度: 前年10月～当年9月）
                if quarter_num == 1:
                    quarter_end = datetime(fy_year - 1, 12, 31)  # 前年12月
                elif quarter_num == 2:
                    quarter_end = datetime(fy_year, 3, 31)  # 当年3月
                else:  # quarter_num == 3
                    quarter_end = datetime(fy_year, 6, 30)  # 当年6月
            else:
                # その他の決算月は未対応（とりあえず年度終了日を使用）
                quarter_end = datetime(fy_year, fy_month, fy_day)
        
        return quarter_end.strftime("%Y-%m-%d")
    except Exception:
        return None


def extract_quarterly_data(
    quarterly_data: List[Dict[str, Any]],
    quarters: int = 8
) -> List[Dict[str, Any]]:
    """
    四半期データから直近N四半期分のデータを抽出
    
    Args:
        quarterly_data: fin-summaryから取得した四半期データ
        quarters: 取得する四半期数（デフォルト: 8四半期 = 2年分）
    
    Returns:
        四半期データ（CurPerType="Q1", "Q2", "Q3", "Q4"）のリスト、四半期末日でソート（新しい順、未来の四半期は除外）
    """
    from datetime import datetime
    
    # 現在日付を取得
    today = datetime.now()
    current_year = today.year
    current_month = today.month
    
    # FYデータから4Q相当のデータを抽出
    # まず、3Qデータを取得（年度ごとに）
    q3_records_by_fy = {}
    for record in quarterly_data:
        if record.get("CurPerType") == "3Q":
            fy_end = record.get("CurFYEn", "")
            if fy_end:
                q3_records_by_fy[fy_end] = record
    
    # FYデータから4Qを算出（FY - 3Q = 4Q）
    fy_records = [r for r in quarterly_data if r.get("CurPerType") == "FY"]
    for fy_record in fy_records:
        fy_end = fy_record.get("CurFYEn", "")
        if fy_end:
            q3_record = q3_records_by_fy.get(fy_end)
            
            # 4Qデータを作成
            q4_record = fy_record.copy()
            q4_record["CurPerType"] = "4Q"
            
            # 3Qデータが存在する場合は、FYから3Qを引いて4Qを算出
            if q3_record:
                # 数値フィールドを処理
                def subtract_values(fy_val, q3_val):
                    """FY値から3Q値を引く（4Q単独の値を算出）"""
                    try:
                        fy_float = float(fy_val) if fy_val is not None else 0
                        q3_float = float(q3_val) if q3_val is not None else 0
                        result = fy_float - q3_float
                        return result if result != 0 else None
                    except (ValueError, TypeError):
                        return None
                
                # 主要な財務指標を計算
                q4_record["Sales"] = subtract_values(fy_record.get("Sales"), q3_record.get("Sales"))
                q4_record["OP"] = subtract_values(fy_record.get("OP"), q3_record.get("OP"))
                q4_record["NP"] = subtract_values(fy_record.get("NP"), q3_record.get("NP"))
                q4_record["Eq"] = fy_record.get("Eq")  # 純資産は時点値なのでFYの値を使用
                q4_record["EPS"] = subtract_values(fy_record.get("EPS"), q3_record.get("EPS"))
                q4_record["BPS"] = fy_record.get("BPS")  # BPSは時点値なのでFYの値を使用
                q4_record["CFO"] = subtract_values(fy_record.get("CFO"), q3_record.get("CFO"))
                q4_record["CFI"] = subtract_values(fy_record.get("CFI"), q3_record.get("CFI"))
            
            # 3Qデータが存在しない場合は、FYデータをそのまま使用（累計値として扱う）
            quarterly_data.append(q4_record)
    
    quarterly_records = []
    per_type_counts = {}  # デバッグ用
    for record in quarterly_data:
        per_type = record.get("CurPerType", "")
        # 1Q, 2Q, 3Q, 4Q または Q1, Q2, Q3, Q4 を対象（J-QUANTS APIは "1Q" 形式を使用）
        if per_type not in ["1Q", "2Q", "3Q", "4Q", "Q1", "Q2", "Q3", "Q4"]:
            continue
        
        # デバッグ: 四半期タイプの分布を記録
        per_type_counts[per_type] = per_type_counts.get(per_type, 0) + 1
        
        # 実際の四半期末日を計算
        fy_end = record.get("CurFYEn", "")
        if fy_end:
            quarter_end_date = _calculate_quarter_end_date(fy_end, per_type)
            if quarter_end_date:
                # 計算された四半期末日をレコードに追加
                record["_quarter_end_date"] = quarter_end_date
                
                # 未来の四半期データを除外
                q_year = int(quarter_end_date[:4])
                q_month = int(quarter_end_date[5:7])
                if q_year > current_year or (q_year == current_year and q_month > current_month):
                    continue
        else:
            # CurFYEnがない場合は除外
            continue
        
        # 主要財務データが全てN/Aの場合は除外
        sales = record.get("Sales")
        op = record.get("OP")
        np = record.get("NP")
        eq = record.get("Eq")
        
        # 値を数値に変換してチェック（NaN、None、空文字列、0は無効）
        def is_valid_value(value):
            if value is None:
                return False
            if value == "":
                return False
            try:
                import math
                if isinstance(value, float) and math.isnan(value):
                    return False
            except (ImportError, TypeError):
                pass
            try:
                import pandas as pd
                if pd.isna(value):
                    return False
            except (ImportError, TypeError, AttributeError):
                pass
            try:
                num_value = float(value)
                if math.isnan(num_value):
                    return False
                return num_value != 0
            except (ValueError, TypeError):
                return False
        
        # 全ての主要データが無効な場合、このレコードを除外
        has_valid_data = (
            is_valid_value(sales) or
            is_valid_value(op) or
            is_valid_value(np) or
            is_valid_value(eq)
        )
        
        if not has_valid_data:
            continue
        
        quarterly_records.append(record)
    
    # 四半期末日（_quarter_end_date）でソート（新しい順）
    # 日付文字列を正しく比較できるように、YYYY-MM-DD形式に統一してからソート
    def get_sort_key(record):
        quarter_end = record.get("_quarter_end_date", "")
        disc_date = record.get("DiscDate", "")
        # YYYYMMDD形式をYYYY-MM-DD形式に変換
        if disc_date and len(disc_date) == 8:
            disc_date = f"{disc_date[:4]}-{disc_date[4:6]}-{disc_date[6:8]}"
        return (quarter_end, disc_date)
    
    quarterly_records.sort(key=get_sort_key, reverse=True)
    
    # 同じ四半期末日と四半期タイプの組み合わせで重複除去
    # _quarter_end_dateとCurPerTypeの組み合わせをキーとして使用（実際の四半期末日で重複を判定）
    seen_quarters = {}
    unique_quarterly_data = []
    for record in quarterly_records:
        quarter_end_date = record.get("_quarter_end_date", "")
        per_type = record.get("CurPerType", "")
        fy_end = record.get("CurFYEn", "")
        
        if not quarter_end_date:
            # _quarter_end_dateがない場合は、CurFYEnとCurPerTypeの組み合わせを使用
            if not fy_end:
                continue
            quarter_key = (fy_end, per_type)
        else:
            # _quarter_end_dateがある場合は、それとCurPerTypeの組み合わせを使用
            quarter_key = (quarter_end_date, per_type)
            
        if quarter_key not in seen_quarters:
            seen_quarters[quarter_key] = record
            unique_quarterly_data.append(record)
        else:
            # 既に存在する場合は、主要データ（売上高）があるもの、またはより新しい開示日を優先
            existing_record = seen_quarters[quarter_key]
            existing_disc_date = existing_record.get("DiscDate", "") or ""
            current_disc_date = record.get("DiscDate", "") or ""
            
            # 主要データ（売上高）の有無を確認
            existing_has_data = existing_record.get("Sales") is not None
            current_has_data = record.get("Sales") is not None
            
            # 4Qデータを優先（FYから算出した4Qより、元の4Qデータがあればそれを優先）
            existing_is_4q = existing_record.get("CurPerType") == "4Q"
            current_is_4q = per_type == "4Q"
            
            # データがあるものを優先、同じなら新しい開示日を優先、4Qデータを優先
            should_replace = False
            if current_has_data and not existing_has_data:
                should_replace = True
            elif current_has_data == existing_has_data:
                # 両方データがある場合、4Qデータを優先、またはより新しい開示日を優先
                if current_is_4q and not existing_is_4q:
                    should_replace = True
                elif current_is_4q == existing_is_4q and current_disc_date > existing_disc_date:
                    should_replace = True
            
            if should_replace:
                # 既存のレコードを置き換え
                idx = unique_quarterly_data.index(existing_record)
                unique_quarterly_data[idx] = record
                seen_quarters[quarter_key] = record
    
    # 指定された四半期数までに制限（新しい順にソート済みなので、最初のN件が最新）
    result = unique_quarterly_data[:quarters]
    
    # デバッグ: 取得された四半期データを確認
    if result:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"四半期データ取得: {len(result)}件（要求: {quarters}件）")
        logger.debug(f"四半期タイプ分布（フィルタ前）: {per_type_counts}")
        result_per_types = {}
        for q in result:
            pt = q.get('CurPerType', '')
            result_per_types[pt] = result_per_types.get(pt, 0) + 1
        logger.debug(f"四半期タイプ分布（取得後）: {result_per_types}")
        # 4Qが含まれているか確認
        has_4q = any(q.get('CurPerType') in ['4Q', 'Q4'] for q in result)
        if not has_4q and '4Q' in per_type_counts:
            logger.warning(f"4Qデータがフィルタ前には存在するが、取得結果に含まれていません（フィルタ前: {per_type_counts.get('4Q', 0)}件）")
        for i, q in enumerate(result):
            logger.debug(f"  {i+1}. {q.get('CurFYEn')} ({q.get('CurPerType')})")
    
    return result


def get_quarter_end_price(
    api_client,
    code: str,
    quarter_end: str
) -> Optional[float]:
    """
    四半期末の株価（終値）を取得
    休日の場合は直前の営業日を使用
    
    Args:
        api_client: JQuantsAPIClientインスタンス
        code: 銘柄コード（4桁または5桁）
        quarter_end: 四半期末日（YYYY-MM-DD形式またはYYYYMMDD形式）
    
    Returns:
        調整後終値（AdjC）
        取得できない場合はNone
    """
    try:
        # 日付形式を統一（YYYY-MM-DD形式に変換）
        if len(quarter_end) == 8:  # YYYYMMDD形式
            date_str = f"{quarter_end[:4]}-{quarter_end[4:6]}-{quarter_end[6:8]}"
        elif len(quarter_end) == 10:  # YYYY-MM-DD形式
            date_str = quarter_end
        else:
            return None
        
        # get_price_at_dateを使用（休日対応）
        price = api_client.get_price_at_date(
            code=code,
            date=date_str,
            use_nearest_trading_day=True
        )
        
        return price
        
    except Exception as e:
        # エラーが発生した場合はNoneを返す
        return None

