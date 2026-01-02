"""
HTMLレポート生成モジュール
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

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False



def calculate_cagr(start_value, end_value, years):
    """CAGR（年平均成長率）を計算
    
    負の値から正の値への変化（またはその逆）も評価可能。
    符号が異なる場合は、符号変化を考慮した評価を行う。
    """
    if start_value is None or end_value is None:
        return None
    if years <= 0:
        return None
    
    # 符号が同じ場合（両方正または両方負）
    if (start_value > 0 and end_value > 0) or (start_value < 0 and end_value < 0):
        # 通常のCAGR計算（両方とも0でないことを確認）
        if start_value == 0 or end_value == 0:
            return None
        return (pow(end_value / start_value, 1 / years) - 1) * 100
    
    # 符号が異なる場合
    # 負から正への変化: 改善を示す（大きな正の成長率として扱う）
    # 正から負への変化: 悪化を示す（大きな負の成長率として扱う）
    if start_value < 0 and end_value > 0:
        # 負から正への変化: 絶対値の変化率を計算し、正の値として扱う
        # 例: -9.31 → 38.44 の場合、絶対値の変化率を計算
        abs_start = abs(start_value)
        abs_end = abs(end_value)
        if abs_start == 0:
            return None
        # 符号変化を考慮して、正の成長率として扱う
        # 絶対値の変化率を計算（必ず正の値になる）
        return abs((pow(abs_end / abs_start, 1 / years) - 1) * 100)
    elif start_value > 0 and end_value < 0:
        # 正から負への変化: 絶対値の変化率を計算し、負の値として扱う
        abs_start = abs(start_value)
        abs_end = abs(end_value)
        if abs_start == 0:
            return None
        # 符号変化を考慮して、負の成長率として扱う
        # 絶対値の変化率を計算し、負の符号を付ける
        return -abs((pow(abs_end / abs_start, 1 / years) - 1) * 100)
    
    # どちらかが0の場合
    return None


class HTMLReportGenerator:
    """HTMLレポート生成クラス"""
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        初期化
        
        Args:
            template_dir: テンプレートディレクトリのパス
        """
        if not JINJA2_AVAILABLE:
            raise ImportError("jinja2が必要です。pip install jinja2 でインストールしてください。")
        
        # テンプレートディレクトリを設定
        if template_dir:
            self.template_dir = Path(template_dir)
        else:
            # デフォルト: プロジェクトルートのtemplates
            project_root = Path(__file__).parent.parent.parent
            self.template_dir = project_root / "templates"
        
        # Jinja2環境を初期化
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # 数値フォーマット用のフィルターを追加
        def format_currency(value, decimals=0):
            """数値を百万円単位で表示（J-Quants APIのデータは円単位）
            
            APIから取得するデータは円単位なので、1000000で割って百万円単位で表示
            """
            if value is None:
                return "N/A"
            try:
                val = float(value)
                if val == 0:
                    return "0"
                
                abs_val = abs(val)
                sign = "-" if val < 0 else ""
                
                # 円単位のデータを百万円単位に変換
                formatted = abs_val / 1000000
                return f"{sign}{formatted:,.{decimals}f}百万円"
            except (ValueError, TypeError):
                return "N/A"
        
        self.env.filters['format_currency'] = format_currency
        
        # 静的ファイルディレクトリ
        project_root = Path(__file__).parent.parent.parent
        self.static_dir = project_root / "static"
    
    def _create_interactive_graphs(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        HTML用のインタラクティブグラフを作成
        
        Args:
            result: 分析結果の辞書
            
        Returns:
            グラフ情報のリスト（PlotlyのHTMLを含む）
        """
        metrics = result.get("metrics", {})
        years = metrics.get("years", [])
        
        if not years:
            return []
        
        fy_ends = [year.get("fy_end") for year in years]
        graphs = []
        
        # データを取得
        fcf_values = [year.get("fcf") for year in years]
        roe_values = [year.get("roe") for year in years]
        eps_values = [year.get("eps") for year in years]
        sales_values = [year.get("sales") for year in years]
        per_values = [year.get("per") for year in years]
        pbr_values = [year.get("pbr") for year in years]
        op_values = [year.get("op") for year in years]
        cfo_values = [year.get("cfo") for year in years]
        
        # HTML変換用のヘルパー関数
        def try_convert_to_html(fig, section_title, graph_title="", width="full"):
            """グラフをHTMLに変換してリストに追加"""
            try:
                html_div = pio.to_html(fig, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
                graphs.append({
                    "section_title": section_title,
                    "title": graph_title if graph_title else section_title,
                    "html": html_div,
                    "type": "interactive",
                    "width": width
                })
            except Exception as e:
                logger.warning(f"インタラクティブグラフ生成失敗 ({section_title}): {e}")
        
        # BPS値を取得（利用可能な場合）
        bps_values = [year.get("bps") for year in years]
        
        # 1. FCF推移（営業利益 vs 営業CFを統合）
        from plotly.subplots import make_subplots
        # 軸を共通化するため、secondary_y=Falseで全て同じ軸に
        fig_fcf = go.Figure()
        
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
            # 円単位のデータを百万円単位に変換
            return val / 1000000 if val != 0 else 0
        
        # FCF（折れ線グラフ、一番上に表示するため最後に追加）
        fcf_x, fcf_y = filter_none_values(fy_ends, fcf_values)[:2]
        
        # 営業利益（棒グラフ、ホバー表示時に百万円単位に変換）
        op_x, op_y = filter_none_values(fy_ends, op_values)[:2]
        
        op_y_million = [to_million(y) for y in op_y]
        fig_fcf.add_trace(go.Bar(
            x=op_x,
            y=op_y,
            name="営業利益",
            marker_color="#17becf",
            customdata=op_y_million,
            hovertemplate='<b>%{x}年度</b><br>営業利益: %{customdata:,.0f}百万円<extra></extra>'
        ))
        
        # 営業CF（棒グラフ、ホバー表示時に百万円単位に変換）
        cfo_x, cfo_y = filter_none_values(fy_ends, cfo_values)[:2]
        cfo_y_million = [to_million(y) for y in cfo_y]
        fig_fcf.add_trace(go.Bar(
            x=cfo_x,
            y=cfo_y,
            name="営業CF",
            marker_color="#bcbd22",
            customdata=cfo_y_million,
            hovertemplate='<b>%{x}年度</b><br>営業CF: %{customdata:,.0f}百万円<extra></extra>'
        ))
        
        # FCF（折れ線グラフ、最後に追加して一番上に表示、ホバー表示時に百万円単位に変換）
        fcf_y_million = [to_million(y) for y in fcf_y]
        fig_fcf.add_trace(go.Scatter(
            x=fcf_x,
            y=fcf_y,
            mode="lines+markers",
            name="FCF",
            line=dict(color="#1e3a8a", width=4),
            marker=dict(size=10),
            customdata=fcf_y_million,
            hovertemplate='<b>%{x}年度</b><br>FCF: %{customdata:,.0f}百万円<extra></extra>'
        ))
        
        # FCF=0の基準線
        fig_fcf.add_hline(y=0, line_dash="dash", line_color="red", line_width=2)
        
        fig_fcf.update_xaxes(title_text="年度")
        fig_fcf.update_yaxes(title_text="金額 (円)")
        fig_fcf.update_layout(
            title="",
            template="plotly_white",
            height=500,
            margin=dict(l=60, r=30, t=60, b=60),
            font=dict(size=16),
            hovermode='x unified',
            barmode='group'
        )
        try_convert_to_html(fig_fcf, "FCF推移（営業利益 vs 営業CF）", "FCF推移と利益品質", width="full")
        
        # 2. ROE/EPS/BPS推移
        from plotly.subplots import make_subplots
        
        # 各指標のホバーテキスト（数値と前年比のみ）
        hover_texts_roe = []
        hover_texts_eps = []
        hover_texts_bps = []
        for i, year in enumerate(fy_ends):
            if i == 0:
                roe_text = f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{year}年度</b><br>ROE: N/A"
                eps_text = f"<b>{year}年度</b><br>EPS: {eps_values[i]:.2f}円" if eps_values[i] is not None else f"<b>{year}年度</b><br>EPS: N/A"
                bps_text = f"<b>{year}年度</b><br>BPS: {bps_values[i]:.2f}円" if bps_values[i] is not None else f"<b>{year}年度</b><br>BPS: N/A"
                hover_texts_roe.append(roe_text)
                hover_texts_eps.append(eps_text)
                hover_texts_bps.append(bps_text)
            else:
                roe_diff = roe_values[i] - roe_values[i-1] if roe_values[i] is not None and roe_values[i-1] is not None else None
                eps_diff = eps_values[i] - eps_values[i-1] if eps_values[i] is not None and eps_values[i-1] is not None else None
                bps_diff = bps_values[i] - bps_values[i-1] if bps_values[i] is not None and bps_values[i-1] is not None else None
                
                roe_text = f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}% ({roe_diff:+.2f}%)" if roe_values[i] is not None and roe_diff is not None else (f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{year}年度</b><br>ROE: N/A")
                eps_text = f"<b>{year}年度</b><br>EPS: {eps_values[i]:.2f}円 ({eps_diff:+.2f}円)" if eps_values[i] is not None and eps_diff is not None else (f"<b>{year}年度</b><br>EPS: {eps_values[i]:.2f}円" if eps_values[i] is not None else f"<b>{year}年度</b><br>EPS: N/A")
                bps_text = f"<b>{year}年度</b><br>BPS: {bps_values[i]:.2f}円 ({bps_diff:+.2f}円)" if bps_values[i] is not None and bps_diff is not None else (f"<b>{year}年度</b><br>BPS: {bps_values[i]:.2f}円" if bps_values[i] is not None else f"<b>{year}年度</b><br>BPS: N/A")
                hover_texts_roe.append(roe_text)
                hover_texts_eps.append(eps_text)
                hover_texts_bps.append(bps_text)
        
        # グラフ作成（ROE: 左軸、EPS/BPS: 右軸共通）
        
        fig_roe_eps_bps = make_subplots(specs=[[{"secondary_y": True}]])
        
        # ROE（左軸、数値のみ）
        roe_x, roe_y, roe_hover = filter_none_values(fy_ends, roe_values, hover_texts_roe)
        fig_roe_eps_bps.add_trace(
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
            secondary_y=False
        )
        
        # EPS（右軸、数値のみ）
        eps_x, eps_y, eps_hover = filter_none_values(fy_ends, eps_values, hover_texts_eps)
        fig_roe_eps_bps.add_trace(
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
            secondary_y=True
        )
        
        # BPS（右軸、EPSと同じ軸、数値のみ）
        if any(bps is not None for bps in bps_values):
            bps_x, bps_y, bps_hover = filter_none_values(fy_ends, bps_values, hover_texts_bps)
            fig_roe_eps_bps.add_trace(
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
                secondary_y=True  # EPSと同じ右軸
            )
        
        fig_roe_eps_bps.update_xaxes(title_text="年度")
        fig_roe_eps_bps.update_yaxes(title_text="ROE (%)", secondary_y=False)
        fig_roe_eps_bps.update_yaxes(title_text="EPS / BPS (円)", secondary_y=True)
        fig_roe_eps_bps.update_layout(
            title="",
            height=500,
            hovermode='closest',
            font=dict(size=14),
            template="plotly_white"
        )
        
        # グラフHTMLを生成
        html_div = pio.to_html(fig_roe_eps_bps, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
        
        # 総合評価を計算
        evaluation_data = None
        if len(years) > 1:
            # 有効なデータ（ROE, EPS, BPS全てが有効な年度）を取得
            valid_years = []
            for i, year in enumerate(years):
                roe = roe_values[i] if i < len(roe_values) else None
                eps = eps_values[i] if i < len(eps_values) else None
                bps = bps_values[i] if i < len(bps_values) else None
                
                # ROE, EPS, BPS全てが有効な年度のみを追加（パターン判定には3つ全てが必要）
                # NaNチェックも含める
                def is_valid_value(value):
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
                
                if is_valid_value(roe) and is_valid_value(eps) and is_valid_value(bps):
                    valid_years.append({
                        "year": year,
                        "roe": roe,
                        "eps": eps,
                        "bps": bps,
                        "index": i
                    })
            
            if len(valid_years) >= 2:
                # 最初（最新）と最後（最古）の有効な年度を取得
                # yearsは新しい順（最新が最初）なので、valid_yearsも同じ順序
                latest = valid_years[0]  # 最新
                oldest = valid_years[-1]  # 最古
                
                # 年度を抽出
                def extract_year(fy_end):
                    if not fy_end:
                        return ""
                    if isinstance(fy_end, str):
                        if len(fy_end) >= 4:
                            return fy_end[:4]
                    return ""
                
                start_year = extract_year(oldest["year"].get("fy_end", ""))
                end_year = extract_year(latest["year"].get("fy_end", ""))
                
                # CAGR計算用の値と期間
                roe_start = oldest["roe"]
                roe_end = latest["roe"]
                eps_start = oldest["eps"]
                eps_end = latest["eps"]
                bps_start = oldest["bps"]
                bps_end = latest["bps"]
                
                # 値がNoneでないことを再確認
                if roe_start is None or roe_end is None or eps_start is None or eps_end is None or bps_start is None or bps_end is None:
                    logger.warning(f"valid_yearsに含まれるデータにNone値が存在: oldest_roe={roe_start}, latest_roe={roe_end}, oldest_eps={eps_start}, latest_eps={eps_end}, oldest_bps={bps_start}, latest_bps={bps_end}")
                    logger.warning(f"  oldest year: {oldest['year']}, latest year: {latest['year']}")
                    # None値がある場合は評価データを生成しない
                else:
                    # 期間年数を計算（有効な年度間の年数）
                    period_years = len(valid_years) - 1
                    
                    roe_cagr = calculate_cagr(roe_start, roe_end, period_years)
                    eps_cagr = calculate_cagr(eps_start, eps_end, period_years)
                    bps_cagr = calculate_cagr(bps_start, bps_end, period_years)
                    
                    if roe_cagr is not None and eps_cagr is not None and bps_cagr is not None:
                        # プラス/マイナス判定
                        roe_sign = "+" if roe_cagr > 0 else "-"
                        eps_sign = "+" if eps_cagr > 0 else "-"
                        bps_sign = "+" if bps_cagr > 0 else "-"
                        
                        # パターンマッピング
                        patterns = {
                            ('+', '+', '+'): ('①', '王道成長', '最良', '効率も規模も拡大'),
                            ('+', '+', '-'): ('②', '希薄化投資', '要精査', '増資や株式報酬でBPS↑、EPS希薄化。'),
                            ('+', '-', '+'): ('③', '高効率縮小', '良い', '自社株買い・リストラ'),
                            ('+', '-', '-'): ('④', '効率↑でも縮小', '注意', '事業縮小'),
                            ('-', '+', '+'): ('⑤', '成長効率低下', '危険', '規模拡大だがROE低下。'),
                            ('-', '+', '-'): ('⑥', '非効率拡張', '悪い', '資本肥大・失敗投資'),
                            ('-', '-', '+'): ('⑦', '一時益', '一時的', '売却益や自社株買いでEPSのみ改善。'),
                            ('-', '-', '-'): ('⑧', '崩壊', '回避', '全部悪化')
                        }
                        
                        pattern_key = (roe_sign, eps_sign, bps_sign)
                        if pattern_key in patterns:
                            pattern_num, pattern_name, evaluation, note = patterns[pattern_key]
                            evaluation_data = {
                                "start_year": start_year,
                                "end_year": end_year,
                                "roe_cagr": roe_cagr,
                                "eps_cagr": eps_cagr,
                                "bps_cagr": bps_cagr,
                                "roe_sign": roe_sign,
                                "eps_sign": eps_sign,
                                "bps_sign": bps_sign,
                                "pattern_num": pattern_num,
                                "pattern_name": pattern_name,
                                "evaluation": evaluation,
                                "note": note
                            }
                        else:
                            logger.warning(f"パターンが見つかりません: {pattern_key}")
                    else:
                        logger.warning(f"CAGR計算失敗: roe={roe_cagr}, eps={eps_cagr}, bps={bps_cagr}")
            else:
                logger.warning(f"有効な年度データが不足: 有効年度数={len(valid_years)}")
        else:
            logger.warning(f"年度データが不足: 年度数={len(years)}")
        
        graph_obj = {
            "section_title": "ROE/EPS/BPS推移",
            "title": "ROE × BPS = EPS（実績の整合性検証）",
            "html": html_div,
            "type": "interactive",
            "width": "full"
        }
        if evaluation_data:
            graph_obj["evaluation"] = evaluation_data
        else:
            logger.warning("評価データが生成されませんでした")
        graphs.append(graph_obj)
        
        # 3. PER/PBR/ROE推移
        
        # 各指標のホバーテキスト（数値と前年比のみ）
        hover_texts_per = []
        hover_texts_pbr = []
        hover_texts_roe2 = []
        for i, year in enumerate(fy_ends):
            if i == 0:
                per_text = f"<b>{year}年度</b><br>PER: {per_values[i]:.2f}倍" if per_values[i] is not None else f"<b>{year}年度</b><br>PER: N/A"
                pbr_text = f"<b>{year}年度</b><br>PBR: {pbr_values[i]:.2f}倍" if pbr_values[i] is not None else f"<b>{year}年度</b><br>PBR: N/A"
                roe_text = f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{year}年度</b><br>ROE: N/A"
                hover_texts_per.append(per_text)
                hover_texts_pbr.append(pbr_text)
                hover_texts_roe2.append(roe_text)
            else:
                per_diff = per_values[i] - per_values[i-1] if per_values[i] is not None and per_values[i-1] is not None else None
                pbr_diff = pbr_values[i] - pbr_values[i-1] if pbr_values[i] is not None and pbr_values[i-1] is not None else None
                roe_diff = roe_values[i] - roe_values[i-1] if roe_values[i] is not None and roe_values[i-1] is not None else None
                
                per_text = f"<b>{year}年度</b><br>PER: {per_values[i]:.2f}倍 ({per_diff:+.2f}倍)" if per_values[i] is not None and per_diff is not None else (f"<b>{year}年度</b><br>PER: {per_values[i]:.2f}倍" if per_values[i] is not None else f"<b>{year}年度</b><br>PER: N/A")
                pbr_text = f"<b>{year}年度</b><br>PBR: {pbr_values[i]:.2f}倍 ({pbr_diff:+.2f}倍)" if pbr_values[i] is not None and pbr_diff is not None else (f"<b>{year}年度</b><br>PBR: {pbr_values[i]:.2f}倍" if pbr_values[i] is not None else f"<b>{year}年度</b><br>PBR: N/A")
                roe_text = f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}% ({roe_diff:+.2f}%)" if roe_values[i] is not None and roe_diff is not None else (f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{year}年度</b><br>ROE: N/A")
                hover_texts_per.append(per_text)
                hover_texts_pbr.append(pbr_text)
                hover_texts_roe2.append(roe_text)
        
        # グラフ作成（PER/PBR: 左軸共通、ROE: 右軸）
        fig_per_pbr_roe = make_subplots(specs=[[{"secondary_y": True}]])
        
        # PER（左軸、数値のみ）
        per_x, per_y, per_hover = filter_none_values(fy_ends, per_values, hover_texts_per)
        fig_per_pbr_roe.add_trace(
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
        
        # PBR（左軸、PERと同じ軸、数値のみ）
        pbr_x, pbr_y, pbr_hover = filter_none_values(fy_ends, pbr_values, hover_texts_pbr)
        fig_per_pbr_roe.add_trace(
            go.Scatter(
                x=pbr_x,
                y=pbr_y,
                mode='lines+markers',
                name='PBR (倍)',
                line=dict(color='#8c564b', width=3),
                marker=dict(size=8),
                hovertext=pbr_hover if pbr_hover else None,
                hoverinfo='text' if pbr_hover else 'y'
            ),
            secondary_y=False  # PERと同じ左軸
        )
        
        # ROE（右軸、数値のみ）
        roe2_x, roe2_y, roe2_hover = filter_none_values(fy_ends, roe_values, hover_texts_roe2)
        fig_per_pbr_roe.add_trace(
            go.Scatter(
                x=roe2_x,
                y=roe2_y,
                mode='lines+markers',
                name='ROE (%)',
                line=dict(color='#ff7f0e', width=3),
                marker=dict(size=8),
                hovertext=roe2_hover if roe2_hover else None,
                hoverinfo='text' if roe2_hover else 'y'
            ),
            secondary_y=True
        )
        
        # PBR=1の基準線
        fig_per_pbr_roe.add_hline(y=1, line_dash="dash", line_color="gray", line_width=1, secondary_y=False)
        
        fig_per_pbr_roe.update_xaxes(title_text="年度")
        fig_per_pbr_roe.update_yaxes(title_text="PER / PBR (倍)", secondary_y=False)
        fig_per_pbr_roe.update_yaxes(title_text="ROE (%)", secondary_y=True)
        fig_per_pbr_roe.update_layout(
            title="",
            height=500,
            hovermode='closest',
            font=dict(size=14),
            template="plotly_white"
        )
        
        # グラフHTMLを生成
        html_div_per_pbr = pio.to_html(fig_per_pbr_roe, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
        
        # 総合評価を計算（PER/PBR/ROE）
        evaluation_data_per_pbr_roe = None
        if len(years) > 1:
            # 有効なデータ（PER, PBR, ROE全てが有効な年度）を取得
            valid_years_per_pbr_roe = []
            for i, year in enumerate(years):
                per = per_values[i] if i < len(per_values) else None
                pbr = pbr_values[i] if i < len(pbr_values) else None
                roe = roe_values[i] if i < len(roe_values) else None
                
                # PER, PBR, ROE全てが有効な年度のみを追加
                if per is not None and pbr is not None and roe is not None:
                    valid_years_per_pbr_roe.append({
                        "year": year,
                        "per": per,
                        "pbr": pbr,
                        "roe": roe,
                        "index": i
                    })
            
            if len(valid_years_per_pbr_roe) >= 2:
                # 最初（最新）と最後（最古）の有効な年度を取得
                latest = valid_years_per_pbr_roe[0]  # 最新
                oldest = valid_years_per_pbr_roe[-1]  # 最古
                
                # 年度を抽出
                def extract_year(fy_end):
                    if not fy_end:
                        return ""
                    if isinstance(fy_end, str):
                        if len(fy_end) >= 4:
                            return fy_end[:4]
                    return ""
                
                start_year = extract_year(oldest["year"].get("fy_end", ""))
                end_year = extract_year(latest["year"].get("fy_end", ""))
                
                # CAGR計算用の値と期間
                per_start = oldest["per"]
                per_end = latest["per"]
                pbr_start = oldest["pbr"]
                pbr_end = latest["pbr"]
                roe_start = oldest["roe"]
                roe_end = latest["roe"]
                
                # 期間年数を計算（有効な年度間の年数）
                period_years = len(valid_years_per_pbr_roe) - 1
                
                per_cagr = calculate_cagr(per_start, per_end, period_years)
                pbr_cagr = calculate_cagr(pbr_start, pbr_end, period_years)
                roe_cagr = calculate_cagr(roe_start, roe_end, period_years)
                
                if per_cagr is not None and pbr_cagr is not None and roe_cagr is not None:
                    # プラス/マイナス判定
                    per_sign = "+" if per_cagr > 0 else "-"
                    pbr_sign = "+" if pbr_cagr > 0 else "-"
                    roe_sign = "+" if roe_cagr > 0 else "-"
                    
                    # パターンマッピング（順番：PER, ROE, PBR）
                    patterns = {
                        ('+', '+', '+'): ('①', '成長再評価', '注意', '実力↑ × 期待↑'),
                        ('+', '+', '-'): ('②', '質疑義', '要精査', 'ROE改善の質に疑問'),
                        ('+', '-', '+'): ('③', '期待先行', '危険', '実力悪化でも評価↑'),
                        ('+', '-', '-'): ('④', '期待乖離', '要精査', '期待↑だが実体↓'),
                        ('-', '+', '+'): ('⑤', '静かな改善', '妙味', '実力↑なのに評価控えめ'),
                        ('-', '+', '-'): ('⑥', '割安候補', '妙味', '実力↑・市場未評価'),
                        ('-', '-', '+'): ('⑦', '見せかけ', '危険', '実体↓だが評価↑'),
                        ('-', '-', '-'): ('⑧', '崩壊', '回避', '全部悪化')
                    }
                    
                    pattern_key = (per_sign, roe_sign, pbr_sign)  # 順番注意：PER, ROE, PBR
                    if pattern_key in patterns:
                        pattern_num, pattern_name, evaluation, note = patterns[pattern_key]
                        evaluation_data_per_pbr_roe = {
                            "start_year": start_year,
                            "end_year": end_year,
                            "per_cagr": per_cagr,
                            "pbr_cagr": pbr_cagr,
                            "roe_cagr": roe_cagr,
                            "per_sign": per_sign,
                            "pbr_sign": pbr_sign,
                            "roe_sign": roe_sign,
                            "pattern_num": pattern_num,
                            "pattern_name": pattern_name,
                            "evaluation": evaluation,
                            "note": note
                        }
                    else:
                        logger.warning(f"PER/PBR/ROEパターンが見つかりません: {pattern_key}")
                else:
                    logger.warning(f"PER/PBR/ROE CAGR計算失敗: per={per_cagr}, pbr={pbr_cagr}, roe={roe_cagr}")
            else:
                logger.warning(f"PER/PBR/ROE有効な年度データが不足: 有効年度数={len(valid_years_per_pbr_roe)}")
        else:
            logger.warning(f"PER/PBR/ROE年度データが不足: 年度数={len(years)}")
        
        graph_obj_per_pbr_roe = {
            "section_title": "PER/PBR/ROE推移",
            "title": "PBR = PER × ROE（評価の整合性検証）",
            "html": html_div_per_pbr,
            "type": "interactive",
            "width": "full"
        }
        if evaluation_data_per_pbr_roe:
            graph_obj_per_pbr_roe["evaluation"] = evaluation_data_per_pbr_roe
        else:
            logger.warning("PER/PBR/ROE評価データが生成されませんでした")
        graphs.append(graph_obj_per_pbr_roe)
        
        # 4. 売上高推移
        fig_sales = go.Figure()
        sales_x, sales_y = filter_none_values(fy_ends, sales_values)[:2]
        # ホバー表示時に百万円単位に変換（to_million関数を使用）
        sales_y_million = [to_million(y) for y in sales_y]
        fig_sales.add_trace(go.Scatter(
            x=sales_x,
            y=sales_y,
            mode="lines+markers",
            name="売上高",
            line=dict(color="#d62728", width=3),
            marker=dict(size=8),
            customdata=sales_y_million,
            hovertemplate='<b>%{x}年度</b><br>売上高: %{customdata:,.0f}百万円<extra></extra>'
        ))
        fig_sales.update_layout(
            title="",
            xaxis_title="年度",
            yaxis_title="売上高 (円)",
            template="plotly_white",
            height=500,
            margin=dict(l=50, r=20, t=50, b=50),
            font=dict(size=14),
            hovermode='closest'
        )
        try_convert_to_html(fig_sales, "売上高推移", "", width="full")
        
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
            for i, fy_end in enumerate(fy_ends):
                eps = eps_values[i] if i < len(eps_values) else None
                year_str = fy_end[:4] if fy_end and len(fy_end) >= 4 else "不明"
                
                if fy_end and eps is not None:
                    price = get_fiscal_year_end_price(api_client, code, fy_end)
                    if price:
                        stock_prices.append(price)
                        stock_years.append(year_str)
                        aligned_fy_ends.append(fy_end)
                        aligned_eps.append(eps)
                    else:
                        logger.warning(f"株価 vs EPS: 年度{i} ({year_str}): 株価取得失敗（fy_end={fy_end}）")
                else:
                    if not fy_end:
                        logger.warning(f"株価 vs EPS: 年度{i} ({year_str}): fy_endが存在しない")
                    if eps is None:
                        logger.warning(f"株価 vs EPS: 年度{i} ({year_str}): EPSがNone")
        
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
            
            # 年度の向きを逆にする（古い年から新しい年の順に）
            reversed_stock_years = list(reversed(stock_years))
            reversed_price_index = list(reversed(price_index))
            reversed_eps_index = list(reversed(eps_index))
            reversed_stock_prices = list(reversed(stock_prices))
            reversed_aligned_eps = list(reversed(aligned_eps))
            
            # グラフ作成
            fig_price_eps = go.Figure()
            
            # 株価指数
            fig_price_eps.add_trace(go.Scatter(
                x=reversed_stock_years,
                y=reversed_price_index,
                mode='lines+markers',
                name='株価指数',
                line=dict(width=3, color='blue'),
                marker=dict(size=10),
                hovertemplate='<b>%{x}年度</b><br>株価指数: %{y:.1f}<br>実際の株価: ¥%{customdata:.0f}<extra></extra>',
                customdata=reversed_stock_prices
            ))
            
            # EPS指数
            fig_price_eps.add_trace(go.Scatter(
                x=reversed_stock_years,
                y=reversed_eps_index,
                mode='lines+markers',
                name='EPS指数',
                line=dict(width=3, color='green'),
                marker=dict(size=10),
                hovertemplate='<b>%{x}年度</b><br>EPS指数: %{y:.1f}<br>実際のEPS: ¥%{customdata:.2f}<extra></extra>',
                customdata=reversed_aligned_eps
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
            
            try_convert_to_html(fig_price_eps, "株価 vs EPS（指数化比較）", f"株価とEPSの乖離（{oldest_year}年=100）", width="full")
        
        # 7. グラフ6: PER推移 vs EPS年次成長率
        # EPS年次成長率を計算（前年比較なので一番古い年は除外）
        # データは新しい年から古い年の順なので、最後の要素（一番古い年）を除外
        # 前年比較なので、最新年（i=0）から計算を開始
        eps_growth_rates = []
        eps_growth_years = []
        for i in range(0, len(eps_values) - 1):  # 最新年から計算、一番古い年は除外
            # i年 vs i+1年（新しい年 vs 古い年）の成長率
            if eps_values[i] is not None and eps_values[i+1] is not None and eps_values[i+1] != 0:
                try:
                    growth_rate = ((eps_values[i] / eps_values[i+1]) - 1) * 100
                    eps_growth_rates.append(growth_rate)
                    eps_growth_years.append(fy_ends[i])
                except (ZeroDivisionError, TypeError):
                    # 計算できない場合はスキップ（追加しない）
                    pass
            # None値や計算できない場合は追加しない（グラフを繋げるため）
        
        # グラフ作成
        fig_per_eps_growth = go.Figure()
        
        # PER推移（左軸、折れ線）
        per_growth_x, per_growth_y = filter_none_values(fy_ends, per_values)[:2]
        fig_per_eps_growth.add_trace(go.Scatter(
            x=per_growth_x,
            y=per_growth_y,
            mode='lines+markers',
            name='PER（倍）',
            line=dict(width=3, color='purple'),
            marker=dict(size=10),
            yaxis='y',
            hovertemplate='<b>%{x}年度</b><br>PER: %{y:.2f}倍<extra></extra>'
        ))
        
        # EPS年次成長率（右軸、折れ線グラフ）
        if len(eps_growth_rates) > 0:
            fig_per_eps_growth.add_trace(go.Scatter(
                x=eps_growth_years,
                y=eps_growth_rates,
                mode='lines+markers',
                name='EPS成長率（%）',
                line=dict(width=3, color='green'),
                marker=dict(size=10),
                yaxis='y2',
                hovertemplate='<b>%{x}年度</b><br>EPS成長率: %{y:+.2f}%<extra></extra>'
            ))
        
        # 0%基準線（右軸）
        fig_per_eps_growth.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1, yref='y2')
        
        # レイアウト
        fig_per_eps_growth.update_layout(
            title="",
            xaxis=dict(title='年度'),
            yaxis=dict(
                title=dict(text='PER（倍）', font=dict(color='purple')),
                side='left',
                tickfont=dict(color='purple')
            ),
            yaxis2=dict(
                title=dict(text='EPS成長率（%）', font=dict(color='green')),
                side='right',
                overlaying='y',
                tickfont=dict(color='green')
            ),
            hovermode='x unified',
            height=500,
            legend=dict(x=0.02, y=0.98),
            template="plotly_white",
            font=dict(size=14)
        )
        
        try_convert_to_html(fig_per_eps_growth, "PER推移 vs EPS年次成長率", "期待（PER）と実績（EPS成長率）", width="full")
        
        return graphs
    
    def generate(
        self,
        result: Dict[str, Any],
        output_path: str
    ) -> bool:
        """
        HTMLレポートを生成
        
        Args:
            result: 分析結果の辞書
            output_path: 出力パス（.html）
            
        Returns:
            常にTrue（HTML生成成功時）
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # データを準備
        code = result.get("code", "")
        name = result.get("name", "")
        sector_name = result.get("sector_33_name", "")
        market_name = result.get("market_name", "")
        
        metrics = result.get("metrics", {})
        years = metrics.get("years", [])
        
        # グラフを作成
        graphs = self._create_interactive_graphs(result)
        
        # 比較情報（過去データとの比較機能は削除済み、テンプレート互換性のため空辞書を渡す）
        comparison_info = {}
        
        # CSSを読み込む
        css_content = ""
        css_path = self.static_dir / "css" / "report.css"
        if css_path.exists():
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
        
        # テンプレートデータ
        template_data = {
            "code": code,
            "name": name,
            "sector_name": sector_name,
            "market_name": market_name,
            "analysis_date": datetime.now().strftime("%Y年%m月%d日"),
            "graphs": graphs,
            "comparison_info": comparison_info,
            "years": years,  # 全年度データ
            "metrics": metrics,  # CAGR用
            "css_content": css_content,
        }
        
        # HTMLを生成
        try:
            template = self.env.get_template("report_template.html")
            html_content = template.render(**template_data)
        except Exception as e:
            logger.error(f"テンプレートレンダリング失敗: {e}")
            raise
        
        # HTMLファイルを保存
        html_path = output_path.with_suffix('.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ HTMLレポートが生成されました: {html_path}")
        print()
        return True
