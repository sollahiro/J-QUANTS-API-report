"""
グラフ生成モジュール

Plotlyグラフの生成を提供します。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import plotly.graph_objects as go
import plotly.io as pio

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraphGenerator:
    """グラフ生成クラス（Streamlit用）"""
    
    def __init__(self):
        """
        初期化
        """
        pass
    
    def _create_interactive_graphs(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        HTML用のインタラクティブグラフを作成（新構成：6グラフ）
        
        Args:
            result: 分析結果の辞書
            
        Returns:
            グラフ情報のリスト（PlotlyのHTMLを含む）
        """
        metrics = result.get("metrics", {})
        years = metrics.get("years", [])
        
        if not years:
            return []
        
        # 年度計算を一度だけ実行して、yearsデータにfiscal_yearを追加
        def extract_fiscal_year_from_fy_end(fy_end):
            """年度終了日から年度を抽出（共通関数）"""
            if not fy_end:
                return ""
            try:
                if isinstance(fy_end, str):
                    if len(fy_end) >= 10:
                        from datetime import datetime
                        period_date = datetime.strptime(fy_end[:10], "%Y-%m-%d")
                        # 3月末が年度終了日の場合、その年度は前年
                        if period_date.month == 3:
                            fiscal_year = period_date.year - 1
                        else:
                            fiscal_year = period_date.year
                        return f"{fiscal_year}年度"
                    elif len(fy_end) >= 4:
                        year = int(fy_end[:4])
                        return f"{year}年度"
            except (ValueError, TypeError):
                pass
            return ""
        
        # 年度を事前計算してyearsデータに追加（一度だけ計算）
        for year in years:
            if "fiscal_year" not in year:
                year["fiscal_year"] = extract_fiscal_year_from_fy_end(year.get("fy_end", ""))
        
        fy_ends = [year.get("fy_end") for year in years]
        fiscal_years = [year.get("fiscal_year", "") for year in years]  # 事前計算済みの値を使用
        
        # グラフの年度軸を古い→新しいの順に変更（左右を入れ替え）
        # yearsデータは新しい順（最新が先頭）なので、逆順にする
        # 年度を数値として抽出してソートする
        def extract_year_number(fiscal_year_str):
            """年度文字列から数値を抽出（例: "2024年度" -> 2024）"""
            if not fiscal_year_str:
                return 0
            try:
                # "2024年度"から"2024"を抽出
                year_str = fiscal_year_str.replace("年度", "").strip()
                return int(year_str)
            except (ValueError, TypeError):
                return 0
        
        # 年度とデータをペアにして、年度の数値順でソート
        year_data_pairs = list(zip(fiscal_years, fy_ends, years))
        # 年度の数値でソート（古い順）
        year_data_pairs.sort(key=lambda x: extract_year_number(x[0]))
        
        # ソート後のデータを分離
        reversed_fiscal_years = [pair[0] for pair in year_data_pairs]
        reversed_fy_ends = [pair[1] for pair in year_data_pairs]
        reversed_years = [pair[2] for pair in year_data_pairs]
        
        graphs = []
        
        # データを取得（年度軸の順序に合わせてソート済みの順序で取得）
        fcf_values = [year.get("fcf") for year in reversed_years]
        roe_values = [year.get("roe") for year in reversed_years]
        eps_values = [year.get("eps") for year in reversed_years]
        per_values = [year.get("per") for year in reversed_years]
        pbr_values = [year.get("pbr") for year in reversed_years]
        op_values = [year.get("op") for year in reversed_years]
        cfo_values = [year.get("cfo") for year in reversed_years]
        cfi_values = [year.get("cfi") for year in reversed_years]
        eq_values = [year.get("eq") for year in reversed_years]
        np_values = [year.get("np") for year in reversed_years]
        bps_values = [year.get("bps") for year in reversed_years]
        payout_ratio_values = [year.get("payout_ratio") for year in reversed_years]
        
        # HTML変換用のヘルパー関数
        def try_convert_to_html(fig, section_title, graph_title="", width="full"):
            """グラフをHTMLに変換してリストに追加"""
            try:
                html_div = pio.to_html(fig, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
                graph_obj = {
                    "section_title": section_title,
                    "title": graph_title if graph_title else section_title,
                    "html": html_div,
                    "type": "interactive",
                    "width": width
                }
                graphs.append(graph_obj)
            except Exception as e:
                logger.warning(f"インタラクティブグラフ生成失敗 ({section_title}): {e}")
        
        # None値を除外して有効な値だけを繋げる
        def filter_none_values(x_list, y_list, hover_list=None):
            """None値を除外したx, y, hoverのリストを返す"""
            filtered_x = []
            filtered_y = []
            filtered_hover = []
            for i, (x, y) in enumerate(zip(x_list, y_list)):
                if y is not None:
                    filtered_x.append(x)
                    filtered_y.append(y)
                    if hover_list and i < len(hover_list):
                        filtered_hover.append(hover_list[i])
            return filtered_x, filtered_y, filtered_hover if hover_list else (filtered_x, filtered_y)
        
        # 値を百万円単位に変換する関数（J-Quants APIのデータは円単位）
        def to_million(val):
            """値を百万円単位に変換（APIデータは円単位なので1000000で割る）"""
            if val is None:
                return None
            return val / 1000000 if val != 0 else 0
        
        # 年度を抽出する関数（年度終了日から年度を計算）
        def extract_fiscal_year(fy_end):
            """
            年度終了日から年度を抽出
            
            Args:
                fy_end: 年度終了日（YYYY-MM-DD形式）
            
            Returns:
                年度（YYYY年度形式の文字列）、抽出できない場合は空文字列
            """
            if not fy_end:
                return ""
            try:
                if isinstance(fy_end, str):
                    if len(fy_end) >= 10:
                        # YYYY-MM-DD形式から年度を計算
                        from datetime import datetime
                        period_date = datetime.strptime(fy_end[:10], "%Y-%m-%d")
                        # 3月末が年度終了日の場合、その年度は前年
                        if period_date.month == 3:
                            fiscal_year = period_date.year - 1
                        else:
                            fiscal_year = period_date.year
                        return f"{fiscal_year}年度"
                    elif len(fy_end) >= 4:
                        # YYYY形式のみの場合
                        year = int(fy_end[:4])
                        return f"{year}年度"
            except (ValueError, TypeError):
                pass
            return ""
        
        # 後方互換性のため、extract_yearも残す（グラフ用）
        def extract_year(fy_end):
            """年度終了日から年度を抽出（グラフ用、YYYY形式）"""
            fiscal_year_str = extract_fiscal_year(fy_end)
            if fiscal_year_str:
                # "2024年度"から"2024"を抽出
                return fiscal_year_str.replace("年度", "")
            return ""
        
        # 有効な値かチェック
        def is_valid_value(value):
            """値が有効かチェック（None、NaNなどを除外）"""
            if value is None:
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
            except (ValueError, TypeError):
                return False
            return True
        
        from plotly.subplots import make_subplots
        
        # ========================================
        # 【事業の実力】
        # ========================================
        
        # グラフ1：事業効率（簡易ROIC × CF変換率）
        # 簡易ROIC = OP / Eq
        # CF変換率 = CFO / OP
        roic_values = []
        cf_conversion_values = []
        for i in range(len(years)):
            op = op_values[i] if i < len(op_values) else None
            eq = eq_values[i] if i < len(eq_values) else None
            cfo = cfo_values[i] if i < len(cfo_values) else None
            
            # 簡易ROIC計算
            roic = None
            if op is not None and eq is not None and eq != 0:
                roic = (op / eq) * 100  # パーセント表示
            roic_values.append(roic)
            
            # CF変換率計算
            cf_conversion = None
            if cfo is not None and op is not None and op != 0:
                cf_conversion = (cfo / op) * 100  # パーセント表示
            cf_conversion_values.append(cf_conversion)
        
        # グラフ作成（2軸折れ線グラフ）
        fig_business_efficiency = make_subplots(specs=[[{"secondary_y": True}]])
        
        roic_x, roic_y = filter_none_values(reversed_fiscal_years, roic_values)[:2]
        fig_business_efficiency.add_trace(
            go.Scatter(
                x=roic_x,
                y=roic_y,
                mode='lines+markers',
                name='簡易ROIC (%)',
                line=dict(color='#1f77b4', width=3),
                marker=dict(size=8),
                hovertemplate='<b>%{x}</b><br>簡易ROIC: %{y:.2f}%<extra></extra>'
            ),
            secondary_y=False
        )
        
        cf_conversion_x, cf_conversion_y = filter_none_values(reversed_fiscal_years, cf_conversion_values)[:2]
        fig_business_efficiency.add_trace(
            go.Scatter(
                x=cf_conversion_x,
                y=cf_conversion_y,
                mode='lines+markers',
                name='CF変換率 (%)',
                line=dict(color='#ff7f0e', width=3),
                marker=dict(size=8),
                hovertemplate='<b>%{x}</b><br>CF変換率: %{y:.2f}%<extra></extra>'
            ),
            secondary_y=True
        )
        
        fig_business_efficiency.update_xaxes(
            title_text="年度",
            categoryorder='array',
            categoryarray=reversed_fiscal_years
        )
        fig_business_efficiency.update_yaxes(title_text="簡易ROIC (%)", secondary_y=False)
        fig_business_efficiency.update_yaxes(title_text="CF変換率 (%)", secondary_y=True)
        fig_business_efficiency.update_layout(
            title="",
            height=500,
            hovermode='x unified',
            font=dict(size=14),
            template="plotly_white"
        )
        
        html_div_be = pio.to_html(fig_business_efficiency, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
        graph_obj_be = {
            "section_title": "事業効率",
            "title": "簡易ROIC＝営業利益/純資産<br>CF変換率＝営業CF/営業利益",
            "html": html_div_be,
            "type": "interactive",
            "width": "full"
        }
        graphs.append(graph_obj_be)
        
        # グラフ2：キャッシュフロー（営業CF + 投資CF + FCF）
        fig_cashflow = go.Figure()
        
        # 営業CF（棒グラフ、プラス/マイナス両対応）
        cfo_x, cfo_y = filter_none_values(reversed_fiscal_years, cfo_values)[:2]
        cfo_y_million = [to_million(y) for y in cfo_y]
        fig_cashflow.add_trace(go.Bar(
            x=cfo_x,
            y=cfo_y,
            name="営業CF",
            marker_color="#17becf",
            customdata=cfo_y_million,
            hovertemplate='<b>%{x}</b><br>営業CF: %{customdata:,.0f}百万円<extra></extra>'
        ))
        
        # 投資CF（棒グラフ、プラス/マイナス両対応）
        cfi_x, cfi_y = filter_none_values(reversed_fiscal_years, cfi_values)[:2]
        cfi_y_million = [to_million(y) for y in cfi_y]
        fig_cashflow.add_trace(go.Bar(
            x=cfi_x,
            y=cfi_y,
            name="投資CF",
            marker_color="#bcbd22",
            customdata=cfi_y_million,
            hovertemplate='<b>%{x}</b><br>投資CF: %{customdata:,.0f}百万円<extra></extra>'
        ))
        
        # FCF（折れ線グラフ）
        fcf_x, fcf_y = filter_none_values(reversed_fiscal_years, fcf_values)[:2]
        fcf_y_million = [to_million(y) for y in fcf_y]
        fig_cashflow.add_trace(go.Scatter(
            x=fcf_x,
            y=fcf_y,
            mode="lines+markers",
            name="FCF",
            line=dict(color="#1e3a8a", width=4),
            marker=dict(size=10),
            customdata=fcf_y_million,
            hovertemplate='<b>%{x}</b><br>FCF: %{customdata:,.0f}百万円<extra></extra>'
        ))
        
        # FCF=0の基準線
        fig_cashflow.add_hline(y=0, line_dash="dash", line_color="red", line_width=2)
        
        fig_cashflow.update_xaxes(
            title_text="年度",
            categoryorder='array',
            categoryarray=reversed_fiscal_years
        )
        fig_cashflow.update_yaxes(title_text="金額 (円)")
        fig_cashflow.update_layout(
            title="",
            template="plotly_white",
            height=500,
            margin=dict(l=60, r=30, t=60, b=60),
            font=dict(size=16),
            hovermode='x unified',
            barmode='group'
        )
        
        html_div_cf = pio.to_html(fig_cashflow, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
        graphs.append({
            "section_title": "キャッシュフロー",
            "title": "FCF＝営業CF＋投資CF",
            "html": html_div_cf,
            "type": "interactive",
            "width": "full"
        })
        
        # ========================================
        # 【株主価値と市場評価】
        # ========================================
        
        # グラフ3：株主価値の蓄積（EPS × BPS × ROE）
        # 表示順序：EPS → BPS → ROE
        hover_texts_eps = []
        hover_texts_bps = []
        hover_texts_roe = []
        for i, fiscal_year in enumerate(reversed_fiscal_years):
            if i == 0:
                eps_text = f"<b>{fiscal_year}</b><br>EPS: {eps_values[i]:.2f}円" if eps_values[i] is not None else f"<b>{fiscal_year}</b><br>EPS: N/A"
                bps_text = f"<b>{fiscal_year}</b><br>BPS: {bps_values[i]:.2f}円" if bps_values[i] is not None else f"<b>{fiscal_year}</b><br>BPS: N/A"
                roe_text = f"<b>{fiscal_year}</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{fiscal_year}</b><br>ROE: N/A"
                hover_texts_eps.append(eps_text)
                hover_texts_bps.append(bps_text)
                hover_texts_roe.append(roe_text)
            else:
                eps_diff = eps_values[i] - eps_values[i-1] if eps_values[i] is not None and eps_values[i-1] is not None else None
                bps_diff = bps_values[i] - bps_values[i-1] if bps_values[i] is not None and bps_values[i-1] is not None else None
                roe_diff = roe_values[i] - roe_values[i-1] if roe_values[i] is not None and roe_values[i-1] is not None else None
                
                eps_text = f"<b>{fiscal_year}</b><br>EPS: {eps_values[i]:.2f}円 ({eps_diff:+.2f}円)" if eps_values[i] is not None and eps_diff is not None else (f"<b>{fiscal_year}</b><br>EPS: {eps_values[i]:.2f}円" if eps_values[i] is not None else f"<b>{fiscal_year}</b><br>EPS: N/A")
                bps_text = f"<b>{fiscal_year}</b><br>BPS: {bps_values[i]:.2f}円 ({bps_diff:+.2f}円)" if bps_values[i] is not None and bps_diff is not None else (f"<b>{fiscal_year}</b><br>BPS: {bps_values[i]:.2f}円" if bps_values[i] is not None else f"<b>{fiscal_year}</b><br>BPS: N/A")
                roe_text = f"<b>{fiscal_year}</b><br>ROE: {roe_values[i]:.2f}% ({roe_diff:+.2f}%)" if roe_values[i] is not None and roe_diff is not None else (f"<b>{fiscal_year}</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{fiscal_year}</b><br>ROE: N/A")
                hover_texts_eps.append(eps_text)
                hover_texts_bps.append(bps_text)
                hover_texts_roe.append(roe_text)
        
        # グラフ作成（EPS/BPS: 左軸、ROE: 右軸）
        fig_shareholder_value = make_subplots(specs=[[{"secondary_y": True}]])
        
        # EPS（左軸、表示順序1）
        eps_x, eps_y, eps_hover = filter_none_values(reversed_fiscal_years, eps_values, hover_texts_eps)
        fig_shareholder_value.add_trace(
            go.Scatter(
                x=eps_x,
                y=eps_y,
                mode='lines+markers',
                name='EPS (円)',
                line=dict(color='#2ca02c', width=3),
                marker=dict(size=8),
                hovertext=eps_hover if eps_hover else None,
                hoverinfo='text' if eps_hover else 'y'
            ),
            secondary_y=False
        )
        
        # BPS（左軸、EPSと同じ軸、表示順序2）
        if any(bps is not None for bps in bps_values):
            bps_x, bps_y, bps_hover = filter_none_values(reversed_fiscal_years, bps_values, hover_texts_bps)
            fig_shareholder_value.add_trace(
                go.Scatter(
                    x=bps_x,
                    y=bps_y,
                    mode='lines+markers',
                    name='BPS (円)',
                    line=dict(color='#9467bd', width=3),
                    marker=dict(size=8),
                    hovertext=bps_hover if bps_hover else None,
                    hoverinfo='text' if bps_hover else 'y'
                ),
                secondary_y=False  # EPSと同じ左軸
            )
        
        # ROE（右軸、表示順序3）
        roe_x, roe_y, roe_hover = filter_none_values(reversed_fiscal_years, roe_values, hover_texts_roe)
        fig_shareholder_value.add_trace(
            go.Scatter(
                x=roe_x,
                y=roe_y,
                mode='lines+markers',
                name='ROE (%)',
                line=dict(color='#ff7f0e', width=3),
                marker=dict(size=8),
                hovertext=roe_hover if roe_hover else None,
                hoverinfo='text' if roe_hover else 'y'
            ),
            secondary_y=True
        )
        
        fig_shareholder_value.update_xaxes(
            title_text="年度",
            categoryorder='array',
            categoryarray=reversed_fiscal_years
        )
        fig_shareholder_value.update_yaxes(title_text="EPS / BPS (円)", secondary_y=False)
        fig_shareholder_value.update_yaxes(title_text="ROE (%)", secondary_y=True)
        fig_shareholder_value.update_layout(
            title="",
            height=500,
            hovermode='x unified',
            font=dict(size=14),
            template="plotly_white"
        )
        
        html_div_sv = pio.to_html(fig_shareholder_value, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
        graph_obj_sv = {
            "section_title": "株主価値の蓄積",
            "title": "EPS＝1株当たり純利益<br>BPS＝1株当たり純資産<br>ROE＝当期純利益/純資産<br>（EPS÷BPS＝ROE）",
            "html": html_div_sv,
            "type": "interactive",
            "width": "full"
        }
        graphs.append(graph_obj_sv)
        
        # グラフ4：配当政策と市場評価（配当性向 × ROE × PBR）
        hover_texts_payout = []
        hover_texts_roe4 = []
        hover_texts_pbr4 = []
        for i, fiscal_year in enumerate(reversed_fiscal_years):
            payout = payout_ratio_values[i] if i < len(payout_ratio_values) else None
            roe = roe_values[i] if i < len(roe_values) else None
            pbr = pbr_values[i] if i < len(pbr_values) else None
            
            if i == 0:
                payout_text = f"<b>{fiscal_year}</b><br>配当性向: {payout:.2f}%" if payout is not None else f"<b>{fiscal_year}</b><br>配当性向: N/A"
                roe_text = f"<b>{fiscal_year}</b><br>ROE: {roe:.2f}%" if roe is not None else f"<b>{fiscal_year}</b><br>ROE: N/A"
                pbr_text = f"<b>{fiscal_year}</b><br>PBR: {pbr:.2f}倍" if pbr is not None else f"<b>{fiscal_year}</b><br>PBR: N/A"
                hover_texts_payout.append(payout_text)
                hover_texts_roe4.append(roe_text)
                hover_texts_pbr4.append(pbr_text)
            else:
                payout_diff = payout_ratio_values[i] - payout_ratio_values[i-1] if payout_ratio_values[i] is not None and payout_ratio_values[i-1] is not None else None
                roe_diff = roe_values[i] - roe_values[i-1] if roe_values[i] is not None and roe_values[i-1] is not None else None
                pbr_diff = pbr_values[i] - pbr_values[i-1] if pbr_values[i] is not None and pbr_values[i-1] is not None else None
                
                payout_text = f"<b>{fiscal_year}</b><br>配当性向: {payout:.2f}% ({payout_diff:+.2f}%)" if payout is not None and payout_diff is not None else (f"<b>{fiscal_year}</b><br>配当性向: {payout:.2f}%" if payout is not None else f"<b>{fiscal_year}</b><br>配当性向: N/A")
                roe_text = f"<b>{fiscal_year}</b><br>ROE: {roe:.2f}% ({roe_diff:+.2f}%)" if roe is not None and roe_diff is not None else (f"<b>{fiscal_year}</b><br>ROE: {roe:.2f}%" if roe is not None else f"<b>{fiscal_year}</b><br>ROE: N/A")
                pbr_text = f"<b>{fiscal_year}</b><br>PBR: {pbr:.2f}倍 ({pbr_diff:+.2f}倍)" if pbr is not None and pbr_diff is not None else (f"<b>{fiscal_year}</b><br>PBR: {pbr:.2f}倍" if pbr is not None else f"<b>{fiscal_year}</b><br>PBR: N/A")
                hover_texts_payout.append(payout_text)
                hover_texts_roe4.append(roe_text)
                hover_texts_pbr4.append(pbr_text)
        
        # グラフ作成（配当性向: 左軸、ROE/PBR: 右軸）
        fig_dividend_policy = make_subplots(specs=[[{"secondary_y": True}]])
        
        # 配当性向（左軸）
        payout_x, payout_y, payout_hover = filter_none_values(reversed_fiscal_years, payout_ratio_values, hover_texts_payout)
        fig_dividend_policy.add_trace(
            go.Scatter(
                x=payout_x,
                y=payout_y,
                mode='lines+markers',
                name='配当性向 (%)',
                line=dict(color='#d62728', width=3),
                marker=dict(size=8),
                hovertext=payout_hover if payout_hover else None,
                hoverinfo='text' if payout_hover else 'y'
            ),
            secondary_y=False
        )
        
        # ROE（右軸）
        roe4_x, roe4_y, roe4_hover = filter_none_values(reversed_fiscal_years, roe_values, hover_texts_roe4)
        fig_dividend_policy.add_trace(
            go.Scatter(
                x=roe4_x,
                y=roe4_y,
                mode='lines+markers',
                name='ROE (%)',
                line=dict(color='#ff7f0e', width=3),
                marker=dict(size=8),
                hovertext=roe4_hover if roe4_hover else None,
                hoverinfo='text' if roe4_hover else 'y'
            ),
            secondary_y=True
        )
        
        # PBR（右軸、ROEと同じ軸）
        pbr4_x, pbr4_y, pbr4_hover = filter_none_values(reversed_fiscal_years, pbr_values, hover_texts_pbr4)
        fig_dividend_policy.add_trace(
            go.Scatter(
                x=pbr4_x,
                y=pbr4_y,
                mode='lines+markers',
                name='PBR (倍)',
                line=dict(color='#8c564b', width=3),
                marker=dict(size=8),
                hovertext=pbr4_hover if pbr4_hover else None,
                hoverinfo='text' if pbr4_hover else 'y'
            ),
            secondary_y=True  # ROEと同じ右軸
        )
        
        fig_dividend_policy.update_xaxes(
            title_text="年度",
            categoryorder='array',
            categoryarray=reversed_fiscal_years
        )
        fig_dividend_policy.update_yaxes(title_text="配当性向 (%)", secondary_y=False)
        fig_dividend_policy.update_yaxes(title_text="ROE (%) / PBR (倍)", secondary_y=True)
        fig_dividend_policy.update_layout(
            title="",
            height=500,
            hovermode='x unified',
            font=dict(size=14),
            template="plotly_white"
        )
        
        html_div_dp = pio.to_html(fig_dividend_policy, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
        graph_obj_dp = {
            "section_title": "配当政策と市場評価",
            "title": "配当性向＝配当総額/当期純利益<br>ROE＝当期純利益/純資産<br>PBR＝株価/BPS",
            "html": html_div_dp,
            "type": "interactive",
            "width": "full"
        }
        graphs.append(graph_obj_dp)
        
        # グラフ5：市場評価（PER × ROE × PBR）
        # 表示順序：PER → ROE → PBR
        hover_texts_per = []
        hover_texts_roe5 = []
        hover_texts_pbr5 = []
        for i, fiscal_year in enumerate(reversed_fiscal_years):
            if i == 0:
                per_text = f"<b>{fiscal_year}</b><br>PER: {per_values[i]:.2f}倍" if per_values[i] is not None else f"<b>{fiscal_year}</b><br>PER: N/A"
                roe_text = f"<b>{fiscal_year}</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{fiscal_year}</b><br>ROE: N/A"
                pbr_text = f"<b>{fiscal_year}</b><br>PBR: {pbr_values[i]:.2f}倍" if pbr_values[i] is not None else f"<b>{fiscal_year}</b><br>PBR: N/A"
                hover_texts_per.append(per_text)
                hover_texts_roe5.append(roe_text)
                hover_texts_pbr5.append(pbr_text)
            else:
                per_diff = per_values[i] - per_values[i-1] if per_values[i] is not None and per_values[i-1] is not None else None
                roe_diff = roe_values[i] - roe_values[i-1] if roe_values[i] is not None and roe_values[i-1] is not None else None
                pbr_diff = pbr_values[i] - pbr_values[i-1] if pbr_values[i] is not None and pbr_values[i-1] is not None else None
                
                per_text = f"<b>{fiscal_year}</b><br>PER: {per_values[i]:.2f}倍 ({per_diff:+.2f}倍)" if per_values[i] is not None and per_diff is not None else (f"<b>{fiscal_year}</b><br>PER: {per_values[i]:.2f}倍" if per_values[i] is not None else f"<b>{fiscal_year}</b><br>PER: N/A")
                roe_text = f"<b>{fiscal_year}</b><br>ROE: {roe_values[i]:.2f}% ({roe_diff:+.2f}%)" if roe_values[i] is not None and roe_diff is not None else (f"<b>{fiscal_year}</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{fiscal_year}</b><br>ROE: N/A")
                pbr_text = f"<b>{fiscal_year}</b><br>PBR: {pbr_values[i]:.2f}倍 ({pbr_diff:+.2f}倍)" if pbr_values[i] is not None and pbr_diff is not None else (f"<b>{fiscal_year}</b><br>PBR: {pbr_values[i]:.2f}倍" if pbr_values[i] is not None else f"<b>{fiscal_year}</b><br>PBR: N/A")
                hover_texts_per.append(per_text)
                hover_texts_roe5.append(roe_text)
                hover_texts_pbr5.append(pbr_text)
        
        # グラフ作成（PER/PBR: 左軸、ROE: 右軸）
        fig_market_valuation = make_subplots(specs=[[{"secondary_y": True}]])
        
        # PER（左軸、表示順序1）
        per_x, per_y, per_hover = filter_none_values(reversed_fiscal_years, per_values, hover_texts_per)
        fig_market_valuation.add_trace(
            go.Scatter(
                x=per_x,
                y=per_y,
                mode='lines+markers',
                name='PER (倍)',
                line=dict(color='#9467bd', width=3),
                marker=dict(size=8),
                hovertext=per_hover if per_hover else None,
                hoverinfo='text' if per_hover else 'y'
            ),
            secondary_y=False
        )
        
        # PBR（左軸、PERと同じ軸、表示順序2）
        pbr5_x, pbr5_y, pbr5_hover = filter_none_values(reversed_fiscal_years, pbr_values, hover_texts_pbr5)
        fig_market_valuation.add_trace(
            go.Scatter(
                x=pbr5_x,
                y=pbr5_y,
                mode='lines+markers',
                name='PBR (倍)',
                line=dict(color='#8c564b', width=3),
                marker=dict(size=8),
                hovertext=pbr5_hover if pbr5_hover else None,
                hoverinfo='text' if pbr5_hover else 'y'
            ),
            secondary_y=False  # PERと同じ左軸
        )
        
        # ROE（右軸、表示順序3）
        roe5_x, roe5_y, roe5_hover = filter_none_values(reversed_fiscal_years, roe_values, hover_texts_roe5)
        fig_market_valuation.add_trace(
            go.Scatter(
                x=roe5_x,
                y=roe5_y,
                mode='lines+markers',
                name='ROE (%)',
                line=dict(color='#ff7f0e', width=3),
                marker=dict(size=8),
                hovertext=roe5_hover if roe5_hover else None,
                hoverinfo='text' if roe5_hover else 'y'
            ),
            secondary_y=True
        )
        
        # PBR=1の基準線
        fig_market_valuation.add_hline(y=1, line_dash="dash", line_color="gray", line_width=1, secondary_y=False)
        
        fig_market_valuation.update_xaxes(
            title_text="年度",
            categoryorder='array',
            categoryarray=reversed_fiscal_years
        )
        fig_market_valuation.update_yaxes(title_text="PER (倍) / PBR (倍)", secondary_y=False)
        fig_market_valuation.update_yaxes(title_text="ROE (%)", secondary_y=True)
        fig_market_valuation.update_layout(
            title="",
            height=500,
            hovermode='x unified',
            font=dict(size=14),
            template="plotly_white"
        )
        
        html_div_mv = pio.to_html(fig_market_valuation, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
        graph_obj_mv = {
            "section_title": "市場評価",
            "title": "PER＝株価/EPS<br>ROE＝当期純利益/純資産<br>PBR＝株価/BPS<br>（PER×ROE＝PBR）",
            "html": html_div_mv,
            "type": "interactive",
            "width": "full"
        }
        graphs.append(graph_obj_mv)
        
        # 5. 株価 vs EPS（指数化比較）
        from ..utils.financial_data import get_fiscal_year_end_price
        from ..api.client import JQuantsAPIClient
        
        code = result.get("code")
        name = result.get("name", "")
        
        # APIクライアントを新規作成
        try:
            api_client = JQuantsAPIClient()
        except Exception as e:
            logger.warning(f"APIクライアント作成失敗（グラフ4スキップ）: {e}")
            api_client = None
        
        # 株価データ取得（年度末終値）
        stock_prices = []
        stock_years = []
        aligned_fy_ends = []
        aligned_eps = []
        
        if api_client:
            # 逆順にしたデータを使用
            for i, fy_end in enumerate(reversed_fy_ends):
                eps = eps_values[i] if i < len(eps_values) else None
                fiscal_year_str = reversed_fiscal_years[i] if i < len(reversed_fiscal_years) else "不明"  # 事前計算済みの値を使用
                
                if fy_end and eps is not None:
                    price = get_fiscal_year_end_price(api_client, code, fy_end)
                    if price:
                        stock_prices.append(price)
                        stock_years.append(fiscal_year_str)
                        aligned_fy_ends.append(fy_end)
                        aligned_eps.append(eps)
                    else:
                        logger.warning(f"株価 vs EPS: 年度{i} ({fiscal_year_str}): 株価取得失敗（fy_end={fy_end}）")
                else:
                    if not fy_end:
                        logger.warning(f"株価 vs EPS: 年度{i} ({fiscal_year_str}): fy_endが存在しない")
                    if eps is None:
                        logger.warning(f"株価 vs EPS: 年度{i} ({fiscal_year_str}): EPSがNone")
        
        if len(stock_prices) > 0 and len(aligned_eps) > 0:
            # 指数化（一番古い年を起点=100）
            # aligned_fy_endsから年度を抽出して、最も古い年度を特定
            # 年度とインデックスのペアを作成
            year_data_list = []
            for i, fy_end in enumerate(aligned_fy_ends):
                try:
                    # YYYY-MM-DD形式またはYYYYMMDD形式から年度を抽出
                    if fy_end and len(fy_end) >= 4:
                        year_str = fy_end[:4] if '-' not in fy_end[:4] else fy_end.split('-')[0]
                        year_int = int(year_str)
                        year_data_list.append({
                            'year': year_int,
                            'index': i,
                            'fy_end': fy_end,
                            'year_str': year_str
                        })
                except (ValueError, TypeError, AttributeError):
                    continue
            
            if year_data_list:
                # 最も古い年のデータを取得
                oldest_data = min(year_data_list, key=lambda x: x['year'])
                oldest_index = oldest_data['index']
                oldest_price = stock_prices[oldest_index]
                oldest_eps = aligned_eps[oldest_index]
                oldest_year = oldest_data['year_str']
            else:
                # フォールバック: 最後の要素を使用
                oldest_index = len(stock_prices) - 1
                oldest_price = stock_prices[oldest_index]
                oldest_eps = aligned_eps[oldest_index]
                oldest_year = stock_years[oldest_index] if stock_years else "不明"
                logger.warning(f"株価 vs EPS 指数化比較: 年度抽出失敗、フォールバック使用（インデックス={oldest_index}, 年度={oldest_year}）")
            
            price_index = [(p / oldest_price) * 100 for p in stock_prices]
            eps_index = [(e / oldest_eps) * 100 for e in aligned_eps]
            
            # PERの計算と指数化
            per_values = []
            for i, (price, eps) in enumerate(zip(stock_prices, aligned_eps)):
                if eps is not None and eps > 0:
                    per = price / eps
                    per_values.append(per)
                else:
                    per_values.append(None)
            
            # 基準年のPERを取得
            oldest_per = None
            if oldest_price and oldest_eps and oldest_eps > 0:
                oldest_per = oldest_price / oldest_eps
            
            # PER指数の計算
            per_index = []
            if oldest_per and oldest_per > 0:
                for per in per_values:
                    if per is not None:
                        per_idx = (per / oldest_per) * 100
                        per_index.append(per_idx)
                    else:
                        per_index.append(None)
            else:
                per_index = [None] * len(per_values)
            
            # reversed_fy_endsから取得したデータは既に古い→新しいの順なので、そのまま使用
            # （reversed()を適用しない）
            
            # グラフ作成
            fig_price_eps = go.Figure()
            
            # 株価指数
            fig_price_eps.add_trace(go.Scatter(
                x=stock_years,  # 既に古い→新しいの順
                y=price_index,
                mode='lines+markers',
                name='株価指数',
                line=dict(width=3, color='blue'),
                marker=dict(size=10),
                hovertemplate='<b>%{x}</b><br>株価指数: %{y:.1f}<br>実際の株価: ¥%{customdata:.0f}<extra></extra>',
                customdata=stock_prices
            ))
            
            # EPS指数
            fig_price_eps.add_trace(go.Scatter(
                x=stock_years,  # 既に古い→新しいの順
                y=eps_index,
                mode='lines+markers',
                name='EPS指数',
                line=dict(width=3, color='green'),
                marker=dict(size=10),
                hovertemplate='<b>%{x}</b><br>EPS指数: %{y:.1f}<br>実際のEPS: ¥%{customdata:.2f}<extra></extra>',
                customdata=aligned_eps
            ))
            
            # PER指数
            fig_price_eps.add_trace(go.Scatter(
                x=stock_years,  # 既に古い→新しいの順
                y=per_index,
                mode='lines+markers',
                name='PER指数',
                line=dict(width=3, color='orange'),
                marker=dict(size=10),
                hovertemplate='<b>%{x}</b><br>PER指数: %{y:.1f}<br>実際のPER: %{customdata:.2f}倍<extra></extra>',
                customdata=per_values
            ))
            
            # 基準線（100）
            fig_price_eps.add_hline(y=100, line_dash="dash", line_color="gray", 
                                  annotation_text="起点（100）", annotation_position="right")
            
            # レイアウト
            fig_price_eps.update_layout(
                title="",
                xaxis=dict(title='年度'),
                yaxis=dict(title='指数（起点=100）'),
                hovermode='x unified',
                height=500,
                legend=dict(x=0.02, y=0.98),
                template="plotly_white",
                font=dict(size=14)
            )
            
            html_div_pe = pio.to_html(fig_price_eps, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
            graphs.append({
                "section_title": "株価とEPSの乖離",
                "title": "株価指数＝(現在株価/基準年株価)×100<br>EPS指数＝(現在EPS/基準年EPS)×100<br>PER指数＝(現在PER/基準年PER)×100",
                "html": html_div_pe,
                "type": "interactive",
                "width": "full"
            })
        
        return graphs


