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


def get_sign(cagr):
    """CAGRから符号（+/-）を取得"""
    if cagr is None:
        return None
    return '+' if cagr > 0 else '-'


def evaluate_business_efficiency_pattern(roic_cagr, cf_conversion_cagr):
    """事業効率パターン評価（簡易ROIC × CF変換率）"""
    if roic_cagr is None or cf_conversion_cagr is None:
        return None
    
    roic_sign = get_sign(roic_cagr)
    cf_sign = get_sign(cf_conversion_cagr)
    
    patterns = {
        ('+', '+'): ('①', '質量拡大', '最良', '効率も質も向上'),
        ('+', '-'): ('②', '効率↑質↓', '要注意', '短期的要因か投資増加の可能性'),
        ('-', '+'): ('③', '効率↓質↑', '注意', '利益効率低下だが現金創出力は確保'),
        ('-', '-'): ('④', '質量劣化', '回避', '効率・現金創出ともに悪化')
    }
    
    pattern_key = (roic_sign, cf_sign)
    if pattern_key in patterns:
        pattern_num, pattern_name, evaluation, note = patterns[pattern_key]
        return {
            "pattern_num": pattern_num,
            "pattern_name": pattern_name,
            "evaluation": evaluation,
            "note": note,
            "roic_cagr": roic_cagr,
            "cf_conversion_cagr": cf_conversion_cagr,
            "roic_sign": roic_sign,
            "cf_sign": cf_sign
        }
    return None


def evaluate_shareholder_value_pattern(eps_cagr, bps_cagr, roe_cagr):
    """株主価値パターン評価（EPS × BPS × ROE）"""
    if eps_cagr is None or bps_cagr is None or roe_cagr is None:
        return None
    
    eps_sign = get_sign(eps_cagr)
    bps_sign = get_sign(bps_cagr)
    roe_sign = get_sign(roe_cagr)
    
    patterns = {
        ('+', '+', '+'): ('①', '王道成長', '最良', '効率も規模も拡大'),
        ('+', '+', '-'): ('⑤', '成長効率低下', '危険', '規模拡大だがROE低下。'),
        ('+', '-', '+'): ('②', '希薄化投資', '要精査', '増資や株式報酬でBPS↑、EPS希薄化。'),
        ('+', '-', '-'): ('⑦', '一時益', '一時的', '売却益や自社株買いでEPSのみ改善。'),
        ('-', '+', '+'): ('③', '高効率縮小', '良い', '自社株買い・リストラ'),
        ('-', '+', '-'): ('⑥', '非効率拡張', '悪い', '資本肥大・失敗投資'),
        ('-', '-', '+'): ('④', '効率↑でも縮小', '注意', '事業縮小'),
        ('-', '-', '-'): ('⑧', '崩壊', '回避', '全部悪化')
    }
    
    pattern_key = (eps_sign, bps_sign, roe_sign)
    if pattern_key in patterns:
        pattern_num, pattern_name, evaluation, note = patterns[pattern_key]
        return {
            "pattern_num": pattern_num,
            "pattern_name": pattern_name,
            "evaluation": evaluation,
            "note": note,
            "eps_cagr": eps_cagr,
            "bps_cagr": bps_cagr,
            "roe_cagr": roe_cagr,
            "eps_sign": eps_sign,
            "bps_sign": bps_sign,
            "roe_sign": roe_sign
        }
    return None


def evaluate_dividend_policy_pattern(roe_cagr, pbr_cagr, payout_cagr):
    """配当政策パターン評価（ROE × PBR × 配当性向）"""
    if roe_cagr is None or pbr_cagr is None or payout_cagr is None:
        return None
    
    roe_sign = get_sign(roe_cagr)
    pbr_sign = get_sign(pbr_cagr)
    payout_sign = get_sign(payout_cagr)
    
    patterns = {
        ('+', '+', '+'): ('①', '理想型', '最良', '稼いで評価されて返す'),
        ('+', '+', '-'): ('②', '成長投資型', '良い', '稼いで評価、内部留保で成長'),
        ('+', '-', '+'): ('③', '割安還元型', '割安', '稼いで返すも過小評価'),
        ('+', '-', '-'): ('④', '評価されず', '割安', '稼ぐ力はあるが市場評価低め'),
        ('-', '+', '+'): ('⑤', '還元で延命', '注意', 'ROE低いが配当高で市場評価は維持'),
        ('-', '+', '-'): ('⑥', '謎の高評価', '警戒', 'ROE低いがPBR高。市場期待先行の可能性'),
        ('-', '-', '+'): ('⑦', '悪化中還元', '悪い', '還元強化も評価下落'),
        ('-', '-', '-'): ('⑧', '全面悪化', '回避', '全て悪化')
    }
    
    pattern_key = (roe_sign, pbr_sign, payout_sign)
    if pattern_key in patterns:
        pattern_num, pattern_name, evaluation, note = patterns[pattern_key]
        return {
            "pattern_num": pattern_num,
            "pattern_name": pattern_name,
            "evaluation": evaluation,
            "note": note,
            "roe_cagr": roe_cagr,
            "pbr_cagr": pbr_cagr,
            "payout_cagr": payout_cagr,
            "roe_sign": roe_sign,
            "pbr_sign": pbr_sign,
            "payout_sign": payout_sign
        }
    return None


def evaluate_market_valuation_pattern(per_cagr, roe_cagr, pbr_cagr):
    """市場評価パターン評価（PER × ROE × PBR）"""
    if per_cagr is None or roe_cagr is None or pbr_cagr is None:
        return None
    
    per_sign = get_sign(per_cagr)
    roe_sign = get_sign(roe_cagr)
    pbr_sign = get_sign(pbr_cagr)
    
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
    
    pattern_key = (per_sign, roe_sign, pbr_sign)
    if pattern_key in patterns:
        pattern_num, pattern_name, evaluation, note = patterns[pattern_key]
        return {
            "pattern_num": pattern_num,
            "pattern_name": pattern_name,
            "evaluation": evaluation,
            "note": note,
            "per_cagr": per_cagr,
            "roe_cagr": roe_cagr,
            "pbr_cagr": pbr_cagr,
            "per_sign": per_sign,
            "roe_sign": roe_sign,
            "pbr_sign": pbr_sign
        }
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
        
        fy_ends = [year.get("fy_end") for year in years]
        graphs = []
        
        # データを取得
        fcf_values = [year.get("fcf") for year in years]
        roe_values = [year.get("roe") for year in years]
        eps_values = [year.get("eps") for year in years]
        per_values = [year.get("per") for year in years]
        pbr_values = [year.get("pbr") for year in years]
        op_values = [year.get("op") for year in years]
        cfo_values = [year.get("cfo") for year in years]
        cfi_values = [year.get("cfi") for year in years]
        eq_values = [year.get("eq") for year in years]
        np_values = [year.get("np") for year in years]
        bps_values = [year.get("bps") for year in years]
        payout_ratio_values = [year.get("payout_ratio") for year in years]
        
        # HTML変換用のヘルパー関数
        def try_convert_to_html(fig, section_title, graph_title="", width="full", evaluation_data=None):
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
                if evaluation_data:
                    graph_obj["evaluation"] = evaluation_data
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
        
        # 年度を抽出する関数
        def extract_year(fy_end):
            """年度終了日から年度を抽出"""
            if not fy_end:
                return ""
            if isinstance(fy_end, str):
                if len(fy_end) >= 4:
                    return fy_end[:4]
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
        
        roic_x, roic_y = filter_none_values(fy_ends, roic_values)[:2]
        fig_business_efficiency.add_trace(
            go.Scatter(
                x=roic_x,
                y=roic_y,
                mode='lines+markers',
                name='簡易ROIC (%)',
                line=dict(color='#1f77b4', width=3),
                marker=dict(size=8),
                hovertemplate='<b>%{x}年度</b><br>簡易ROIC: %{y:.2f}%<extra></extra>'
            ),
            secondary_y=False
        )
        
        cf_conversion_x, cf_conversion_y = filter_none_values(fy_ends, cf_conversion_values)[:2]
        fig_business_efficiency.add_trace(
            go.Scatter(
                x=cf_conversion_x,
                y=cf_conversion_y,
                mode='lines+markers',
                name='CF変換率 (%)',
                line=dict(color='#ff7f0e', width=3),
                marker=dict(size=8),
                hovertemplate='<b>%{x}年度</b><br>CF変換率: %{y:.2f}%<extra></extra>'
            ),
            secondary_y=True
        )
        
        fig_business_efficiency.update_xaxes(title_text="年度")
        fig_business_efficiency.update_yaxes(title_text="簡易ROIC (%)", secondary_y=False)
        fig_business_efficiency.update_yaxes(title_text="CF変換率 (%)", secondary_y=True)
        fig_business_efficiency.update_layout(
            title="",
            height=500,
            hovermode='closest',
            font=dict(size=14),
            template="plotly_white"
        )
        
        # 総合評価を計算（事業効率パターン）
        evaluation_business_efficiency = None
        if len(years) >= 2:
            valid_years_roic = []
            for i, year in enumerate(years):
                roic = roic_values[i] if i < len(roic_values) else None
                cf_conversion = cf_conversion_values[i] if i < len(cf_conversion_values) else None
                
                if is_valid_value(roic) and is_valid_value(cf_conversion):
                    valid_years_roic.append({
                        "year": year,
                        "roic": roic,
                        "cf_conversion": cf_conversion,
                        "index": i
                    })
            
            if len(valid_years_roic) >= 2:
                latest = valid_years_roic[0]
                oldest = valid_years_roic[-1]
                
                start_year = extract_year(oldest["year"].get("fy_end", ""))
                end_year = extract_year(latest["year"].get("fy_end", ""))
                
                period_years = len(valid_years_roic) - 1
                
                roic_start = oldest["roic"]
                roic_end = latest["roic"]
                cf_start = oldest["cf_conversion"]
                cf_end = latest["cf_conversion"]
                
                roic_cagr = calculate_cagr(roic_start, roic_end, period_years)
                cf_conversion_cagr = calculate_cagr(cf_start, cf_end, period_years)
                
                if roic_cagr is not None and cf_conversion_cagr is not None:
                    eval_result = evaluate_business_efficiency_pattern(roic_cagr, cf_conversion_cagr)
                    if eval_result:
                        eval_result["start_year"] = start_year
                        eval_result["end_year"] = end_year
                        evaluation_business_efficiency = eval_result
        
        html_div_be = pio.to_html(fig_business_efficiency, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
        graph_obj_be = {
            "section_title": "事業効率",
            "title": "簡易ROIC＝営業利益/純資産<br>CF変換率＝営業CF/営業利益",
            "html": html_div_be,
            "type": "interactive",
            "width": "full"
        }
        if evaluation_business_efficiency:
            graph_obj_be["evaluation"] = evaluation_business_efficiency
        graphs.append(graph_obj_be)
        
        # グラフ2：キャッシュフロー（営業CF + 投資CF + FCF）
        fig_cashflow = go.Figure()
        
        # 営業CF（棒グラフ、プラス/マイナス両対応）
        cfo_x, cfo_y = filter_none_values(fy_ends, cfo_values)[:2]
        cfo_y_million = [to_million(y) for y in cfo_y]
        fig_cashflow.add_trace(go.Bar(
            x=cfo_x,
            y=cfo_y,
            name="営業CF",
            marker_color="#17becf",
            customdata=cfo_y_million,
            hovertemplate='<b>%{x}年度</b><br>営業CF: %{customdata:,.0f}百万円<extra></extra>'
        ))
        
        # 投資CF（棒グラフ、プラス/マイナス両対応）
        cfi_x, cfi_y = filter_none_values(fy_ends, cfi_values)[:2]
        cfi_y_million = [to_million(y) for y in cfi_y]
        fig_cashflow.add_trace(go.Bar(
            x=cfi_x,
            y=cfi_y,
            name="投資CF",
            marker_color="#bcbd22",
            customdata=cfi_y_million,
            hovertemplate='<b>%{x}年度</b><br>投資CF: %{customdata:,.0f}百万円<extra></extra>'
        ))
        
        # FCF（折れ線グラフ）
        fcf_x, fcf_y = filter_none_values(fy_ends, fcf_values)[:2]
        fcf_y_million = [to_million(y) for y in fcf_y]
        fig_cashflow.add_trace(go.Scatter(
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
        fig_cashflow.add_hline(y=0, line_dash="dash", line_color="red", line_width=2)
        
        fig_cashflow.update_xaxes(title_text="年度")
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
        for i, year in enumerate(fy_ends):
            if i == 0:
                eps_text = f"<b>{year}年度</b><br>EPS: {eps_values[i]:.2f}円" if eps_values[i] is not None else f"<b>{year}年度</b><br>EPS: N/A"
                bps_text = f"<b>{year}年度</b><br>BPS: {bps_values[i]:.2f}円" if bps_values[i] is not None else f"<b>{year}年度</b><br>BPS: N/A"
                roe_text = f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{year}年度</b><br>ROE: N/A"
                hover_texts_eps.append(eps_text)
                hover_texts_bps.append(bps_text)
                hover_texts_roe.append(roe_text)
            else:
                eps_diff = eps_values[i] - eps_values[i-1] if eps_values[i] is not None and eps_values[i-1] is not None else None
                bps_diff = bps_values[i] - bps_values[i-1] if bps_values[i] is not None and bps_values[i-1] is not None else None
                roe_diff = roe_values[i] - roe_values[i-1] if roe_values[i] is not None and roe_values[i-1] is not None else None
                
                eps_text = f"<b>{year}年度</b><br>EPS: {eps_values[i]:.2f}円 ({eps_diff:+.2f}円)" if eps_values[i] is not None and eps_diff is not None else (f"<b>{year}年度</b><br>EPS: {eps_values[i]:.2f}円" if eps_values[i] is not None else f"<b>{year}年度</b><br>EPS: N/A")
                bps_text = f"<b>{year}年度</b><br>BPS: {bps_values[i]:.2f}円 ({bps_diff:+.2f}円)" if bps_values[i] is not None and bps_diff is not None else (f"<b>{year}年度</b><br>BPS: {bps_values[i]:.2f}円" if bps_values[i] is not None else f"<b>{year}年度</b><br>BPS: N/A")
                roe_text = f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}% ({roe_diff:+.2f}%)" if roe_values[i] is not None and roe_diff is not None else (f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{year}年度</b><br>ROE: N/A")
                hover_texts_eps.append(eps_text)
                hover_texts_bps.append(bps_text)
                hover_texts_roe.append(roe_text)
        
        # グラフ作成（EPS/BPS: 左軸、ROE: 右軸）
        fig_shareholder_value = make_subplots(specs=[[{"secondary_y": True}]])
        
        # EPS（左軸、表示順序1）
        eps_x, eps_y, eps_hover = filter_none_values(fy_ends, eps_values, hover_texts_eps)
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
            bps_x, bps_y, bps_hover = filter_none_values(fy_ends, bps_values, hover_texts_bps)
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
        roe_x, roe_y, roe_hover = filter_none_values(fy_ends, roe_values, hover_texts_roe)
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
        
        fig_shareholder_value.update_xaxes(title_text="年度")
        fig_shareholder_value.update_yaxes(title_text="EPS / BPS (円)", secondary_y=False)
        fig_shareholder_value.update_yaxes(title_text="ROE (%)", secondary_y=True)
        fig_shareholder_value.update_layout(
            title="",
            height=500,
            hovermode='closest',
            font=dict(size=14),
            template="plotly_white"
        )
        
        # 総合評価を計算（株主価値パターン：EPS × BPS × ROE）
        evaluation_shareholder_value = None
        if len(years) >= 2:
            valid_years_shareholder = []
            for i, year in enumerate(years):
                eps = eps_values[i] if i < len(eps_values) else None
                bps = bps_values[i] if i < len(bps_values) else None
                roe = roe_values[i] if i < len(roe_values) else None
                
                if is_valid_value(eps) and is_valid_value(bps) and is_valid_value(roe):
                    valid_years_shareholder.append({
                        "year": year,
                        "eps": eps,
                        "bps": bps,
                        "roe": roe,
                        "index": i
                    })
            
            if len(valid_years_shareholder) >= 2:
                latest = valid_years_shareholder[0]
                oldest = valid_years_shareholder[-1]
                
                start_year = extract_year(oldest["year"].get("fy_end", ""))
                end_year = extract_year(latest["year"].get("fy_end", ""))
                
                period_years = len(valid_years_shareholder) - 1
                
                eps_start = oldest["eps"]
                eps_end = latest["eps"]
                bps_start = oldest["bps"]
                bps_end = latest["bps"]
                roe_start = oldest["roe"]
                roe_end = latest["roe"]
                
                eps_cagr = calculate_cagr(eps_start, eps_end, period_years)
                bps_cagr = calculate_cagr(bps_start, bps_end, period_years)
                roe_cagr = calculate_cagr(roe_start, roe_end, period_years)
                
                if eps_cagr is not None and bps_cagr is not None and roe_cagr is not None:
                    eval_result = evaluate_shareholder_value_pattern(eps_cagr, bps_cagr, roe_cagr)
                    if eval_result:
                        eval_result["start_year"] = start_year
                        eval_result["end_year"] = end_year
                        evaluation_shareholder_value = eval_result
        
        html_div_sv = pio.to_html(fig_shareholder_value, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
        graph_obj_sv = {
            "section_title": "株主価値の蓄積",
            "title": "EPS＝1株当たり純利益<br>BPS＝1株当たり純資産<br>ROE＝当期純利益/純資産<br>（EPS÷BPS＝ROE）",
            "html": html_div_sv,
            "type": "interactive",
            "width": "full"
        }
        if evaluation_shareholder_value:
            graph_obj_sv["evaluation"] = evaluation_shareholder_value
        graphs.append(graph_obj_sv)
        
        # グラフ4：配当政策と市場評価（配当性向 × ROE × PBR）
        hover_texts_payout = []
        hover_texts_roe4 = []
        hover_texts_pbr4 = []
        for i, year in enumerate(fy_ends):
            payout = payout_ratio_values[i] if i < len(payout_ratio_values) else None
            roe = roe_values[i] if i < len(roe_values) else None
            pbr = pbr_values[i] if i < len(pbr_values) else None
            
            if i == 0:
                payout_text = f"<b>{year}年度</b><br>配当性向: {payout:.2f}%" if payout is not None else f"<b>{year}年度</b><br>配当性向: N/A"
                roe_text = f"<b>{year}年度</b><br>ROE: {roe:.2f}%" if roe is not None else f"<b>{year}年度</b><br>ROE: N/A"
                pbr_text = f"<b>{year}年度</b><br>PBR: {pbr:.2f}倍" if pbr is not None else f"<b>{year}年度</b><br>PBR: N/A"
                hover_texts_payout.append(payout_text)
                hover_texts_roe4.append(roe_text)
                hover_texts_pbr4.append(pbr_text)
            else:
                payout_diff = payout_ratio_values[i] - payout_ratio_values[i-1] if payout_ratio_values[i] is not None and payout_ratio_values[i-1] is not None else None
                roe_diff = roe_values[i] - roe_values[i-1] if roe_values[i] is not None and roe_values[i-1] is not None else None
                pbr_diff = pbr_values[i] - pbr_values[i-1] if pbr_values[i] is not None and pbr_values[i-1] is not None else None
                
                payout_text = f"<b>{year}年度</b><br>配当性向: {payout:.2f}% ({payout_diff:+.2f}%)" if payout is not None and payout_diff is not None else (f"<b>{year}年度</b><br>配当性向: {payout:.2f}%" if payout is not None else f"<b>{year}年度</b><br>配当性向: N/A")
                roe_text = f"<b>{year}年度</b><br>ROE: {roe:.2f}% ({roe_diff:+.2f}%)" if roe is not None and roe_diff is not None else (f"<b>{year}年度</b><br>ROE: {roe:.2f}%" if roe is not None else f"<b>{year}年度</b><br>ROE: N/A")
                pbr_text = f"<b>{year}年度</b><br>PBR: {pbr:.2f}倍 ({pbr_diff:+.2f}倍)" if pbr is not None and pbr_diff is not None else (f"<b>{year}年度</b><br>PBR: {pbr:.2f}倍" if pbr is not None else f"<b>{year}年度</b><br>PBR: N/A")
                hover_texts_payout.append(payout_text)
                hover_texts_roe4.append(roe_text)
                hover_texts_pbr4.append(pbr_text)
        
        # グラフ作成（配当性向: 左軸、ROE/PBR: 右軸）
        fig_dividend_policy = make_subplots(specs=[[{"secondary_y": True}]])
        
        # 配当性向（左軸）
        payout_x, payout_y, payout_hover = filter_none_values(fy_ends, payout_ratio_values, hover_texts_payout)
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
        roe4_x, roe4_y, roe4_hover = filter_none_values(fy_ends, roe_values, hover_texts_roe4)
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
        pbr4_x, pbr4_y, pbr4_hover = filter_none_values(fy_ends, pbr_values, hover_texts_pbr4)
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
        
        fig_dividend_policy.update_xaxes(title_text="年度")
        fig_dividend_policy.update_yaxes(title_text="配当性向 (%)", secondary_y=False)
        fig_dividend_policy.update_yaxes(title_text="ROE (%) / PBR (倍)", secondary_y=True)
        fig_dividend_policy.update_layout(
            title="",
            height=500,
            hovermode='closest',
            font=dict(size=14),
            template="plotly_white"
        )
        
        # 総合評価を計算（配当政策パターン：ROE × PBR × 配当性向）
        evaluation_dividend_policy = None
        if len(years) >= 2:
            valid_years_dividend = []
            for i, year in enumerate(years):
                roe = roe_values[i] if i < len(roe_values) else None
                pbr = pbr_values[i] if i < len(pbr_values) else None
                payout = payout_ratio_values[i] if i < len(payout_ratio_values) else None
                
                if is_valid_value(roe) and is_valid_value(pbr) and is_valid_value(payout):
                    valid_years_dividend.append({
                        "year": year,
                        "roe": roe,
                        "pbr": pbr,
                        "payout": payout,
                        "index": i
                    })
            
            if len(valid_years_dividend) >= 2:
                latest = valid_years_dividend[0]
                oldest = valid_years_dividend[-1]
                
                start_year = extract_year(oldest["year"].get("fy_end", ""))
                end_year = extract_year(latest["year"].get("fy_end", ""))
                
                period_years = len(valid_years_dividend) - 1
                
                roe_start = oldest["roe"]
                roe_end = latest["roe"]
                pbr_start = oldest["pbr"]
                pbr_end = latest["pbr"]
                payout_start = oldest["payout"]
                payout_end = latest["payout"]
                
                roe_cagr = calculate_cagr(roe_start, roe_end, period_years)
                pbr_cagr = calculate_cagr(pbr_start, pbr_end, period_years)
                payout_cagr = calculate_cagr(payout_start, payout_end, period_years)
                
                if roe_cagr is not None and pbr_cagr is not None and payout_cagr is not None:
                    eval_result = evaluate_dividend_policy_pattern(roe_cagr, pbr_cagr, payout_cagr)
                    if eval_result:
                        eval_result["start_year"] = start_year
                        eval_result["end_year"] = end_year
                        evaluation_dividend_policy = eval_result
        
        html_div_dp = pio.to_html(fig_dividend_policy, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
        graph_obj_dp = {
            "section_title": "配当政策と市場評価",
            "title": "配当性向＝配当総額/当期純利益<br>ROE＝当期純利益/純資産<br>PBR＝株価/BPS",
            "html": html_div_dp,
            "type": "interactive",
            "width": "full"
        }
        if evaluation_dividend_policy:
            graph_obj_dp["evaluation"] = evaluation_dividend_policy
        graphs.append(graph_obj_dp)
        
        # グラフ5：市場評価（PER × ROE × PBR）
        # 表示順序：PER → ROE → PBR
        hover_texts_per = []
        hover_texts_roe5 = []
        hover_texts_pbr5 = []
        for i, year in enumerate(fy_ends):
            if i == 0:
                per_text = f"<b>{year}年度</b><br>PER: {per_values[i]:.2f}倍" if per_values[i] is not None else f"<b>{year}年度</b><br>PER: N/A"
                roe_text = f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{year}年度</b><br>ROE: N/A"
                pbr_text = f"<b>{year}年度</b><br>PBR: {pbr_values[i]:.2f}倍" if pbr_values[i] is not None else f"<b>{year}年度</b><br>PBR: N/A"
                hover_texts_per.append(per_text)
                hover_texts_roe5.append(roe_text)
                hover_texts_pbr5.append(pbr_text)
            else:
                per_diff = per_values[i] - per_values[i-1] if per_values[i] is not None and per_values[i-1] is not None else None
                roe_diff = roe_values[i] - roe_values[i-1] if roe_values[i] is not None and roe_values[i-1] is not None else None
                pbr_diff = pbr_values[i] - pbr_values[i-1] if pbr_values[i] is not None and pbr_values[i-1] is not None else None
                
                per_text = f"<b>{year}年度</b><br>PER: {per_values[i]:.2f}倍 ({per_diff:+.2f}倍)" if per_values[i] is not None and per_diff is not None else (f"<b>{year}年度</b><br>PER: {per_values[i]:.2f}倍" if per_values[i] is not None else f"<b>{year}年度</b><br>PER: N/A")
                roe_text = f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}% ({roe_diff:+.2f}%)" if roe_values[i] is not None and roe_diff is not None else (f"<b>{year}年度</b><br>ROE: {roe_values[i]:.2f}%" if roe_values[i] is not None else f"<b>{year}年度</b><br>ROE: N/A")
                pbr_text = f"<b>{year}年度</b><br>PBR: {pbr_values[i]:.2f}倍 ({pbr_diff:+.2f}倍)" if pbr_values[i] is not None and pbr_diff is not None else (f"<b>{year}年度</b><br>PBR: {pbr_values[i]:.2f}倍" if pbr_values[i] is not None else f"<b>{year}年度</b><br>PBR: N/A")
                hover_texts_per.append(per_text)
                hover_texts_roe5.append(roe_text)
                hover_texts_pbr5.append(pbr_text)
        
        # グラフ作成（PER/PBR: 左軸、ROE: 右軸）
        fig_market_valuation = make_subplots(specs=[[{"secondary_y": True}]])
        
        # PER（左軸、表示順序1）
        per_x, per_y, per_hover = filter_none_values(fy_ends, per_values, hover_texts_per)
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
        pbr5_x, pbr5_y, pbr5_hover = filter_none_values(fy_ends, pbr_values, hover_texts_pbr5)
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
        roe5_x, roe5_y, roe5_hover = filter_none_values(fy_ends, roe_values, hover_texts_roe5)
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
        
        fig_market_valuation.update_xaxes(title_text="年度")
        fig_market_valuation.update_yaxes(title_text="PER (倍) / PBR (倍)", secondary_y=False)
        fig_market_valuation.update_yaxes(title_text="ROE (%)", secondary_y=True)
        fig_market_valuation.update_layout(
            title="",
            height=500,
            hovermode='closest',
            font=dict(size=14),
            template="plotly_white"
        )
        
        # 総合評価を計算（市場評価パターン：PER × ROE × PBR）
        evaluation_market_valuation = None
        if len(years) >= 2:
            valid_years_market = []
            for i, year in enumerate(years):
                per = per_values[i] if i < len(per_values) else None
                roe = roe_values[i] if i < len(roe_values) else None
                pbr = pbr_values[i] if i < len(pbr_values) else None
                
                if is_valid_value(per) and is_valid_value(roe) and is_valid_value(pbr):
                    valid_years_market.append({
                        "year": year,
                        "per": per,
                        "roe": roe,
                        "pbr": pbr,
                        "index": i
                    })
            
            if len(valid_years_market) >= 2:
                latest = valid_years_market[0]
                oldest = valid_years_market[-1]
                
                start_year = extract_year(oldest["year"].get("fy_end", ""))
                end_year = extract_year(latest["year"].get("fy_end", ""))
                
                period_years = len(valid_years_market) - 1
                
                per_start = oldest["per"]
                per_end = latest["per"]
                roe_start = oldest["roe"]
                roe_end = latest["roe"]
                pbr_start = oldest["pbr"]
                pbr_end = latest["pbr"]
                
                per_cagr = calculate_cagr(per_start, per_end, period_years)
                roe_cagr = calculate_cagr(roe_start, roe_end, period_years)
                pbr_cagr = calculate_cagr(pbr_start, pbr_end, period_years)
                
                if per_cagr is not None and roe_cagr is not None and pbr_cagr is not None:
                    eval_result = evaluate_market_valuation_pattern(per_cagr, roe_cagr, pbr_cagr)
                    if eval_result:
                        eval_result["start_year"] = start_year
                        eval_result["end_year"] = end_year
                        evaluation_market_valuation = eval_result
        
        html_div_mv = pio.to_html(fig_market_valuation, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
        graph_obj_mv = {
            "section_title": "市場評価",
            "title": "PER＝株価/EPS<br>ROE＝当期純利益/純資産<br>PBR＝株価/BPS<br>（PER×ROE＝PBR）",
            "html": html_div_mv,
            "type": "interactive",
            "width": "full"
        }
        if evaluation_market_valuation:
            graph_obj_mv["evaluation"] = evaluation_market_valuation
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
            
            html_div_pe = pio.to_html(fig_price_eps, include_plotlyjs='cdn', div_id=f"graph_{len(graphs)}")
            graphs.append({
                "section_title": "株価とEPSの乖離",
                "title": "株価指数＝(現在株価/基準年株価)×100<br>EPS指数＝(現在EPS/基準年EPS)×100",
                "html": html_div_pe,
                "type": "interactive",
                "width": "full"
            })
        
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
