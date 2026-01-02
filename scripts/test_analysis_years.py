#!/usr/bin/env python3
"""
分析年数の動作確認スクリプト

2年データと3年以上データの両方で動作することを確認します。
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api import JQuantsAPIClient
from src.analysis import IndividualAnalyzer
from src.config import config


def main():
    """メイン処理"""
    print("=" * 60)
    print("分析年数の動作確認")
    print("=" * 60)
    print()
    
    print(f"現在の設定:")
    print(f"  分析年数: {config.analysis_years}年")
    print(f"  プラン: {config.jquants_plan}")
    print(f"  最大年数: {config.get_max_analysis_years()}年")
    print()
    
    # APIクライアントの初期化
    try:
        api_client = JQuantsAPIClient()
        analyzer = IndividualAnalyzer(api_client, use_cache=True)
    except ValueError as e:
        print(f"エラー: {e}")
        return
    
    # テスト銘柄（味の素）
    test_code = "2802"
    print(f"テスト銘柄: {test_code} 味の素")
    print()
    
    # 分析実行
    print("分析中...")
    result = analyzer.get_report_data(test_code)
    
    if not result:
        print("❌ 分析に失敗しました")
        return
    
    metrics = result.get("metrics", {})
    years = metrics.get("years", [])
    
    print(f"\n取得できた年度データ: {len(years)}年分")
    for i, year in enumerate(years, 1):
        print(f"  {i}. {year.get('fy_end')}")
    print()
    
    # データ取得状況
    data_status = metrics.get("data_availability", "unknown")
    data_message = metrics.get("data_availability_message", "")
    print(f"データ取得状況: {data_status}")
    if data_message:
        print(f"  {data_message}")
    print()
    
    # 成長率の表示
    analysis_years = metrics.get("analysis_years", 2)
    if analysis_years >= 3:
        print("【CAGR（年平均成長率）】")
    else:
        print("【前年比成長率】")
    
    fcf_growth = metrics.get('fcf_growth') or metrics.get('fcf_cagr')
    roe_growth = metrics.get('roe_growth') or metrics.get('roe_cagr')
    eps_growth = metrics.get('eps_growth') or metrics.get('eps_cagr')
    sales_growth = metrics.get('sales_growth') or metrics.get('sales_cagr')
    
    print(f"  FCF: {fcf_growth:.1f}%" if fcf_growth is not None else "  FCF: N/A")
    print(f"  ROE: {roe_growth:.1f}%" if roe_growth is not None else "  ROE: N/A")
    print(f"  EPS: {eps_growth:.1f}%" if eps_growth is not None else "  EPS: N/A")
    print(f"  売上高: {sales_growth:.1f}%" if sales_growth is not None else "  売上高: N/A")
    print()
    
    print("=" * 60)
    print("動作確認完了")
    print("=" * 60)


if __name__ == "__main__":
    main()










