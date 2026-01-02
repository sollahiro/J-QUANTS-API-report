#!/usr/bin/env python3
"""
パターンA：スクリーニング実行スクリプト

全市場からFCF 3年連続プラスの銘柄をスクリーニングします。

使用方法:
    python3 scripts/screening.py                    # 全業種、合格銘柄上位10件を表示
    python3 scripts/screening.py 3050               # 特定業種（食料品）、合格銘柄上位10件を表示
    python3 scripts/screening.py 3050 --count 20    # 合格銘柄上位20件を表示
    python3 scripts/screening.py 3050 3650          # 複数業種（食料品、電気機器）
"""

import sys
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api import JQuantsAPIClient
from src.analysis import ScreeningAnalyzer
from src.utils import get_sector_list


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="J-QUANTS API 投資判断分析ツール - スクリーニング",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s                    # 全業種をスクリーニング
  %(prog)s 3050               # 食料品のみ
  %(prog)s 3050 3650          # 食料品と電気機器
  %(prog)s --list             # 利用可能な業種一覧を表示
        """
    )
    parser.add_argument(
        "sectors",
        nargs="*",
        help="業種コード（33業種分類）。複数指定可能。指定しない場合は全業種"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="利用可能な業種一覧を表示して終了"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="表示する合格銘柄数（デフォルト: 10、最大: 20）。合格銘柄から上位N件を表示（分析数は自動的に表示数+5件、最大50）"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="各リクエスト間の待機時間（秒、デフォルト: 1.0）。レート制限を避けるため"
    )
    parser.add_argument(
        "--no-random",
        action="store_true",
        help="ランダム選択を無効化（銘柄コード順で選択）。デフォルトはランダム選択"
    )
    parser.add_argument(
        "--no-early-exit",
        action="store_true",
        help="早期終了を無効化（全銘柄を分析してからソート）。デフォルトは早期終了"
    )
    
    args = parser.parse_args()
    
    # 表示銘柄数の上限チェック（最大20）
    if args.count > 20:
        print(f"⚠️  エラー: 表示銘柄数は最大20までです（指定: {args.count}）")
        args.count = 20
        print(f"   表示銘柄数を20に調整しました")
    
    # 分析数の自動計算（表示数+5件、最大50）
    # 表示上限が20なので、実際の分析数は最大25件（20 + 5）
    max_analysis = min(args.count + 5, 50)
    
    print("=" * 60)
    print("J-QUANTS API 投資判断分析ツール - スクリーニング")
    print("=" * 60)
    print()
    
    # APIクライアントとアナライザーを初期化
    try:
        api_client = JQuantsAPIClient()
        analyzer = ScreeningAnalyzer(api_client, use_cache=True)
    except ValueError as e:
        print(f"エラー: {e}")
        print("環境変数JQUANTS_API_KEYを設定してください。")
        return
    
    # 業種一覧を取得
    sectors = get_sector_list(api_client)
    
    # 業種一覧を表示して終了
    if args.list:
        print("利用可能な業種:")
        for sector in sectors:
            print(f"  {sector['code']}: {sector['name']}")
        return
    
    # 業種フィルタの設定
    if args.sectors:
        # コマンドライン引数で指定された業種コード
        sector_filter = args.sectors
        
        # 業種コードの妥当性チェック
        valid_codes = {s["code"] for s in sectors}
        invalid_codes = [code for code in sector_filter if code not in valid_codes]
        if invalid_codes:
            print(f"⚠️  エラー: 無効な業種コード: {', '.join(invalid_codes)}")
            print()
            print("利用可能な業種:")
            for sector in sectors:
                print(f"  {sector['code']}: {sector['name']}")
            return
        
        sector_names = [s["name"] for s in sectors if s["code"] in sector_filter]
    else:
        # スクリプト内で直接設定する場合（コマンドライン引数がない場合）
        # 以下を編集して業種コードを指定してください
        # 例: sector_filter = ["3050"]  # 食料品のみ
        # 例: sector_filter = ["3050", "3650"]  # 食料品と電気機器
        sector_filter = None  # 全業種
        
        # スクリプト内で直接設定する場合は、以下のコメントを外して編集
        # sector_filter = ["3050"]  # 食料品のみ
        # sector_filter = ["3050", "3650"]  # 食料品と電気機器
        sector_names = None
    
    # スクリーニング実行
    print("スクリーニングを開始します...")
    if sector_filter:
        if not sector_names:
            sector_names = [s["name"] for s in sectors if s["code"] in sector_filter]
        print(f"対象業種: {', '.join(sector_names)}")
        print(f"対象業種コード: {', '.join(sector_filter)}")
    else:
        print("対象業種: 全業種")
    
    # 分析・表示設定
    output_count = args.count
    
    # 早期終了の設定（デフォルトは有効）
    use_early_exit = not args.no_early_exit
    early_exit_count = output_count if use_early_exit else None
    
    if use_early_exit:
        print(f"（最大{max_analysis}銘柄を分析、合格銘柄が{output_count}件に達したら早期終了してソート）")
    else:
        print(f"（{max_analysis}銘柄を全分析してからソート）")
    print()
    
    # ランダム選択の設定（デフォルトはTrue、--no-randomでFalse）
    use_random = not args.no_random
    
    passed_stocks, skipped_stocks = analyzer.screen_all_stocks(
        sector_filter=sector_filter,
        max_stocks=max_analysis,
        request_delay=args.delay,
        random_sample=use_random,
        early_exit_count=early_exit_count
    )
    
    # 結果表示
    print()
    print("=" * 60)
    print("スクリーニング結果")
    print("=" * 60)
    print()
    
    # データ取得時点を表示
    from datetime import datetime
    analysis_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    print(f"📅 分析実行日時: {analysis_time}")
    
    # 最新の財務データ年度を取得（最初の合格銘柄から）
    if passed_stocks:
        first_stock = passed_stocks[0]
        metrics = first_stock.get("metrics", {})
        years = metrics.get("years", [])
        if years:
            latest_fy_end = years[0].get("fy_end")
            if latest_fy_end:
                # YYYY-MM-DD形式をYYYY年MM月に変換
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
    
    if passed_stocks:
        total_passed = len(passed_stocks)
        
        # 表示する合格銘柄数を制限
        if output_count < total_passed:
            print(f"✅ 合格銘柄: {total_passed}銘柄（上位{output_count}銘柄を表示）")
            # ソート後に上位N件を取得
            passed_stocks_for_display = passed_stocks[:output_count]
        else:
            print(f"✅ 合格銘柄: {total_passed}銘柄（全件表示）")
            passed_stocks_for_display = passed_stocks
        print()
        
        # サマリービューを取得（ROE順でソート）
        summaries = analyzer.get_summary_view(passed_stocks_for_display, sort_by="roe")
        
        print("【サマリービュー（ROE順）】")
        print("-" * 60)
        for summary in summaries:
            code = summary.get("code", "")
            name = summary.get("name", "")
            fcf = summary.get("fcf")
            roe = summary.get("roe")
            eps = summary.get("eps")
            per = summary.get("per")
            pbr = summary.get("pbr")
            fiscal_period = summary.get("fiscal_period")
            
            # 決算時期の表示
            fiscal_period_str = fiscal_period if fiscal_period else "決算時期不明"
            
            print(f"銘柄コード: {code} | {name} ({fiscal_period_str})")
            
            # FCFの表示
            if fcf:
                print(f"  FCF: {fcf:,.0f}")
            else:
                print("  FCF: N/A")
            
            print(f"  ROE: {roe:.2f}%" if roe else "  ROE: N/A")
            print(f"  EPS: {eps:.2f}" if eps else "  EPS: N/A")
            print(f"  PER: {per:.2f} | PBR: {pbr:.2f}" if per and pbr else f"  PER: {per:.2f}" if per else "  PER: N/A")
            print()
    else:
        print("合格銘柄はありませんでした。")
        print()


if __name__ == "__main__":
    main()

