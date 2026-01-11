"""
分析ハンドラー

銘柄分析の実行と進捗管理を提供します。
"""

import streamlit as st
import time
from typing import Optional, Dict, Any
from src.analysis.individual import IndividualAnalyzer
from src.report.graph_generator import GraphGenerator
from src.api.client import JQuantsAPIClient


def run_analysis(
    code: str,
    status_placeholder: Optional[Any],  # st.delta_generator.DeltaGenerator
    progress_bar: Optional[Any]  # st.delta_generator.DeltaGenerator
) -> Optional[Dict[str, Any]]:
    """
    銘柄分析を実行
    
    Args:
        code: 銘柄コード
        status_placeholder: Streamlitのプレースホルダー（進捗表示用）
        progress_bar: Streamlitのプログレスバー
    
    Returns:
        分析結果の辞書、エラー時はNone
    
    Raises:
        ValueError: 銘柄コードが無効な場合、またはデータが取得できない場合
        Exception: その他の予期しないエラー
    """
    error_message = None
    
    try:
        # アナライザーを初期化
        if status_placeholder:
            status_placeholder.markdown("🔧 **アナライザーを初期化中...**")
        if progress_bar:
            progress_bar.progress(10)
        
        analyzer = IndividualAnalyzer(use_cache=True)  # キャッシュは自動で使用
        report_generator = GraphGenerator()
        
        if status_placeholder:
            status_placeholder.markdown("✅ **アナライザー初期化完了**")
        if progress_bar:
            progress_bar.progress(20)
        
        # まず銘柄マスタで存在確認
        if status_placeholder:
            status_placeholder.markdown(f"📊 **{code}**\n\n🔍 **J-QUANTS APIから情報を取得中...**\n- 銘柄マスタを取得中")
        if progress_bar:
            progress_bar.progress(30)
        
        api_client = JQuantsAPIClient()
        
        try:
            master_data = api_client.get_equity_master(code=code)
        except Exception as e:
            error_message = f"銘柄コード {code}: 銘柄マスタの取得中にエラーが発生しました - {str(e)}"
            st.error(error_message)
            raise
        
        if not master_data:
            error_message = f"銘柄コード {code}: J-QUANTS APIの銘柄マスタに存在しません。銘柄コードが正しいか確認してください。"
            st.error(error_message)
            raise ValueError(error_message)
        
        stock_info = master_data[0] if master_data else {}
        stock_name = stock_info.get("CoName", "")
        
        # 財務データの存在確認
        if status_placeholder:
            status_placeholder.markdown(f"📊 **{code} ({stock_name})**\n\n🔍 **J-QUANTS APIから情報を取得中...**\n- 財務データを取得中")
        if progress_bar:
            progress_bar.progress(40)
        
        try:
            financial_data = api_client.get_financial_summary(code=code)
        except Exception as e:
            error_message = f"銘柄コード {code} ({stock_name if stock_name else '不明'}): 財務データの取得中にエラーが発生しました - {str(e)}"
            st.error(error_message)
            raise
        
        if not financial_data:
            error_message = f"銘柄コード {code} ({stock_name if stock_name else '不明'}): 銘柄マスタには存在しますが、財務データが取得できませんでした。財務データが登録されていない可能性があります。"
            st.error(error_message)
            raise ValueError(error_message)
        
        # 分析実行
        if status_placeholder:
            status_placeholder.markdown(f"📊 **{code} ({stock_name})**\n\n🔧 **財務データを分析中...**\n- 年度データを抽出中\n- 指標を計算中")
        if progress_bar:
            progress_bar.progress(50)
        
        # 進捗コールバック関数を定義
        def update_progress(message: str):
            """進捗を更新するコールバック関数"""
            if status_placeholder:
                status_placeholder.markdown(f"📊 **{code} ({stock_name})**\n\n{message}")
            time.sleep(0.1)  # UI更新のため
        
        result = analyzer.analyze_stock(code, save_data=True, progress_callback=update_progress)
        
        if result:
            # EDINETデータ取得の進捗はprogress_callbackで表示されるため、ここでは完了表示のみ
            edinet_data = result.get("edinet_data", {})
            if progress_bar:
                progress_bar.progress(85)
            
            # analyze_stockの結果を直接使用してレポートデータを構築
            # get_report_dataは内部で再度analyze_stockを呼び出すため、結果を再利用
            comparison = analyzer.compare_with_previous(code) if hasattr(analyzer, 'compare_with_previous') else None
            
            report_data = {
                **result,
                "comparison": comparison,
                "quarterly_metrics": None,
            }
            
            if report_data:
                # EDINETデータの詳細はprogress_callbackで表示されるため、ここでは完了表示のみ
                if progress_bar:
                    progress_bar.progress(90)
                
                if status_placeholder:
                    status_placeholder.markdown(f"✅ **{code} ({stock_name}) の分析完了**")
                if progress_bar:
                    progress_bar.progress(95)
                
                return report_data
            else:
                error_message = f"銘柄コード {code}: レポートデータの構築に失敗しました。"
                st.error(error_message)
                raise ValueError(error_message)
        else:
            # 年度データ抽出を直接試行して原因を特定
            try:
                from src.utils.financial_data import extract_annual_data
                annual_data_test = extract_annual_data(financial_data)
                if not annual_data_test:
                    error_message = f"銘柄コード {code} ({stock_name if stock_name else '不明'}): 年度データが抽出できませんでした。財務データは {len(financial_data)}件取得できましたが、有効な年度データがありません。"
                else:
                    error_message = f"銘柄コード {code} ({stock_name if stock_name else '不明'}): 年度データは {len(annual_data_test)}件抽出できましたが、指標計算で失敗した可能性があります。"
            except Exception as e:
                error_message = f"銘柄コード {code} ({stock_name if stock_name else '不明'}): 年度データ抽出中にエラーが発生しました - {str(e)}"
            st.error(error_message)
            raise ValueError(error_message)
    
    except Exception as e:
        if not error_message:
            import traceback
            error_detail = traceback.format_exc()
            error_message = f"銘柄コード {code}: 予期しないエラーが発生しました - {str(e)}"
            # デバッグ用に詳細をログに出力
            import logging
            logging.error(f"銘柄コード {code} の分析エラー詳細:\n{error_detail}")
        # エラーが発生した場合は処理を中断
        raise

