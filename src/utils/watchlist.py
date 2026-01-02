"""
ウォッチリスト管理モジュール
"""

import json
import csv
from typing import List, Dict, Any, Optional
from pathlib import Path


class WatchlistManager:
    """ウォッチリスト管理クラス"""
    
    def __init__(self, watchlist_file: str = "watchlist.json"):
        """
        初期化
        
        Args:
            watchlist_file: ウォッチリストファイルのパス（JSON形式）
        """
        self.watchlist_file = Path(watchlist_file)
        self.watchlist_file.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Dict[str, Dict[str, Any]]:
        """
        ウォッチリストを読み込み
        
        Returns:
            ウォッチリストの辞書 {銘柄コード: {name, tags}}
        """
        if not self.watchlist_file.exists():
            return {}
        
        try:
            with open(self.watchlist_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def save(self, watchlist: Dict[str, Dict[str, Any]]):
        """
        ウォッチリストを保存
        
        Args:
            watchlist: ウォッチリストの辞書
        """
        with open(self.watchlist_file, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=2)
    
    def add_stock(
        self,
        code: str,
        name: str,
        tags: Optional[List[str]] = None
    ):
        """
        銘柄を追加
        
        Args:
            code: 銘柄コード
            name: 銘柄名
            tags: タグのリスト
        """
        watchlist = self.load()
        watchlist[code] = {
            "name": name,
            "tags": tags or []
        }
        self.save(watchlist)
    
    def remove_stock(self, code: str):
        """
        銘柄を削除
        
        Args:
            code: 銘柄コード
        """
        watchlist = self.load()
        if code in watchlist:
            del watchlist[code]
            self.save(watchlist)
    
    def update_tags(self, code: str, tags: List[str]):
        """
        銘柄のタグを更新
        
        Args:
            code: 銘柄コード
            tags: タグのリスト
        """
        watchlist = self.load()
        if code in watchlist:
            watchlist[code]["tags"] = tags
            self.save(watchlist)
    
    def get_stocks_by_tag(self, tag: str) -> List[str]:
        """
        タグでフィルタリング
        
        Args:
            tag: タグ名
            
        Returns:
            該当する銘柄コードのリスト
        """
        watchlist = self.load()
        return [
            code for code, data in watchlist.items()
            if tag in data.get("tags", [])
        ]
    
    def get_all_tags(self) -> List[str]:
        """
        全タグのリストを取得
        
        Returns:
            タグのリスト（重複除去、ソート済み）
        """
        watchlist = self.load()
        tags = set()
        
        for data in watchlist.values():
            tags.update(data.get("tags", []))
        
        return sorted(list(tags))
    
    def export_to_csv(self, csv_file: str):
        """
        CSV形式でエクスポート
        
        Args:
            csv_file: 出力CSVファイルのパス
        """
        watchlist = self.load()
        
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["銘柄コード", "銘柄名", "タグ"])
            
            for code, data in sorted(watchlist.items()):
                name = data.get("name", "")
                tags = ",".join(data.get("tags", []))
                writer.writerow([code, name, tags])
    
    def import_from_csv(self, csv_file: str):
        """
        CSV形式からインポート
        
        Args:
            csv_file: 入力CSVファイルのパス
        """
        watchlist = self.load()
        
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get("銘柄コード", "").strip()
                name = row.get("銘柄名", "").strip()
                tags_str = row.get("タグ", "").strip()
                
                if code:
                    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                    watchlist[code] = {
                        "name": name,
                        "tags": tags
                    }
        
        self.save(watchlist)










