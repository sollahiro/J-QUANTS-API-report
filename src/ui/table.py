"""
テーブル生成コンポーネント

年度別財務データテーブルの生成を提供します。
"""

import pandas as pd
import streamlit as st
from typing import List, Dict, Any, Optional
from src.utils.formatters import format_currency, extract_fiscal_year_from_fy_end


def create_financial_data_dataframe(years: List[Dict[str, Any]]) -> Optional[pd.DataFrame]:
    """
    年度別財務データのDataFrameを生成
    
    Args:
        years: 年度別財務データのリスト
    
    Returns:
        pandas DataFrame（データがない場合はNone）
    """
    if not years:
        return None
    
    # 年度列を最初に配置するため、列順序を明示的に定義
    column_order = [
        "年度",
        "売上高",
        "営業利益",
        "当期純利益",
        "純資産",
        "FCF",
        "ROE",
        "EPS",
        "PER",
        "配当金総額"
    ]
    
    df_data = []
    for year in years:
        # 年度列は数字のみ（「年度」の文字列を削除）
        fiscal_year = extract_fiscal_year_from_fy_end(year.get("fy_end", ""))
        fiscal_year_number = fiscal_year.replace("年度", "") if fiscal_year else ""
        
        df_data.append({
            "年度": fiscal_year_number,
            "売上高": format_currency(year.get("sales")),
            "営業利益": format_currency(year.get("op")),
            "当期純利益": format_currency(year.get("np")),
            "純資産": format_currency(year.get("eq")),
            "FCF": format_currency(year.get("fcf")),
            "ROE": f"{year.get('roe', 0):.1f}%" if year.get('roe') is not None else "N/A",
            "EPS": f"{year.get('eps', 0):.2f}円" if year.get('eps') is not None else "N/A",
            "PER": f"{year.get('per', 0):.1f}倍" if year.get('per') is not None else "N/A",
            "配当金総額": format_currency(year.get("div_total")),
        })
    
    # DataFrameを作成してから、列順序を明示的に指定
    df = pd.DataFrame(df_data)
    # 年度列が存在する列のみを順序付け
    existing_columns = [col for col in column_order if col in df.columns]
    df = df[existing_columns]
    
    return df


def display_financial_data_table(years: List[Dict[str, Any]]) -> None:
    """
    年度別財務データをStreamlitの純正コンポーネントで表示
    
    Args:
        years: 年度別財務データのリスト
    """
    if not years:
        st.info("年度別財務データがありません")
        return
    
    df = create_financial_data_dataframe(years)
    if df is None or df.empty:
        st.info("年度別財務データがありません")
        return
    
    # Streamlitの純正コンポーネントで表示
    # width='stretch'で幅を最大限に使用
    st.dataframe(
        df,
        width='stretch',
        hide_index=True
    )


# 後方互換性のため、旧関数名も残す（非推奨）
def create_financial_data_table(years: List[Dict[str, Any]]) -> str:
    """
    年度別財務データのHTMLテーブルを生成（非推奨）
    
    この関数は後方互換性のため残されていますが、新しいコードでは
    display_financial_data_table()を使用してください。
    
    Args:
        years: 年度別財務データのリスト
    
    Returns:
        空文字列（HTMLテーブルは生成されません）
    """
    # 非推奨警告を出す（ただし、既存コードの動作を壊さないため、空文字列を返す）
    return ""

