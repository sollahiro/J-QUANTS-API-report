#!/usr/bin/env python3
"""
Jupyter Notebook起動ラッパースクリプト

銘柄コードを引数として受け取り、環境変数に設定してから
Jupyter Notebookを起動します。

使用方法:
    python3 scripts/notebook_analysis.py 6501
    python3 scripts/notebook_analysis.py 6501 2802  # 複数銘柄
"""

import sys
import os
import subprocess
from pathlib import Path


def main():
    """メイン処理"""
    if len(sys.argv) < 2:
        print("使用方法: python3 scripts/notebook_analysis.py <銘柄コード> [銘柄コード2 ...]")
        print("例: python3 scripts/notebook_analysis.py 6501")
        print("例: python3 scripts/notebook_analysis.py 6501 2802")
        return 1
    
    # 銘柄コードを取得
    stock_codes = sys.argv[1:]
    
    # 環境変数に設定（カンマ区切り）
    os.environ["NOTEBOOK_STOCK_CODES"] = ",".join(stock_codes)
    
    # プロジェクトルートを取得
    project_root = Path(__file__).parent.parent
    notebook_path = project_root / "notebooks" / "individual_analysis_template.ipynb"
    
    if not notebook_path.exists():
        print(f"❌ エラー: ノートブックが見つかりません: {notebook_path}")
        return 1
    
    print("=" * 60)
    print("Jupyter Notebook 起動")
    print("=" * 60)
    print(f"分析対象銘柄: {', '.join(stock_codes)}")
    print(f"ノートブック: {notebook_path}")
    print()
    print("ノートブック内で環境変数から銘柄コードが自動的に読み込まれます。")
    print()
    
    # Jupyter Notebookを起動
    try:
        subprocess.run(
            ["jupyter", "notebook", str(notebook_path)],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ エラー: Jupyter Notebookの起動に失敗しました: {e}")
        return 1
    except FileNotFoundError:
        print("❌ エラー: jupyter コマンドが見つかりません")
        print("   Jupyter Notebookがインストールされているか確認してください。")
        print("   インストール: pip install jupyter")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())










