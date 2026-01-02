#!/usr/bin/env python3
"""
APIから取得されるデータを確認するテストスクリプト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api import JQuantsAPIClient
from src.utils.financial_data import extract_annual_data

def test_api_data(code: str = "6501"):
    """APIから取得されるデータを確認"""
    print(f"🔍 銘柄コード {code} のデータ取得テスト\n")
    
    # APIクライアントを初期化
    api_client = JQuantsAPIClient()
    
    # 財務データを取得
    print("📥 APIから財務データを取得中...")
    financial_data = api_client.get_financial_summary(code=code)
    
    print(f"\n✅ 取得完了: {len(financial_data)}件のデータ")
    
    # 年度データ（CurPerType="FY"）を抽出
    fy_data = [r for r in financial_data if r.get("CurPerType") == "FY"]
    print(f"📊 年度データ（CurPerType='FY'）: {len(fy_data)}件")
    
    # 年度終了日でグループ化
    fy_by_year = {}
    for record in fy_data:
        fy_end = record.get("CurFYEn", "")
        if fy_end:
            if fy_end not in fy_by_year:
                fy_by_year[fy_end] = []
            fy_by_year[fy_end].append(record)
    
    print(f"\n📅 年度終了日別のデータ数: {len(fy_by_year)}種類")
    print("\n年度終了日一覧（新しい順）:")
    for fy_end in sorted(fy_by_year.keys(), reverse=True):
        records = fy_by_year[fy_end]
        disc_dates = [r.get("DiscDate", "") for r in records]
        print(f"  {fy_end}: {len(records)}件 (開示日: {', '.join(disc_dates)})")
    
    # extract_annual_dataで処理
    print("\n🔄 extract_annual_dataで処理...")
    annual_data = extract_annual_data(financial_data)
    
    print(f"\n✅ 処理後: {len(annual_data)}年分のデータ")
    print("\n処理後の年度データ（新しい順）:")
    for i, year_data in enumerate(annual_data):
        fy_end = year_data.get("CurFYEn", "")
        disc_date = year_data.get("DiscDate", "")
        sales = year_data.get("Sales")
        print(f"  {i+1}. 年度終了日: {fy_end}, 開示日: {disc_date}, 売上高: {sales}")
    
    # 全データのCurPerTypeを確認
    print("\n📋 全データのCurPerType分布:")
    per_type_count = {}
    for record in financial_data:
        per_type = record.get("CurPerType", "不明")
        per_type_count[per_type] = per_type_count.get(per_type, 0) + 1
    
    for per_type, count in sorted(per_type_count.items()):
        print(f"  {per_type}: {count}件")
    
    return financial_data, annual_data

if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else "6501"
    test_api_data(code)









