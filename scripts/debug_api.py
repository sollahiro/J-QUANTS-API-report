#!/usr/bin/env python3
"""
API接続デバッグスクリプト

APIキーとベースURLの設定を確認します。
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

def main():
    """メイン処理"""
    print("=" * 60)
    print("API設定デバッグ")
    print("=" * 60)
    print()
    
    # .envファイルの読み込み
    env_path = project_root / ".env"
    if env_path.exists():
        print(f"✅ .envファイルが見つかりました: {env_path}")
        load_dotenv(env_path)
    else:
        print(f"❌ .envファイルが見つかりません: {env_path}")
        print("   .env.exampleをコピーして.envを作成してください")
        return
    
    # APIキーの確認
    api_key = os.getenv("JQUANTS_API_KEY")
    if api_key:
        # 最初と最後の数文字だけ表示（セキュリティのため）
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"✅ APIキーが設定されています: {masked_key}")
        print(f"   長さ: {len(api_key)}文字")
        
        # 空白チェック
        if api_key != api_key.strip():
            print("   ⚠️  警告: APIキーに前後の空白が含まれています")
            print("   空白を削除してください")
    else:
        print("❌ APIキーが設定されていません")
        print("   .envファイルに JQUANTS_API_KEY=your_api_key を設定してください")
    
    # ベースURLの確認
    base_url = os.getenv("JQUANTS_API_BASE_URL", "https://api.jquants.com/v1")
    print(f"\n✅ ベースURL: {base_url}")
    
    # 推奨設定
    print("\n" + "=" * 60)
    print("推奨設定")
    print("=" * 60)
    print()
    print("J-QUANTS APIはV2に移行している可能性があります。")
    print("もしV1で403エラーが出る場合は、以下を試してください：")
    print()
    print(".envファイルに以下を追加/変更：")
    print("  JQUANTS_API_BASE_URL=https://api.jquants.com/v2")
    print()
    print("または、V1の場合は：")
    print("  JQUANTS_API_BASE_URL=https://api.jquants.com/v1")
    print()
    
    # 実際のAPIリクエストテスト
    if api_key:
        print("=" * 60)
        print("APIリクエストテスト")
        print("=" * 60)
        print()
        
        try:
            from src.api import JQuantsAPIClient
            
            # V1で試す
            print("V1でテスト中...")
            try:
                client_v1 = JQuantsAPIClient(base_url="https://api.jquants.com/v1")
                master = client_v1.get_equity_master()
                print(f"   ✅ V1で成功: {len(master)}銘柄取得")
            except Exception as e:
                print(f"   ❌ V1で失敗: {e}")
            
            # V2で試す
            print("\nV2でテスト中...")
            try:
                client_v2 = JQuantsAPIClient(base_url="https://api.jquants.com/v2")
                master = client_v2.get_equity_master()
                print(f"   ✅ V2で成功: {len(master)}銘柄取得")
                print("\n   ⚠️  V2が動作する場合は、.envファイルに以下を設定してください：")
                print("   JQUANTS_API_BASE_URL=https://api.jquants.com/v2")
            except Exception as e:
                print(f"   ❌ V2で失敗: {e}")
        
        except Exception as e:
            print(f"エラー: {e}")


if __name__ == "__main__":
    main()










