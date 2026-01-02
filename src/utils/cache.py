"""
キャッシュ管理モジュール
"""

import os
import json
import pickle
from datetime import datetime, date
from typing import Any, Optional, Dict
from pathlib import Path


class CacheManager:
    """キャッシュ管理クラス"""
    
    def __init__(self, cache_dir: str = "cache"):
        """
        初期化
        
        Args:
            cache_dir: キャッシュディレクトリのパス
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_file_path(self, key: str) -> Path:
        """キャッシュファイルのパスを取得"""
        # キーから安全なファイル名を生成
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe_key}.pkl"
    
    def _get_metadata_file_path(self) -> Path:
        """メタデータファイルのパスを取得"""
        return self.cache_dir / "metadata.json"
    
    def _load_metadata(self) -> Dict[str, str]:
        """メタデータを読み込み"""
        metadata_path = self._get_metadata_file_path()
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_metadata(self, metadata: Dict[str, str]):
        """メタデータを保存"""
        metadata_path = self._get_metadata_file_path()
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def get(self, key: str) -> Optional[Any]:
        """
        キャッシュからデータを取得
        
        Args:
            key: キャッシュキー
            
        Returns:
            キャッシュされたデータ。存在しないか期限切れの場合はNone
        """
        cache_file = self._get_cache_file_path(key)
        if not cache_file.exists():
            return None
        
        # メタデータを確認
        metadata = self._load_metadata()
        cache_date = metadata.get(key)
        
        if cache_date:
            cache_date_obj = datetime.fromisoformat(cache_date).date()
            today = date.today()
            
            # 日付が変わったらキャッシュを無効化
            if cache_date_obj < today:
                return None
        
        # キャッシュファイルを読み込み
        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except (pickle.UnpicklingError, IOError):
            return None
    
    def set(self, key: str, value: Any):
        """
        キャッシュにデータを保存
        
        Args:
            key: キャッシュキー
            value: 保存するデータ
        """
        cache_file = self._get_cache_file_path(key)
        
        # データを保存
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(value, f)
        except (pickle.PicklingError, IOError) as e:
            # キャッシュ保存に失敗しても処理は続行
            print(f"警告: キャッシュの保存に失敗しました: {e}")
            return
        
        # メタデータを更新
        metadata = self._load_metadata()
        metadata[key] = datetime.now().isoformat()
        self._save_metadata(metadata)
    
    def clear(self, key: Optional[str] = None):
        """
        キャッシュをクリア
        
        Args:
            key: クリアするキャッシュキー。Noneの場合は全キャッシュをクリア
        """
        if key:
            cache_file = self._get_cache_file_path(key)
            if cache_file.exists():
                cache_file.unlink()
            
            # メタデータからも削除
            metadata = self._load_metadata()
            if key in metadata:
                del metadata[key]
                self._save_metadata(metadata)
        else:
            # 全キャッシュをクリア
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
            
            # メタデータもクリア
            metadata_path = self._get_metadata_file_path()
            if metadata_path.exists():
                metadata_path.unlink()










