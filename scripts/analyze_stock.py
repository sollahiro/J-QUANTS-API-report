#!/usr/bin/env python3
"""
個別銘柄分析スクリプト

指定した銘柄コードの詳細分析を実行します。
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api import JQuantsAPIClient
from src.analysis import IndividualAnalyzer
import pandas as pd


def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("使用方法: python3 scripts/analyze_stock.py <銘柄コード>")
        print("例: python3 scripts/analyze_stock.py 2802")
        return
    
    code = sys.argv[1]
    
    print("=" * 60)
    print(f"個別銘柄分析: {code}")
    print("=" * 60)
    print()
    
    # アナライザーを初期化
    try:
        api_client = JQuantsAPIClient()
        analyzer = IndividualAnalyzer(api_client, use_cache=True)
    except ValueError as e:
        print(f"エラー: {e}")
        return
    
    # 分析実行
    print("分析中...")
    try:
        result = analyzer.get_report_data(code)
    except Exception as e:
        error_msg = str(e)
        if "レート制限" in error_msg or "429" in error_msg:
            print(f"⚠️  レート制限に達しました")
            print("   無料プランには1日あたりのリクエスト数制限があります。")
            print("   しばらく時間をおいてから再試行してください。")
            print("   または、キャッシュ機能が有効な場合は以前のデータが使用されます。")
        else:
            print(f"❌ エラー: {error_msg}")
        return
    
    if not result:
        print(f"❌ {code} の分析に失敗しました")
        print("   データが取得できなかったか、財務データが不足している可能性があります。")
        return
    
    # 結果表示
    name = result.get("name", "")
    metrics = result.get("metrics", {})
    years = metrics.get("years", [])
    
    print(f"\n{'='*60}")
    print(f"銘柄: {code} {name}")
    print(f"{'='*60}")
    print()
    
    # データ取得時点を表示
    from datetime import datetime
    analyzed_at = result.get("analyzed_at")
    if analyzed_at:
        try:
            # ISO形式から読みやすい形式に変換
            dt = datetime.fromisoformat(analyzed_at.replace('Z', '+00:00'))
            analysis_time = dt.strftime("%Y年%m月%d日 %H:%M:%S")
        except:
            analysis_time = analyzed_at
    else:
        analysis_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    
    print("【データ取得時点】")
    print(f"📅 分析実行日時: {analysis_time}")
    
    # 最新の財務データ年度を表示
    if years:
        latest_fy_end = years[0].get("fy_end")
        if latest_fy_end:
            try:
                if len(latest_fy_end) == 10:  # YYYY-MM-DD
                    year, month, _ = latest_fy_end.split("-")
                    print(f"📊 最新財務データ: {year}年{month}月期")
                elif len(latest_fy_end) == 8:  # YYYYMMDD
                    print(f"📊 最新財務データ: {latest_fy_end[:4]}年{latest_fy_end[4:6]}月期")
                else:
                    print(f"📊 最新財務データ: {latest_fy_end}")
            except:
                print(f"📊 最新財務データ: {latest_fy_end}")
    print()
    
    # 基本情報
    print("【基本情報】")
    print(f"業種: {result.get('sector_33_name')} ({result.get('sector_33')})")
    print(f"市場: {result.get('market_name')}")
    
    # 決算時期を表示
    if years:
        latest_fy_end = years[0].get("fy_end")
        if latest_fy_end:
            try:
                if len(latest_fy_end) == 10:  # YYYY-MM-DD
                    _, month, _ = latest_fy_end.split("-")
                    print(f"決算時期: {int(month)}月")
                elif len(latest_fy_end) == 8:  # YYYYMMDD
                    month = latest_fy_end[4:6]
                    print(f"決算時期: {int(month)}月")
            except:
                pass
    
    if result.get("tags"):
        print(f"タグ: {', '.join(result.get('tags', []))}")
    print()
    
    # 財務データ表（実際の年数に応じて表示）
    if years:
        analysis_years = metrics.get("analysis_years", len(years))
        available_years = metrics.get("available_years", len(years))
        print(f"【{available_years}年分の財務データ】")
        if available_years < analysis_years:
            print(f"  ⚠️  注意: {analysis_years}年分のデータが必要ですが、{available_years}年分しか取得できませんでした")
        df_data = []
        for year in years:
            df_data.append({
                "年度終了日": year.get("fy_end"),
                "売上高": year.get("sales"),
                "営業利益": year.get("op"),
                "当期純利益": year.get("np"),
                "営業CF": year.get("cfo"),
                "投資CF": year.get("cfi"),
                "FCF": year.get("fcf"),
                "ROE(%)": year.get("roe"),
                "EPS": year.get("eps"),
                "PER": year.get("per"),
                "PBR": year.get("pbr"),
            })
        
        df = pd.DataFrame(df_data)
        print(df.to_string(index=False))
        print()
    
    # 成長率（データ年数に応じて前年比またはCAGR）
    analysis_years = metrics.get("analysis_years", 2)
    available_years = metrics.get("available_years", len(years))
    
    # 成長率の表示（2年分のデータでも表示可能）
    if available_years >= 2:
        # データ年数に応じて表示ラベルを変更
        if available_years >= 3:
            print("【CAGR（年平均成長率）】")
        else:
            print("【前年比成長率】")
        
        # 成長率の表示（growthまたはcagrを使用）
        fcf_growth = metrics.get('fcf_growth') or metrics.get('fcf_cagr')
        roe_growth = metrics.get('roe_growth') or metrics.get('roe_cagr')
        eps_growth = metrics.get('eps_growth') or metrics.get('eps_cagr')
        sales_growth = metrics.get('sales_growth') or metrics.get('sales_cagr')
        per_growth = metrics.get('per_growth') or metrics.get('per_cagr')
        pbr_growth = metrics.get('pbr_growth') or metrics.get('pbr_cagr')
        
        print(f"  FCF: {fcf_growth:.1f}%" if fcf_growth is not None else "  FCF: N/A")
        print(f"  ROE: {roe_growth:.1f}%" if roe_growth is not None else "  ROE: N/A")
        print(f"  EPS: {eps_growth:.1f}%" if eps_growth is not None else "  EPS: N/A")
        print(f"  売上高: {sales_growth:.1f}%" if sales_growth is not None else "  売上高: N/A")
        
        # PER、PBRの成長率も表示（2年分のデータがあれば）
        if per_growth is not None:
            print(f"  PER: {per_growth:.1f}%")
        if pbr_growth is not None:
            print(f"  PBR: {pbr_growth:.1f}%")
        
        if available_years < analysis_years:
            print(f"\n  ⚠️  注意: {analysis_years}年分のデータが必要ですが、{available_years}年分しか取得できませんでした")
        print()
    else:
        print("【成長率】")
        print("  ⚠️  成長率を計算するには最低2年分のデータが必要です")
        print()
    
    # 過去データとの比較
    comparison = result.get("comparison")
    if comparison:
        print("【過去分析結果との比較】")
        print(f"最新: {comparison.get('latest_date')}")
        print(f"前回: {comparison.get('previous_date')}")
        print()
        
        changes = comparison.get("changes", {})
        if changes:
            for metric, change_data in changes.items():
                change_pct = change_data.get("change_pct", 0)
                significant = change_data.get("significant", False)
                
                marker = "🔴" if significant else "  "
                print(f"{marker} {metric}:")
                print(f"   前回: {change_data.get('previous'):,.2f}")
                print(f"   最新: {change_data.get('latest'):,.2f}")
                print(f"   変化: {change_data.get('change'):+,.2f} ({change_pct:+.1f}%)")
                print()
    
    print("=" * 60)
    print("分析完了")
    print("=" * 60)
    print()
    print("詳細なグラフ表示はJupyter Notebookを使用してください：")
    print("  jupyter notebook notebooks/individual_analysis_template.ipynb")


if __name__ == "__main__":
    main()

