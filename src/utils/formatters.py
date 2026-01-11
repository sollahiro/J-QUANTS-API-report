"""
フォーマットユーティリティ

数値や日付のフォーマット関数を提供します。
"""

from datetime import datetime
from typing import Optional


def format_currency(value: Optional[float], decimals: int = 0) -> str:
    """
    数値を百万円単位で表示
    
    Args:
        value: フォーマットする数値
        decimals: 小数点以下の桁数（デフォルト: 0）
    
    Returns:
        フォーマットされた文字列（例: "1,234.56百万円"）
    """
    if value is None:
        return "N/A"
    try:
        val = float(value)
        if val == 0:
            return "0"
        abs_val = abs(val)
        sign = "-" if val < 0 else ""
        formatted = abs_val / 1000000
        return f"{sign}{formatted:,.{decimals}f}百万円"
    except (ValueError, TypeError):
        return "N/A"


def extract_fiscal_year_from_fy_end(fy_end: Optional[str]) -> str:
    """
    年度終了日から年度を抽出
    
    Args:
        fy_end: 年度終了日（YYYY-MM-DD形式またはYYYYMMDD形式）
    
    Returns:
        年度文字列（例: "2023年度"）
    """
    if not fy_end:
        return ""
    try:
        if isinstance(fy_end, str):
            if len(fy_end) >= 10:
                period_date = datetime.strptime(fy_end[:10], "%Y-%m-%d")
            elif len(fy_end) >= 8:
                period_date = datetime.strptime(fy_end[:8], "%Y%m%d")
            else:
                return ""
        else:
            return ""
        
        # 3月末が年度終了日の場合、その年度は前年
        if period_date.month == 3:
            return f"{period_date.year - 1}年度"
        else:
            return f"{period_date.year}年度"
    except (ValueError, TypeError):
        pass
    return ""

