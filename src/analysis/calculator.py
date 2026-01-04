"""
指標計算モジュール（Phase 1: 2年対応）

2年データと3年以上データの両方に対応した指標計算を提供します。
- 2年データ: 前年比成長率（Year-over-Year）
- 3年以上データ: CAGR（年平均成長率）
"""

from typing import Optional, Dict, Any, List
import math
from ..config import config
from ..utils.errors import (
    check_data_availability,
    get_data_availability_message,
    validate_metrics_for_analysis,
    DataAvailability
)


def calculate_yoy_growth(
    current_value: float,
    previous_value: float
) -> Optional[float]:
    """
    前年比成長率を計算（2年データ用）
    
    Args:
        current_value: 最新年の値
        previous_value: 前年の値
        
    Returns:
        前年比成長率（パーセント）。計算不可能な場合はNone
    """
    if current_value is None or previous_value is None:
        return None
    
    if previous_value <= 0:
        return None
    
    if current_value <= 0:
        return None
    
    try:
        yoy = ((current_value / previous_value) - 1.0) * 100
        return yoy
    except (ValueError, ZeroDivisionError):
        return None


def calculate_cagr(
    latest_value: float,
    oldest_value: float,
    years: int
) -> Optional[float]:
    """
    CAGR（年平均成長率）を計算（3年以上データ用）
    
    Args:
        latest_value: 最新年の値
        oldest_value: 最古の値
        years: 年数（例: 3年分のデータなら2年）
        
    Returns:
        CAGR（パーセント）。計算不可能な場合はNone
    """
    if latest_value is None or oldest_value is None:
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


def calculate_growth_rate(
    values: List[float],
    metric_name: str = ""
) -> Optional[float]:
    """
    成長率を計算（データ年数に応じて自動選択）
    
    Args:
        values: 値のリスト（新しい順、最大3年分以上）
        metric_name: 指標名（ログ用）
        
    Returns:
        成長率（パーセント）。計算不可能な場合はNone
    """
    if not values or len(values) < 2:
        return None
    
    # None値を除外
    valid_values = [v for v in values if v is not None]
    if len(valid_values) < 2:
        return None
    
    # 最新値と最古値
    latest = valid_values[0]
    oldest = valid_values[-1]
    
    # データ年数に応じて計算方法を選択
    if len(valid_values) == 2:
        # 2年データ: 前年比成長率
        return calculate_yoy_growth(latest, oldest)
    else:
        # 3年以上: CAGR
        years = len(valid_values) - 1
        return calculate_cagr(latest, oldest, years)


def calculate_metrics_flexible(
    annual_data: List[Dict[str, Any]],
    prices: Optional[Dict[str, float]] = None,
    analysis_years: Optional[int] = None
) -> Dict[str, Any]:
    """
    年度データから各種指標を計算（柔軟な年数対応）
    
    Args:
        annual_data: 年度データのリスト（新しい順）
        prices: 年度終了日をキーとした株価の辞書（YYYY-MM-DD形式）
        analysis_years: 分析対象年数（Noneの場合は設定から取得）
        
    Returns:
        計算済み指標の辞書
    """
    if not annual_data:
        return {}
    
    # 分析年数を取得（Noneの場合は利用可能なデータを最大限使用）
    if analysis_years is None:
        # 利用可能なデータを最大限使用（最大10年まで）
        max_years = config.get_max_analysis_years()
        analysis_years = min(len(annual_data), max_years)
    
    # デバッグ出力
    print(f"🔧 calculate_metrics_flexible: 分析年数={analysis_years}, 利用可能年数={len(annual_data)}")
    
    # 未来の年度データを除外（念のため追加チェック）
    from datetime import datetime
    today = datetime.now()
    current_year = today.year
    current_month = today.month
    
    # 重複除去済みのデータから指定年数分を取得（未来の年度は除外）
    years_data = []
    seen_fy_ends = set()
    for year_data in annual_data:
        fy_end = year_data.get("CurFYEn")
        if not fy_end:
            continue
        
        # 未来の年度データを除外
        try:
            if len(fy_end) == 8:  # YYYYMMDD
                year = int(fy_end[:4])
                month = int(fy_end[4:6])
            elif len(fy_end) == 10:  # YYYY-MM-DD
                year = int(fy_end[:4])
                month = int(fy_end[5:7])
            else:
                # 形式が不明な場合は含める
                year = None
                month = None
            
            # 現在日付より未来の年度は除外
            if year is not None and month is not None:
                if year > current_year or (year == current_year and month > current_month):
                    continue
        except (ValueError, IndexError):
            # パースエラーは無視（含める）
            pass
        
        # 主要財務データが全てN/Aの場合は除外
        # 売上高、営業利益、当期純利益、純資産の全てがNone、NaN、0、または空文字列の場合
        sales = year_data.get("Sales")
        op = year_data.get("OP")
        np = year_data.get("NP")
        eq = year_data.get("Eq")
        
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
            # デバッグログ
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"主要財務データが全てN/Aのため除外: fy_end={fy_end}, sales={sales}, op={op}, np={np}, eq={eq}")
            continue
        
        if fy_end not in seen_fy_ends:
            years_data.append(year_data)
            seen_fy_ends.add(fy_end)
            if len(years_data) >= analysis_years:
                break
    
    print(f"🔧 calculate_metrics_flexible: 実際に使用する年数={len(years_data)}")
    
    if len(years_data) < 1:
        return {}
    
    # 最新年度のデータ
    latest = years_data[0]
    
    # 指標計算用のデータを準備
    metrics = {
        "code": latest.get("Code"),
        "latest_fy_end": latest.get("CurFYEn"),
        "analysis_years": len(years_data),
        "available_years": len(years_data),
    }
    
    # 各年度の指標を計算
    years_metrics = []
    for year_data in years_data:
        fy_end = year_data.get("CurFYEn")
        
        # 基本財務データ（数値に変換）
        def to_float(value):
            """値をfloatに変換"""
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
        op = to_float(year_data.get("OP"))
        np = to_float(year_data.get("NP"))
        eq = to_float(year_data.get("Eq"))
        cfo = to_float(year_data.get("CFO"))
        cfi = to_float(year_data.get("CFI"))
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
            price_key = fy_end
            if price_key in prices:
                price = prices[price_key]
            else:
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
    
    # 成長率計算（データ年数に応じて自動選択）
    # 2年データ: 前年比成長率、3年以上: CAGR
    if len(years_metrics) >= 2:
        # FCF成長率
        fcf_values = [y.get("fcf") for y in years_metrics]
        metrics["fcf_growth"] = calculate_growth_rate(fcf_values, "FCF")
        # 後方互換性のため、CAGRという名前でも保存（3年以上の場合のみ）
        if len(years_metrics) >= 3:
            metrics["fcf_cagr"] = metrics["fcf_growth"]
        else:
            metrics["fcf_cagr"] = None
        
        # ROE成長率
        roe_values = [y.get("roe") for y in years_metrics]
        metrics["roe_growth"] = calculate_growth_rate(roe_values, "ROE")
        if len(years_metrics) >= 3:
            metrics["roe_cagr"] = metrics["roe_growth"]
        else:
            metrics["roe_cagr"] = None
        
        # EPS成長率
        eps_values = [y.get("eps") for y in years_metrics]
        metrics["eps_growth"] = calculate_growth_rate(eps_values, "EPS")
        if len(years_metrics) >= 3:
            metrics["eps_cagr"] = metrics["eps_growth"]
        else:
            metrics["eps_cagr"] = None
        
        # 売上高成長率
        sales_values = [y.get("sales") for y in years_metrics]
        metrics["sales_growth"] = calculate_growth_rate(sales_values, "売上高")
        if len(years_metrics) >= 3:
            metrics["sales_cagr"] = metrics["sales_growth"]
        else:
            metrics["sales_cagr"] = None
        
        # PER成長率
        per_values = [y.get("per") for y in years_metrics if y.get("per") is not None]
        if len(per_values) >= 2:
            metrics["per_growth"] = calculate_growth_rate(per_values, "PER")
            if len(per_values) >= 3:
                metrics["per_cagr"] = metrics["per_growth"]
            else:
                metrics["per_cagr"] = None
        else:
            metrics["per_growth"] = None
            metrics["per_cagr"] = None
        
        # PBR成長率
        pbr_values = [y.get("pbr") for y in years_metrics if y.get("pbr") is not None]
        if len(pbr_values) >= 2:
            metrics["pbr_growth"] = calculate_growth_rate(pbr_values, "PBR")
            if len(pbr_values) >= 3:
                metrics["pbr_cagr"] = metrics["pbr_growth"]
            else:
                metrics["pbr_cagr"] = None
        else:
            metrics["pbr_growth"] = None
            metrics["pbr_cagr"] = None
        
        # 配当性向成長率
        payout_values = [y.get("payout_ratio") for y in years_metrics if y.get("payout_ratio") is not None]
        if len(payout_values) >= 2:
            metrics["payout_growth"] = calculate_growth_rate(payout_values, "配当性向")
            if len(payout_values) >= 3:
                metrics["payout_cagr"] = metrics["payout_growth"]
            else:
                metrics["payout_cagr"] = None
        else:
            metrics["payout_growth"] = None
            metrics["payout_cagr"] = None
    else:
        metrics["fcf_growth"] = None
        metrics["roe_growth"] = None
        metrics["eps_growth"] = None
        metrics["sales_growth"] = None
        metrics["per_growth"] = None
        metrics["pbr_growth"] = None
        metrics["payout_growth"] = None
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
    
    # データ取得状況の検証
    data_status = check_data_availability(metrics, analysis_years)
    metrics["data_availability"] = data_status.value
    metrics["data_availability_message"] = get_data_availability_message(metrics, analysis_years)
    
    # 検証結果
    is_valid, validation_message = validate_metrics_for_analysis(metrics, min(2, analysis_years))
    metrics["data_valid"] = is_valid
    if not is_valid:
        metrics["validation_message"] = validation_message
    
    return metrics


def calculate_quarterly_metrics(
    quarterly_data: List[Dict[str, Any]],
    prices: Optional[Dict[str, float]] = None,
    quarters: int = 8
) -> Dict[str, Any]:
    """
    四半期データから各種指標を計算（直近N四半期分）
    
    Args:
        quarterly_data: 四半期データのリスト（新しい順）
        prices: 四半期末日をキーとした株価の辞書（YYYY-MM-DD形式）
        quarters: 分析対象四半期数（デフォルト: 8四半期 = 2年分）
        
    Returns:
        計算済み指標の辞書
    """
    if not quarterly_data:
        return {}
    
    # 指定された四半期数までに制限
    quarters_data = quarterly_data[:quarters]
    
    if not quarters_data:
        return {}
    
    # 最新四半期のデータ
    latest = quarters_data[0]
    
    # 指標計算用のデータを準備
    metrics = {
        "code": latest.get("Code"),
        "latest_quarter_end": latest.get("CurFYEn"),  # 最新四半期末日
        "quarters": len(quarters_data),
    }
    
    # 各四半期の指標を計算
    quarters_metrics = []
    for i, quarter_data in enumerate(quarters_data):
        # 実際の四半期末日を取得（計算済みのものがあればそれを使用）
        quarter_end = quarter_data.get("_quarter_end_date") or quarter_data.get("CurFYEn")
        
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
        
        sales = to_float(quarter_data.get("Sales"))
        np = to_float(quarter_data.get("NP"))
        eq = to_float(quarter_data.get("Eq"))
        eps = to_float(quarter_data.get("EPS"))
        bps = to_float(quarter_data.get("BPS"))
        
        # BPSが取得できない場合、Eq（純資産）と発行済み株式数から計算
        if bps is None:
            sh_out = to_float(quarter_data.get("ShOutFY"))  # 発行済み株式数（千株）
            if eq is not None and sh_out is not None and sh_out > 0:
                # BPS = 純資産（円） / 発行済み株式数（千株） / 1000
                # Eqは円単位、ShOutFYは千株単位なので、1000で割る必要がある
                bps = eq / (sh_out * 1000)
        
        # 株価を取得
        price = None
        if prices and quarter_end:
            # 日付形式を統一して検索
            if len(quarter_end) == 8:  # YYYYMMDD
                date_key = f"{quarter_end[:4]}-{quarter_end[4:6]}-{quarter_end[6:8]}"
            elif len(quarter_end) == 10:  # YYYY-MM-DD
                date_key = quarter_end
            else:
                date_key = quarter_end
            
            price = prices.get(date_key) or prices.get(quarter_end)
        
        # PER, PBRを計算
        per = None
        pbr = None
        if price is not None:
            if eps is not None and eps > 0:
                per = price / eps
            if bps is not None and bps > 0:
                pbr = price / bps
        
        quarter_metric = {
            "quarter_end": quarter_end,
            "per_type": quarter_data.get("CurPerType"),  # Q1, Q2, Q3, Q4
            "sales": sales,
            "np": np,
            "eq": eq,
            "eps": eps,
            "bps": bps,
            "price": price,
            "per": per,
            "pbr": pbr,
        }
        
        quarters_metrics.append(quarter_metric)
    
    metrics["quarters_data"] = quarters_metrics
    
    # 指数化の基準（最も古い四半期）を取得
    if len(quarters_metrics) >= 2:
        oldest_quarter = quarters_metrics[-1]
        oldest_price = oldest_quarter.get("price")
        oldest_eps = oldest_quarter.get("eps")
        oldest_sales = oldest_quarter.get("sales")
        
        # 指数化（基準 = 100）
        price_index = []
        eps_index = []
        sales_index = []
        
        for qm in quarters_metrics:
            price = qm.get("price")
            eps = qm.get("eps")
            sales = qm.get("sales")
            
            if oldest_price and price:
                price_idx = (price / oldest_price) * 100
                price_index.append(price_idx)
            else:
                price_index.append(None)
            
            if oldest_eps and eps and oldest_eps > 0:
                eps_idx = (eps / oldest_eps) * 100
                eps_index.append(eps_idx)
            else:
                eps_index.append(None)
            
            if oldest_sales and sales and oldest_sales > 0:
                sales_idx = (sales / oldest_sales) * 100
                sales_index.append(sales_idx)
            else:
                sales_index.append(None)
        
        metrics["price_index"] = price_index
        metrics["eps_index"] = eps_index
        metrics["sales_index"] = sales_index
        metrics["oldest_quarter_end"] = oldest_quarter.get("quarter_end")
    else:
        metrics["price_index"] = []
        metrics["eps_index"] = []
        metrics["sales_index"] = []
        metrics["oldest_quarter_end"] = None
    
    return metrics

