#!/usr/bin/env python3
"""
ウォッチリスト管理スクリプト

ウォッチリストの追加、削除、タグ管理を行います。
"""

import sys
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils import WatchlistManager


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description="ウォッチリスト管理")
    parser.add_argument(
        "--file",
        default="watchlist.json",
        help="ウォッチリストファイルのパス（デフォルト: watchlist.json）"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="コマンド")
    
    # 追加コマンド
    add_parser = subparsers.add_parser("add", help="銘柄を追加")
    add_parser.add_argument("code", help="銘柄コード")
    add_parser.add_argument("name", help="銘柄名")
    add_parser.add_argument("--tags", nargs="+", help="タグ（複数指定可能）")
    
    # 削除コマンド
    remove_parser = subparsers.add_parser("remove", help="銘柄を削除")
    remove_parser.add_argument("code", help="銘柄コード")
    
    # リスト表示コマンド
    list_parser = subparsers.add_parser("list", help="ウォッチリストを表示")
    list_parser.add_argument("--tag", help="タグでフィルタリング")
    
    # タグ更新コマンド
    tags_parser = subparsers.add_parser("tags", help="タグを更新")
    tags_parser.add_argument("code", help="銘柄コード")
    tags_parser.add_argument("--tags", nargs="+", required=True, help="タグ（複数指定可能）")
    
    # エクスポートコマンド
    export_parser = subparsers.add_parser("export", help="CSV形式でエクスポート")
    export_parser.add_argument("--output", default="watchlist.csv", help="出力ファイル")
    
    # インポートコマンド
    import_parser = subparsers.add_parser("import", help="CSV形式からインポート")
    import_parser.add_argument("--input", required=True, help="入力ファイル")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    watchlist = WatchlistManager(args.file)
    
    if args.command == "add":
        watchlist.add_stock(args.code, args.name, args.tags)
        print(f"✅ {args.code} {args.name} を追加しました")
        if args.tags:
            print(f"   タグ: {', '.join(args.tags)}")
    
    elif args.command == "remove":
        watchlist.remove_stock(args.code)
        print(f"✅ {args.code} を削除しました")
    
    elif args.command == "list":
        watchlist_data = watchlist.load()
        
        if args.tag:
            codes = watchlist.get_stocks_by_tag(args.tag)
            watchlist_data = {code: watchlist_data[code] for code in codes if code in watchlist_data}
        
        if not watchlist_data:
            print("ウォッチリストは空です")
            return
        
        print(f"ウォッチリスト: {len(watchlist_data)}銘柄")
        print("-" * 60)
        
        for code, data in sorted(watchlist_data.items()):
            name = data.get("name", "")
            tags = data.get("tags", [])
            tags_str = ", ".join(tags) if tags else "(タグなし)"
            print(f"{code} {name}")
            print(f"  タグ: {tags_str}")
            print()
    
    elif args.command == "tags":
        watchlist.update_tags(args.code, args.tags)
        print(f"✅ {args.code} のタグを更新しました: {', '.join(args.tags)}")
    
    elif args.command == "export":
        watchlist.export_to_csv(args.output)
        print(f"✅ {args.output} にエクスポートしました")
    
    elif args.command == "import":
        watchlist.import_from_csv(args.input)
        print(f"✅ {args.input} からインポートしました")


if __name__ == "__main__":
    main()










