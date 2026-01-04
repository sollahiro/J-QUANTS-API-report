#!/usr/bin/env python3
"""
API接続テストスクリプト

J-QUANTS APIへの接続と基本的な動作を確認します。
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api import JQuantsAPIClient
from src.utils import get_sector_list


def main():
    """メイン処理"""
    print("=" * 60)
    print("J-QUANTS API 接続テスト")
    print("=" * 60)
    print()
    
    # APIクライアントの初期化
    try:
        print("1. APIクライアントを初期化中...")
        api_client = JQuantsAPIClient()
        print("   ✅ APIクライアントの初期化に成功しました")
        print()
    except ValueError as e:
        print(f"   ❌ エラー: {e}")
        print()
        print("環境変数JQUANTS_API_KEYを設定してください。")
        print(".envファイルを作成し、以下のように設定してください：")
        print("  JQUANTS_API_KEY=your_api_key_here")
        return
    
    # 銘柄マスタの取得テスト
    try:
        print("2. 銘柄マスタを取得中...")
        master_data = api_client.get_equity_master()
        print(f"   ✅ 銘柄マスタの取得に成功しました（{len(master_data)}銘柄）")
        print()
        
        # サンプル銘柄を表示
        if master_data:
            print("   サンプル銘柄（最初の5件）:")
            for stock in master_data[:5]:
                code = stock.get("Code", "")
                name = stock.get("CoName", "")
                sector = stock.get("S33Nm", "")
                print(f"     {code} {name} ({sector})")
            print()
    except Exception as e:
        print(f"   ❌ エラー: {e}")
        return
    
    # 業種一覧の取得テスト
    try:
        print("3. 業種一覧を取得中...")
        sectors = get_sector_list(api_client)
        print(f"   ✅ 業種一覧の取得に成功しました（{len(sectors)}業種）")
        print()
        
        if sectors:
            print("   業種一覧（最初の10件）:")
            for sector in sectors[:10]:
                print(f"     {sector['code']}: {sector['name']}")
            print()
    except Exception as e:
        print(f"   ❌ エラー: {e}")
        return
    
    # テスト用銘柄の財務データ取得（1銘柄のみ）
    try:
        print("4. テスト銘柄の財務データを取得中...")
        # 最初の銘柄コードを取得
        test_code = master_data[0].get("Code")
        test_name = master_data[0].get("CoName")
        
        print(f"   対象銘柄: {test_code} {test_name}")
        financial_data = api_client.get_financial_summary(code=test_code)
        
        if financial_data:
            print(f"   ✅ 財務データの取得に成功しました（{len(financial_data)}件）")
            print()
            
            # 年度データを抽出
            from src.utils import extract_annual_data
            annual_data = extract_annual_data(financial_data)
            
            if annual_data:
                print(f"   年度データ: {len(annual_data)}件")
                print("   最新年度データ（最初の1件）:")
                latest = annual_data[0]
                print(f"     年度終了日: {latest.get('CurFYEn')}")
                sales = latest.get('Sales')
                op = latest.get('OP')
                np = latest.get('NP')
                print(f"     売上高: {sales:,.0f}" if sales is not None else "     売上高: N/A")
                print(f"     営業利益: {op:,.0f}" if op is not None else "     営業利益: N/A")
                print(f"     当期純利益: {np:,.0f}" if np is not None else "     当期純利益: N/A")
                print()
            else:
                print("   ⚠️  年度データが見つかりませんでした")
                print()
        else:
            print("   ⚠️  財務データが取得できませんでした")
            print()
    except Exception as e:
        print(f"   ❌ エラー: {e}")
        print()
    
    print("=" * 60)
    print("接続テスト完了")
    print("=" * 60)
    print()
    print("次のステップ:")
    print("1. 個別分析: python3 scripts/analyze_stock.py <銘柄コード>")
    print("2. Jupyter Notebookで詳細分析: python3 scripts/notebook_analysis.py <銘柄コード>")
    print("3. ウォッチリスト管理: python scripts/watchlist_manager.py list")


if __name__ == "__main__":
    main()

