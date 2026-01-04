"""
パターンB：個別詳細分析モジュール
"""

import os
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..api.client import JQuantsAPIClient
from ..utils.financial_data import extract_annual_data
from ..utils.cache import CacheManager
from ..utils.watchlist import WatchlistManager
from ..analysis.calculator import calculate_metrics_flexible
from ..config import config


class IndividualAnalyzer:
    """個別詳細分析クラス"""
    
    def __init__(
        self,
        api_client: Optional[JQuantsAPIClient] = None,
        data_dir: str = "data",
        use_cache: bool = True,
        watchlist_file: Optional[str] = None
    ):
        """
        初期化
        
        Args:
            api_client: J-QUANTS APIクライアント。Noneの場合は新規作成
            data_dir: データ保存ディレクトリ
            use_cache: キャッシュを使用するか
            watchlist_file: ウォッチリストファイルのパス
        """
        self.api_client = api_client or JQuantsAPIClient()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache = CacheManager() if use_cache else None
        self.watchlist = WatchlistManager(watchlist_file) if watchlist_file else None
    
    def analyze_stock(
        self,
        code: str,
        save_data: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        個別銘柄を詳細分析
        
        Args:
            code: 銘柄コード（5桁）
            save_data: データをCSVに保存するか
            
        Returns:
            分析結果の辞書。エラー時はNone
        """
        cache_key = f"individual_analysis_{code}"
        
        # キャッシュから取得を試みる
        if self.cache:
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                print(f"💾 キャッシュからデータを取得しました: {code}")
                metrics = cached_result.get("metrics", {})
                years = metrics.get("years", [])
                analysis_years = metrics.get("analysis_years", len(years))
                print(f"  キャッシュデータ: {len(years)}年分（分析年数: {analysis_years}年）")
                return cached_result
        
        try:
            # 銘柄マスタから基本情報取得
            master_data = self.api_client.get_equity_master(code=code)
            stock_info = master_data[0] if master_data else {}
            stock_name = stock_info.get("CoName", "")
            
            # 財務データ取得
            financial_data = self.api_client.get_financial_summary(code=code)
            
            if not financial_data:
                return None
            
            # デバッグ: APIから取得された生データの確認
            name_display = f" {stock_name}" if stock_name else ""
            print(f"📥 APIから取得された財務データ: {len(financial_data)}件{name_display}")
            fy_records = [r for r in financial_data if r.get("CurPerType") == "FY"]
            print(f"📥 年度データ（CurPerType='FY'）: {len(fy_records)}件{name_display}")
            if fy_records:
                print("  年度終了日一覧:")
                for record in fy_records[:10]:  # 最大10件を表示
                    fy_end = record.get("CurFYEn", "")
                    disc_date = record.get("DiscDate", "")
                    print(f"    {fy_end} (開示日: {disc_date})")
            
            # 年度データ抽出
            annual_data = extract_annual_data(financial_data)
            
            if not annual_data:
                return None
            
            # デバッグ: 取得された年度データの確認
            name_display = f" {stock_name}" if stock_name else ""
            print(f"📊 取得された年度データ: {len(annual_data)}年分{name_display}")
            for i, year_data in enumerate(annual_data[:10]):  # 最大10年分を表示
                fy_end = year_data.get("CurFYEn", "")
                disc_date = year_data.get("DiscDate", "")
                print(f"  {i+1}. 年度終了日: {fy_end}, 開示日: {disc_date}")
            
            # 年度末株価を取得（利用可能なデータを最大限使用）
            # 休日の場合は直前の営業日を使用
            prices = {}
            # 分析年数: 利用可能な年数を使用（最大10年まで）
            available_years = len(annual_data)
            # 利用可能なデータを最大限使用（最大10年まで）
            max_years = config.get_max_analysis_years()
            analysis_years = min(available_years, max_years)
            
            print(f"📈 分析年数: {analysis_years}年（利用可能: {available_years}年、最大: {max_years}年）{name_display}")
            for year_data in annual_data[:analysis_years]:
                fy_end = year_data.get("CurFYEn")
                if fy_end:
                    # 年度終了日の形式を統一（YYYY-MM-DD）
                    if len(fy_end) == 8:  # YYYYMMDD形式
                        fy_end_formatted = f"{fy_end[:4]}-{fy_end[4:6]}-{fy_end[6:8]}"
                    else:
                        fy_end_formatted = fy_end
                    
                    # 休日の場合は直前の営業日を使用
                    price = self.api_client.get_price_at_date(
                        code, 
                        fy_end_formatted,
                        use_nearest_trading_day=True
                    )
                    if price:
                        prices[fy_end_formatted] = price
                        prices[fy_end.replace("-", "")] = price  # YYYYMMDD形式も保存
            
            # 指標計算（柔軟な年数対応）
            metrics = calculate_metrics_flexible(annual_data, prices, analysis_years)
            
            result = {
                "code": code,
                "name": stock_info.get("CoName"),
                "name_en": stock_info.get("CoNameEn"),
                "sector_33": stock_info.get("S33"),
                "sector_33_name": stock_info.get("S33Nm"),
                "sector_17": stock_info.get("S17"),
                "sector_17_name": stock_info.get("S17Nm"),
                "market": stock_info.get("Mkt"),
                "market_name": stock_info.get("MktNm"),
                "metrics": metrics,
                "analyzed_at": datetime.now().isoformat(),
            }
            
            # データ保存
            if save_data:
                self._save_to_csv(code, result)
            
            # キャッシュに保存
            if self.cache:
                self.cache.set(cache_key, result)
            
            return result
        
        except Exception as e:
            print(f"エラー: {code} の分析に失敗しました: {e}")
            return None
    
    def _save_to_csv(self, code: str, result: Dict[str, Any]):
        """
        分析結果をCSVに保存
        
        Args:
            code: 銘柄コード
            result: 分析結果
        """
        csv_path = self.data_dir / f"{code}.csv"
        
        metrics = result.get("metrics", {})
        years = metrics.get("years", [])
        
        if not years:
            return
        
        # CSVデータを準備
        rows = []
        for year_data in years:
            row = {
                "取得日時": result.get("analyzed_at"),
                "年度終了日": year_data.get("fy_end"),
                "売上高": year_data.get("sales"),
                "営業利益": year_data.get("op"),
                "当期純利益": year_data.get("np"),
                "純資産": year_data.get("eq"),
                "営業CF": year_data.get("cfo"),
                "投資CF": year_data.get("cfi"),
                "FCF": year_data.get("fcf"),
                "ROE": year_data.get("roe"),
                "EPS": year_data.get("eps"),
                "BPS": year_data.get("bps"),
                "株価": year_data.get("price"),
                "PER": year_data.get("per"),
                "PBR": year_data.get("pbr"),
            }
            rows.append(row)
        
        # CAGRデータを追加
        if rows:
            rows[0]["FCF_CAGR"] = metrics.get("fcf_cagr")
            rows[0]["ROE_CAGR"] = metrics.get("roe_cagr")
            rows[0]["EPS_CAGR"] = metrics.get("eps_cagr")
            rows[0]["売上高CAGR"] = metrics.get("sales_cagr")
            rows[0]["PER_CAGR"] = metrics.get("per_cagr")
            rows[0]["PBR_CAGR"] = metrics.get("pbr_cagr")
        
        # CSVに追記（履歴として保存）
        file_exists = csv_path.exists()
        
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            fieldnames = [
                "取得日時", "年度終了日", "売上高", "営業利益", "当期純利益",
                "純資産", "営業CF", "投資CF", "FCF", "ROE", "EPS", "BPS",
                "株価", "PER", "PBR", "FCF_CAGR", "ROE_CAGR", "EPS_CAGR",
                "売上高CAGR", "PER_CAGR", "PBR_CAGR"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerows(rows)
    
    def load_history(self, code: str) -> Optional[pd.DataFrame]:
        """
        過去の分析結果を読み込み
        
        Args:
            code: 銘柄コード
            
        Returns:
            過去データのDataFrame。存在しない場合はNone
        """
        csv_path = self.data_dir / f"{code}.csv"
        
        if not csv_path.exists():
            return None
        
        try:
            df = pd.read_csv(csv_path, encoding="utf-8")
            return df
        except Exception as e:
            print(f"エラー: {code} の履歴読み込みに失敗しました: {e}")
            return None
    
    def compare_with_previous(self, code: str) -> Optional[Dict[str, Any]]:
        """
        直前の分析結果と比較
        
        Args:
            code: 銘柄コード
            
        Returns:
            比較結果の辞書
        """
        history = self.load_history(code)
        
        if history is None or len(history) < 2:
            return None
        
        # 最新2回の分析結果を取得
        latest = history.iloc[-1]
        previous = history.iloc[-2]
        
        comparison = {
            "code": code,
            "latest_date": latest.get("取得日時"),
            "previous_date": previous.get("取得日時"),
            "changes": {},
        }
        
        # 各指標の変化を計算
        metrics_to_compare = [
            "FCF", "ROE", "EPS", "PER", "PBR", "売上高",
            "営業利益", "当期純利益", "営業CF"
        ]
        
        for metric in metrics_to_compare:
            latest_val = latest.get(metric)
            previous_val = previous.get(metric)
            
            if latest_val is not None and previous_val is not None:
                try:
                    latest_val = float(latest_val)
                    previous_val = float(previous_val)
                    
                    if previous_val != 0:
                        change_pct = ((latest_val - previous_val) / abs(previous_val)) * 100
                        comparison["changes"][metric] = {
                            "previous": previous_val,
                            "latest": latest_val,
                            "change": latest_val - previous_val,
                            "change_pct": change_pct,
                            "significant": abs(change_pct) >= 5.0,  # ±5%以上の変化
                        }
                except (ValueError, TypeError):
                    pass
        
        return comparison
    
    def get_report_data(self, code: str) -> Optional[Dict[str, Any]]:
        """
        レポート用データを取得
        
        Args:
            code: 銘柄コード
            
        Returns:
            レポート用データの辞書
        """
        # 先に銘柄名を取得してログに表示
        try:
            master_data = self.api_client.get_equity_master(code=code)
            stock_info = master_data[0] if master_data else {}
            stock_name = stock_info.get("CoName", "")
            name_display = f" {stock_name}" if stock_name else ""
        except Exception:
            name_display = ""
        
        print(f"🔍 get_report_data: {code}{name_display} の分析を開始します（キャッシュ: {'有効' if self.cache else '無効'}）")
        result = self.analyze_stock(code, save_data=True)
        
        if result:
            # 結果から銘柄名を取得（analyze_stockで取得済み）
            result_name = result.get("name", "")
            result_name_display = f" {result_name}" if result_name else name_display
            metrics = result.get("metrics", {})
            years = metrics.get("years", [])
            analysis_years = metrics.get("analysis_years", len(years))
            print(f"✅ 分析完了: {len(years)}年分のデータ（分析年数: {analysis_years}年）{result_name_display}")
        
        if not result:
            return None
        
        # 過去データとの比較
        comparison = self.compare_with_previous(code)
        
        # ウォッチリストからタグ情報を取得
        tags = []
        if self.watchlist:
            watchlist_data = self.watchlist.load()
            if code in watchlist_data:
                tags = watchlist_data[code].get("tags", [])
        
        # 四半期データ取得・分析（機能削除済み）
        quarterly_metrics = None
        
        report_data = {
            **result,
            "comparison": comparison,
            "tags": tags,
            "quarterly_metrics": quarterly_metrics,
        }
        
        return report_data
    
def evaluate_roe_eps_bps_pattern(roe_change: bool, eps_change: bool, bps_change: bool) -> Dict[str, Any]:
    """
    ROE/EPS/BPSの前年比から8パターン評価
    
    Args:
        roe_change: ROEの前年比（+: True, -: False）
        eps_change: EPSの前年比（+: True, -: False）
        bps_change: BPSの前年比（+: True, -: False）
    
    Returns:
        dict: {
            'pattern': 1-8,
            'name': '王道成長' など,
            'evaluation': '最良' など,
            'note': '効率も規模も拡大' など,
            'basis': 'ROE:+, EPS:+, BPS:+'
        }
    """
    # 8パターンのマッピング
    patterns = {
        (True, True, True): {
            'pattern': 1,
            'name': '王道成長',
            'evaluation': '最良',
            'note': '効率も規模も拡大',
            'basis': 'ROE:+, EPS:+, BPS:+'
        },
        (True, True, False): {
            'pattern': 2,
            'name': '異常',
            'evaluation': 'データ疑え',
            'note': '数式矛盾（要確認）',
            'basis': 'ROE:+, EPS:+, BPS:-'
        },
        (True, False, True): {
            'pattern': 3,
            'name': '効率改善',
            'evaluation': '良好',
            'note': '効率↑×規模維持',
            'basis': 'ROE:+, EPS:-, BPS:+'
        },
        (True, False, False): {
            'pattern': 4,
            'name': '効率改善',
            'evaluation': '要注意',
            'note': '効率↑×規模縮小',
            'basis': 'ROE:+, EPS:-, BPS:-'
        },
        (False, True, True): {
            'pattern': 5,
            'name': '規模拡大',
            'evaluation': '良好',
            'note': '効率↓×規模拡大',
            'basis': 'ROE:-, EPS:+, BPS:+'
        },
        (False, True, False): {
            'pattern': 6,
            'name': '異常',
            'evaluation': 'データ疑え',
            'note': '数式矛盾（要確認）',
            'basis': 'ROE:-, EPS:+, BPS:-'
        },
        (False, False, True): {
            'pattern': 7,
            'name': '規模維持',
            'evaluation': '要注意',
            'note': '効率↓×規模維持',
            'basis': 'ROE:-, EPS:-, BPS:+'
        },
        (False, False, False): {
            'pattern': 8,
            'name': '全面悪化',
            'evaluation': '最悪',
            'note': '効率も規模も縮小',
            'basis': 'ROE:-, EPS:-, BPS:-'
        }
    }
    
    key = (roe_change, eps_change, bps_change)
    return patterns.get(key, {
        'pattern': 0,
        'name': '不明',
        'evaluation': '評価不可',
        'note': 'データ不足',
        'basis': 'N/A'
    })


def evaluate_per_pbr_roe_pattern(per_change: bool, roe_change: bool, pbr_change: bool) -> Dict[str, Any]:
    """
    PER/PBR/ROEの前年比から8パターン評価
    
    Args:
        per_change: PERの前年比（+: True, -: False）
        roe_change: ROEの前年比（+: True, -: False）
        pbr_change: PBRの前年比（+: True, -: False）
    
    Returns:
        dict: {
            'pattern': 1-8,
            'name': '成長＋再評価' など,
            'evaluation': '初期良、後半注意' など,
            'note': '実力↑×期待↑' など,
            'basis': 'PER:+, ROE:+, PBR:+'
        }
    """
    # 8パターンのマッピング
    patterns = {
        (True, True, True): {
            'pattern': 1,
            'name': '成長＋再評価',
            'evaluation': '初期良、後半注意',
            'note': '実力↑×期待↑',
            'basis': 'PER:+, ROE:+, PBR:+'
        },
        (True, True, False): {
            'pattern': 2,
            'name': '成長＋期待先行',
            'evaluation': '要注意',
            'note': '実力↑×期待過大',
            'basis': 'PER:+, ROE:+, PBR:-'
        },
        (True, False, True): {
            'pattern': 3,
            'name': '期待先行',
            'evaluation': '要注意',
            'note': '実力↓×期待↑',
            'basis': 'PER:+, ROE:-, PBR:+'
        },
        (True, False, False): {
            'pattern': 4,
            'name': '期待先行',
            'evaluation': '最悪',
            'note': '実力↓×期待過大',
            'basis': 'PER:+, ROE:-, PBR:-'
        },
        (False, True, True): {
            'pattern': 5,
            'name': '成長＋割安',
            'evaluation': '最良',
            'note': '実力↑×期待↓',
            'basis': 'PER:-, ROE:+, PBR:+'
        },
        (False, True, False): {
            'pattern': 6,
            'name': '成長＋割安',
            'evaluation': '良好',
            'note': '実力↑×期待適正',
            'basis': 'PER:-, ROE:+, PBR:-'
        },
        (False, False, True): {
            'pattern': 7,
            'name': '割安',
            'evaluation': '要注意',
            'note': '実力↓×期待↓',
            'basis': 'PER:-, ROE:-, PBR:+'
        },
        (False, False, False): {
            'pattern': 8,
            'name': '全面悪化',
            'evaluation': '最悪',
            'note': '実力↓×期待↓',
            'basis': 'PER:-, ROE:-, PBR:-'
        }
    }
    
    key = (per_change, roe_change, pbr_change)
    return patterns.get(key, {
        'pattern': 0,
        'name': '不明',
        'evaluation': '評価不可',
        'note': 'データ不足',
        'basis': 'N/A'
    })


def evaluate_roe_eps_bps_pattern_by_cagr(roe_cagr: Optional[float], eps_cagr: Optional[float], bps_cagr: Optional[float]) -> Dict[str, Any]:
    """
    ROE/EPS/BPSのCAGRから8パターン評価
    
    Args:
        roe_cagr: ROEのCAGR（%）
        eps_cagr: EPSのCAGR（%）
        bps_cagr: BPSのCAGR（%）
    
    Returns:
        dict: {
            'pattern': 1-8,
            'name': '王道成長' など,
            'evaluation': '最良' など,
            'note': '効率も規模も拡大' など,
            'summary': '全期間で安定成長' など,
            'basis': 'ROE:+, EPS:+, BPS:+'
        }
    """
    if roe_cagr is None or eps_cagr is None or bps_cagr is None:
        return {
            'pattern': 0,
            'name': '不明',
            'evaluation': '評価不可',
            'note': 'データ不足',
            'summary': 'CAGRを計算できませんでした',
            'basis': 'N/A'
        }
    
    roe_positive = roe_cagr > 0
    eps_positive = eps_cagr > 0
    bps_positive = bps_cagr > 0
    
    patterns = {
        (True, True, True): {
            'pattern': 1,
            'name': '王道成長',
            'evaluation': '最良',
            'note': '効率も規模も拡大',
            'summary': '全期間で安定成長',
            'basis': 'ROE:+, EPS:+, BPS:+'
        },
        (True, True, False): {
            'pattern': 2,
            'name': '異常',
            'evaluation': 'データ疑え',
            'note': '数式矛盾（要確認）',
            'summary': 'データの整合性を確認',
            'basis': 'ROE:+, EPS:+, BPS:-'
        },
        (True, False, True): {
            'pattern': 3,
            'name': '効率改善',
            'evaluation': '良好',
            'note': '効率↑×規模維持',
            'summary': '効率重視の経営',
            'basis': 'ROE:+, EPS:-, BPS:+'
        },
        (True, False, False): {
            'pattern': 4,
            'name': '効率改善',
            'evaluation': '要注意',
            'note': '効率↑×規模縮小',
            'summary': '規模縮小傾向',
            'basis': 'ROE:+, EPS:-, BPS:-'
        },
        (False, True, True): {
            'pattern': 5,
            'name': '規模拡大',
            'evaluation': '良好',
            'note': '効率↓×規模拡大',
            'summary': '効率悪化しながら拡大',
            'basis': 'ROE:-, EPS:+, BPS:+'
        },
        (False, True, False): {
            'pattern': 6,
            'name': '異常',
            'evaluation': 'データ疑え',
            'note': '数式矛盾（要確認）',
            'summary': 'データの整合性を確認',
            'basis': 'ROE:-, EPS:+, BPS:-'
        },
        (False, False, True): {
            'pattern': 7,
            'name': '規模維持',
            'evaluation': '要注意',
            'note': '効率↓×規模維持',
            'summary': 'リストラ局面',
            'basis': 'ROE:-, EPS:-, BPS:+'
        },
        (False, False, False): {
            'pattern': 8,
            'name': '全面悪化',
            'evaluation': '最悪',
            'note': '効率も規模も縮小',
            'summary': '全面的な業績悪化',
            'basis': 'ROE:-, EPS:-, BPS:-'
        }
    }
    
    key = (roe_positive, eps_positive, bps_positive)
    return patterns.get(key, {
        'pattern': 0,
        'name': '不明',
        'evaluation': '評価不可',
        'note': 'データ不足',
        'summary': 'CAGRを計算できませんでした',
        'basis': 'N/A'
    })


def evaluate_per_pbr_roe_pattern_by_cagr(per_cagr: Optional[float], roe_cagr: Optional[float], pbr_cagr: Optional[float]) -> Dict[str, Any]:
    """
    PER/PBR/ROEのCAGRから8パターン評価
    
    Args:
        per_cagr: PERのCAGR（%）
        roe_cagr: ROEのCAGR（%）
        pbr_cagr: PBRのCAGR（%）
    
    Returns:
        dict: {
            'pattern': 1-8,
            'name': '成長＋再評価' など,
            'evaluation': '初期良、後半注意' など,
            'note': '実力↑×期待↑' など,
            'summary': '全期間で期待先行' など,
            'basis': 'PER:+, ROE:+, PBR:+'
        }
    """
    if per_cagr is None or roe_cagr is None or pbr_cagr is None:
        return {
            'pattern': 0,
            'name': '不明',
            'evaluation': '評価不可',
            'note': 'データ不足',
            'summary': 'CAGRを計算できませんでした',
            'basis': 'N/A'
        }
    
    per_positive = per_cagr > 0
    roe_positive = roe_cagr > 0
    pbr_positive = pbr_cagr > 0
    
    patterns = {
        (True, True, True): {
            'pattern': 1,
            'name': '成長＋再評価',
            'evaluation': '初期良、後半注意',
            'note': '実力↑×期待↑',
            'summary': '全期間で期待先行',
            'basis': 'PER:+, ROE:+, PBR:+'
        },
        (True, True, False): {
            'pattern': 2,
            'name': '成長＋期待先行',
            'evaluation': '要注意',
            'note': '実力↑×期待過大',
            'summary': '期待が先行しすぎ',
            'basis': 'PER:+, ROE:+, PBR:-'
        },
        (True, False, True): {
            'pattern': 3,
            'name': '期待先行',
            'evaluation': '要注意',
            'note': '実力↓×期待↑',
            'summary': '実力と期待の乖離',
            'basis': 'PER:+, ROE:-, PBR:+'
        },
        (True, False, False): {
            'pattern': 4,
            'name': '期待先行',
            'evaluation': '最悪',
            'note': '実力↓×期待過大',
            'summary': '実力不足で期待先行',
            'basis': 'PER:+, ROE:-, PBR:-'
        },
        (False, True, True): {
            'pattern': 5,
            'name': '成長＋割安',
            'evaluation': '最良',
            'note': '実力↑×期待↓',
            'summary': '実力向上で割安',
            'basis': 'PER:-, ROE:+, PBR:+'
        },
        (False, True, False): {
            'pattern': 6,
            'name': '成長＋割安',
            'evaluation': '良好',
            'note': '実力↑×期待適正',
            'summary': '実力向上で適正評価',
            'basis': 'PER:-, ROE:+, PBR:-'
        },
        (False, False, True): {
            'pattern': 7,
            'name': '割安',
            'evaluation': '要注意',
            'note': '実力↓×期待↓',
            'summary': '実力低下で割安',
            'basis': 'PER:-, ROE:-, PBR:+'
        },
        (False, False, False): {
            'pattern': 8,
            'name': '全面悪化',
            'evaluation': '最悪',
            'note': '実力↓×期待↓',
            'summary': '全面的な評価下落',
            'basis': 'PER:-, ROE:-, PBR:-'
        }
    }
    
    key = (per_positive, roe_positive, pbr_positive)
    return patterns.get(key, {
        'pattern': 0,
        'name': '不明',
        'evaluation': '評価不可',
        'note': 'データ不足',
        'summary': 'CAGRを計算できませんでした',
        'basis': 'N/A'
    })

