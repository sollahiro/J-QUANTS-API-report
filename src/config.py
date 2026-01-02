"""
設定管理モジュール

環境変数から設定を読み込み、アプリケーション全体で使用する設定値を管理します。
"""

import os
from typing import Optional
from dotenv import load_dotenv


class Config:
    """アプリケーション設定クラス"""
    
    def __init__(self):
        """環境変数を読み込み"""
        load_dotenv()
        
        # J-QUANTS API設定
        self.api_key = os.getenv("JQUANTS_API_KEY")
        self.api_base_url = os.getenv(
            "JQUANTS_API_BASE_URL",
            "https://api.jquants.com/v2"
        )
        
        # 分析設定
        # ANALYSIS_YEARSは環境変数で指定可能（指定しない場合は利用可能なデータを最大限使用）
        analysis_years_str = os.getenv("ANALYSIS_YEARS")
        if analysis_years_str:
            self.analysis_years = int(analysis_years_str)
        else:
            self.analysis_years = None  # Noneの場合は利用可能なデータを最大限使用
        
        self.jquants_plan = os.getenv("JQUANTS_PLAN", "free").lower()
        
        # プランに応じた最大年数の設定（最大10年）
        self.max_years_by_plan = {
            "free": 10,  # 無料プランでも取得できる限り使用（最大10年）
            "light": 10,
            "standard": 10,
            "premium": 10,
        }
        
        # キャッシュ設定
        self.cache_dir = os.getenv("CACHE_DIR", "cache")
        self.cache_enabled = os.getenv("CACHE_ENABLED", "true").lower() == "true"
        
        # データ保存設定
        self.data_dir = os.getenv("DATA_DIR", "data")
    
    def get_max_analysis_years(self) -> int:
        """
        プランに応じた最大分析年数を取得
        
        Returns:
            最大分析年数（デフォルト: 10年）
        """
        return self.max_years_by_plan.get(self.jquants_plan, 10)
    
    def is_premium_plan(self) -> bool:
        """
        有料プランかどうかを判定
        
        Returns:
            有料プラン（light/standard/premium）の場合True
        """
        return self.jquants_plan in ["light", "standard", "premium"]
    
    def can_use_cagr(self, analysis_years: Optional[int] = None) -> bool:
        """
        CAGR計算が可能かどうかを判定（3年以上のデータが必要）
        
        Args:
            analysis_years: 分析年数（Noneの場合は設定値を使用）
        
        Returns:
            分析年数が3年以上の場合True
        """
        years = analysis_years if analysis_years is not None else self.analysis_years
        return years is not None and years >= 3


# グローバル設定インスタンス
config = Config()

