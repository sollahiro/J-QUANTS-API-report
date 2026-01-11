"""
個別詳細分析モジュール

個別銘柄の詳細分析を実行します。
"""

import csv
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from ..api.client import JQuantsAPIClient
from ..utils.financial_data import extract_annual_data
from ..utils.cache import CacheManager
from ..analysis.calculator import calculate_metrics_flexible
from ..config import config

logger = logging.getLogger(__name__)

# EDINET統合（オプション）
try:
    from ..api.edinet_client import EdinetAPIClient
    from ..analysis.xbrl_parser import XBRLParser
    from ..analysis.llm_summarizer import LLMSummarizer
    from ..utils.xbrl_compressor import compress_text
    EDINET_AVAILABLE = True
except ImportError:
    EDINET_AVAILABLE = False
    logger.debug("EDINET統合モジュールが利用できません。")


class IndividualAnalyzer:
    """個別詳細分析クラス"""
    
    def __init__(
        self,
        api_client: Optional[JQuantsAPIClient] = None,
        data_dir: str = "data",
        use_cache: bool = True
    ):
        """
        初期化
        
        Args:
            api_client: J-QUANTS APIクライアント。Noneの場合は新規作成
            data_dir: データ保存ディレクトリ
            use_cache: キャッシュを使用するか
        """
        self.api_client = api_client or JQuantsAPIClient()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache = CacheManager() if use_cache else None
        
        # EDINET統合（オプション）
        if EDINET_AVAILABLE:
            try:
                self.edinet_client = EdinetAPIClient()
                self.xbrl_parser = XBRLParser()  # XBRLは要約用
                self.llm_summarizer = LLMSummarizer()
            except Exception as e:
                logger.warning(f"EDINETクライアントの初期化に失敗しました: {e}")
                self.edinet_client = None
                self.xbrl_parser = None
                self.llm_summarizer = None
        else:
            self.edinet_client = None
            self.xbrl_parser = None
            self.llm_summarizer = None
    
    def analyze_stock(
        self,
        code: str,
        save_data: bool = True,
        progress_callback: Optional[Callable] = None
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
                
                # EDINETデータがキャッシュにない場合のみ取得（無駄なAPI呼び出しを避ける）
                cached_edinet_data = cached_result.get("edinet_data", {})
                if self.edinet_client and not cached_edinet_data:
                    try:
                        logger.info(f"EDINET検索開始（キャッシュにEDINETデータなし）: code={code}")
                        # J-QUANTSデータから最新4データを取得（開示日基準、FY/2Q区別なし）
                        from ..utils.financial_data import _calculate_quarter_end_date
                        
                        # J-QUANTSデータを取得
                        try:
                            financial_data = self.api_client.get_financial_summary(code=code)
                        except Exception as e:
                            logger.warning(f"J-QUANTSデータ取得エラー: {e}")
                            financial_data = None
                        
                        if not financial_data:
                            logger.warning(f"J-QUANTSデータが取得できませんでした: code={code}")
                            return cached_result
                        
                        # FYと2Qのデータのみを抽出
                        fy_and_q2_records = [
                            r for r in financial_data 
                            if r.get("CurPerType") in ["FY", "2Q"]
                        ]
                        
                        # DiscDateでソート（降順、最新が最初）
                        all_records_sorted = sorted(
                            fy_and_q2_records,
                            key=lambda x: x.get("DiscDate", ""),
                            reverse=True
                        )
                        
                        # 最新4データを取得
                        latest_4_records = all_records_sorted[:4]
                        
                        annual_data_for_edinet = []
                        for record in latest_4_records:
                            fy_end = record.get("CurFYEn", "")
                            disc_date = record.get("DiscDate", "")
                            period_type = record.get("CurPerType", "FY")
                            
                            # 年度を計算
                            fiscal_year = None
                            period_date = None
                            period_end_str = fy_end  # デフォルトは年度終了日
                            
                            if fy_end:
                                try:
                                    if len(fy_end) >= 10:
                                        period_date = datetime.strptime(fy_end[:10], "%Y-%m-%d")
                                    elif len(fy_end) >= 8:
                                        period_date = datetime.strptime(fy_end[:8], "%Y%m%d")
                                    
                                    if period_date:
                                        # 3月末が年度終了日の場合、その年度は前年
                                        if period_date.month == 3:
                                            fiscal_year = period_date.year - 1
                                        else:
                                            fiscal_year = period_date.year
                                        
                                        # 2Qの場合は期間終了日を計算
                                        if period_type == "2Q":
                                            period_end_str = _calculate_quarter_end_date(fy_end, "2Q")
                                            if not period_end_str:
                                                period_end_str = fy_end  # 計算失敗時は年度終了日を使用
                                except (ValueError, TypeError):
                                    pass
                            
                            # EDINET検索用データとして保存
                            if fy_end and disc_date:
                                annual_data_for_edinet.append({
                                    "CurFYEn": period_end_str,  # 2Qの場合は期間終了日、FYの場合は年度終了日
                                    "DiscDate": disc_date,
                                    "CurPerType": period_type,
                                    "fiscal_year": fiscal_year,
                                    "period_type": period_type
                                })
                        
                        logger.info(f"EDINET検索用データ準備完了: {len(annual_data_for_edinet)}件（最新4データ、開示日基準）")
                        logger.info(f"  - FYデータ: {len([d for d in annual_data_for_edinet if d.get('CurPerType') == 'FY'])}件")
                        logger.info(f"  - 2Qデータ: {len([d for d in annual_data_for_edinet if d.get('CurPerType') == '2Q'])}件")
                        
                        # 年度リストを作成（J-QUANTSデータから直接取得）
                        years_list = []
                        seen_years = set()
                        for data in annual_data_for_edinet:
                            fiscal_year = data.get("fiscal_year")
                            if fiscal_year and fiscal_year not in seen_years:
                                years_list.append(fiscal_year)
                                seen_years.add(fiscal_year)
                        
                        if not years_list:
                            # 年度が取得できない場合は、直近3年を試す
                            current_year = datetime.now().year
                            years_list = [current_year, current_year - 1, current_year - 2]
                            logger.warning(f"J-QUANTSデータから年度が取得できなかったため、直近3年を使用: {years_list}")
                        else:
                            # 降順にソート（最新年度を優先）
                            years_list = sorted(years_list, reverse=True)
                            logger.info(f"EDINET検索対象年度（最新優先）: {years_list}（最新年度: {years_list[0]}年度）")
                        
                        if financial_data:
                            # キャッシュから取得した場合も、新規分析時と同じロジックを使用
                            # FYと2Qを区別せず、開示日基準で最新4データを取得
                            from ..utils.financial_data import _calculate_quarter_end_date
                            
                        edinet_data = self.fetch_edinet_reports(code, years_list, jquants_annual_data=annual_data_for_edinet, progress_callback=progress_callback)
                        if edinet_data:
                            cached_result["edinet_data"] = edinet_data
                            logger.info(f"EDINETデータ取得成功: code={code}, years={list(edinet_data.keys())}")
                        else:
                            logger.warning(f"EDINETデータが見つかりませんでした: code={code}, years={years_list}")
                    except Exception as e:
                        logger.error(f"EDINETデータ取得エラー: {code} - {e}", exc_info=True)
                elif cached_edinet_data:
                    logger.info(f"EDINETデータはキャッシュから取得済み: code={code}, years={list(cached_edinet_data.keys())}")
                    
                    # 要約が含まれているか確認（修正前のキャッシュには要約が含まれていない可能性がある）
                    needs_regeneration = False
                    for year, year_data in cached_edinet_data.items():
                        if not year_data.get("management_policy"):
                            logger.info(f"要約が含まれていない年度を検出: code={code}, year={year}, 再生成を実行します")
                            needs_regeneration = True
                            break
                    
                    # 要約が含まれていない場合は再生成
                    if needs_regeneration and self.edinet_client and self.xbrl_parser and self.llm_summarizer:
                        logger.info(f"要約再生成開始: code={code}")
                        try:
                            # 年度リストを取得
                            years_list = list(cached_edinet_data.keys())
                            
                            # J-QUANTSデータを取得（EDINET検索用）
                            try:
                                financial_data = self.api_client.get_financial_summary(code=code)
                            except Exception as e:
                                logger.warning(f"J-QUANTSデータ取得エラー: {e}")
                                financial_data = None
                            
                            annual_data_for_edinet = []
                            if financial_data:
                                from ..utils.financial_data import _calculate_quarter_end_date
                                
                                # FYと2Qのデータのみを抽出
                                fy_and_q2_records = [
                                    r for r in financial_data 
                                    if r.get("CurPerType") in ["FY", "2Q"]
                                ]
                                
                                # DiscDateでソート（降順、最新が最初）
                                all_records_sorted = sorted(
                                    fy_and_q2_records,
                                    key=lambda x: x.get("DiscDate", ""),
                                    reverse=True
                                )
                                
                                # 最新4データを取得
                                latest_4_records = all_records_sorted[:4]
                                
                                for record in latest_4_records:
                                    fy_end = record.get("CurFYEn", "")
                                    disc_date = record.get("DiscDate", "")
                                    period_type = record.get("CurPerType", "FY")
                                    
                                    # 年度を計算
                                    fiscal_year = None
                                    period_date = None
                                    period_end_str = fy_end
                                    
                                    if fy_end:
                                        try:
                                            if len(fy_end) >= 10:
                                                period_date = datetime.strptime(fy_end[:10], "%Y-%m-%d")
                                            elif len(fy_end) >= 8:
                                                period_date = datetime.strptime(fy_end[:8], "%Y%m%d")
                                            
                                            if period_date:
                                                if period_date.month == 3:
                                                    fiscal_year = period_date.year - 1
                                                else:
                                                    fiscal_year = period_date.year
                                                
                                                if period_type == "2Q":
                                                    period_end_str = _calculate_quarter_end_date(fy_end, "2Q")
                                                    if not period_end_str:
                                                        period_end_str = fy_end
                                        except (ValueError, TypeError):
                                            pass
                                    
                                    if fy_end and disc_date:
                                        annual_data_for_edinet.append({
                                            "CurFYEn": period_end_str,
                                            "DiscDate": disc_date,
                                            "CurPerType": period_type,
                                            "fiscal_year": fiscal_year,
                                            "period_type": period_type
                                        })
                            
                            # 要約が含まれていない年度のみ再生成
                            for year in years_list:
                                year_data = cached_edinet_data.get(year, {})
                                if not year_data.get("management_policy"):
                                    # 該当年度の要約を再生成
                                    xbrl_path = year_data.get("xbrl_path")
                                    doc_id = year_data.get("docID")
                                    
                                    logger.info(f"要約再生成チェック: code={code}, year={year}, xbrl_path={xbrl_path}, docID={doc_id}")
                                    
                                    if not xbrl_path:
                                        logger.warning(f"要約再生成スキップ: xbrl_pathが存在しません: code={code}, year={year}")
                                        continue
                                    
                                    if not doc_id:
                                        logger.warning(f"要約再生成スキップ: docIDが存在しません: code={code}, year={year}")
                                        continue
                                    
                                    xbrl_dir = Path(xbrl_path)
                                    if not xbrl_dir.exists():
                                        logger.warning(f"要約再生成スキップ: XBRLディレクトリが存在しません: code={code}, year={year}, path={xbrl_path}")
                                        continue
                                    
                                    logger.info(f"要約再生成開始: code={code}, year={year}, docID={doc_id}, xbrl_path={xbrl_path}")
                                    try:
                                        logger.info(f"XBRLセクション抽出開始: code={code}, year={year}, docID={doc_id}")
                                        sections = self.xbrl_parser.extract_sections_by_type(xbrl_dir)
                                        logger.info(f"XBRLセクション抽出結果: code={code}, year={year}, docID={doc_id}, セクション数={len(sections)}")
                                        
                                        # セクションを順序付きで結合（A→B→C...の順）
                                        section_order = sorted(sections.keys())
                                        xbrl_text_parts = []
                                        for section_id in section_order:
                                            text = sections[section_id]
                                            if text:
                                                xbrl_text_parts.append(text)
                                        
                                        xbrl_text = '\n\n'.join(xbrl_text_parts)
                                        logger.info(f"XBRLテキスト結合結果: code={code}, year={year}, docID={doc_id}, 文字数={len(xbrl_text) if xbrl_text else 0}")
                                        
                                        if xbrl_text:
                                            # 圧縮前のテキストを直接LLMに渡す（圧縮処理をスキップ）
                                            logger.info(f"XBRLテキストをLLMに直接渡します（圧縮処理をスキップ）: code={code}, year={year}, docID={doc_id}, 文字数={len(xbrl_text)}")
                                            
                                            llm_model = self.llm_summarizer.model if self.llm_summarizer else "不明"
                                            logger.info(f"LLM要約開始: code={code}, year={year}, docID={doc_id}, モデル={llm_model}, 入力文字数={len(xbrl_text)}")
                                            summary = self.llm_summarizer.summarize_text(
                                                xbrl_text,
                                                "経営方針・課題",
                                                doc_id=doc_id,
                                                use_cache=False  # 再生成時はキャッシュを使わない
                                            )
                                            logger.info(f"LLM要約完了: code={code}, year={year}, docID={doc_id}, 文字数={len(summary) if summary else 0}")
                                            
                                            if summary:
                                                year_data["management_policy"] = summary
                                                logger.info(f"要約再生成成功: code={code}, year={year}")
                                            else:
                                                logger.warning(f"要約再生成失敗: 要約が空です: code={code}, year={year}")
                                        else:
                                            logger.warning(f"要約再生成失敗: XBRLテキストが空です: code={code}, year={year}")
                                    except Exception as e:
                                        logger.error(f"要約再生成エラー: code={code}, year={year}, error={e}", exc_info=True)
                            
                            # 更新されたedinet_dataをキャッシュに保存
                            cached_result["edinet_data"] = cached_edinet_data
                            if self.cache:
                                self.cache.set(cache_key, cached_result)
                                logger.info(f"要約再生成後のデータをキャッシュに保存: code={code}")
                        except Exception as e:
                            logger.error(f"要約再生成処理エラー: code={code}, error={e}", exc_info=True)
                
                return cached_result
        
        try:
            # 銘柄マスタから基本情報取得
            master_data = self.api_client.get_equity_master(code=code)
            stock_info = master_data[0] if master_data else {}
            stock_name = stock_info.get("CoName", "")
            
            if not stock_info:
                logger.warning(f"銘柄コード {code}: 銘柄マスタにデータが見つかりませんでした。")
                print(f"⚠️ 銘柄コード {code}: 銘柄マスタにデータが見つかりませんでした。")
            
            # 財務データ取得
            financial_data = self.api_client.get_financial_summary(code=code)
            
            if not financial_data:
                logger.warning(f"銘柄コード {code}: 財務データが取得できませんでした。")
                print(f"⚠️ 銘柄コード {code}: 財務データが取得できませんでした。")
                if stock_name:
                    print(f"   銘柄名: {stock_name}")
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
            try:
                annual_data = extract_annual_data(financial_data)
            except Exception as e:
                logger.error(f"銘柄コード {code}: 年度データ抽出中にエラーが発生しました - {e}", exc_info=True)
                print(f"❌ 銘柄コード {code}: 年度データ抽出中にエラーが発生しました - {e}")
                return None
            
            if not annual_data:
                # より詳細な情報を出力
                fy_records = [r for r in financial_data if r.get("CurPerType") == "FY"]
                print(f"⚠️ 銘柄コード {code}: 年度データが抽出できませんでした。")
                print(f"   財務データ総数: {len(financial_data)}件")
                print(f"   年度データ（CurPerType='FY'）: {len(fy_records)}件")
                if fy_records:
                    print(f"   年度データのサンプル（最初の3件）:")
                    for i, record in enumerate(fy_records[:3]):
                        fy_end = record.get("CurFYEn", "")
                        disc_date = record.get("DiscDate", "")
                        sales = record.get("Sales")
                        op = record.get("OP")
                        np = record.get("NP")
                        eq = record.get("Eq")
                        print(f"     {i+1}. 年度終了日: {fy_end}, 開示日: {disc_date}")
                        print(f"        売上高: {sales}, 営業利益: {op}, 当期純利益: {np}, 純資産: {eq}")
                logger.warning(f"銘柄コード {code}: 年度データが抽出できませんでした。財務データは {len(financial_data)}件取得できました。")
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
            # J-QUANTS APIのサブスクリプション開始日（2021-01-09）より前のデータは取得できない
            subscription_start_date = datetime(2021, 1, 9)
            price_errors = []
            for year_data in annual_data[:analysis_years]:
                fy_end = year_data.get("CurFYEn")
                if fy_end:
                    # 年度終了日の形式を統一（YYYY-MM-DD）
                    if len(fy_end) == 8:  # YYYYMMDD形式
                        fy_end_formatted = f"{fy_end[:4]}-{fy_end[4:6]}-{fy_end[6:8]}"
                    else:
                        fy_end_formatted = fy_end
                    
                    # 年度終了日がサブスクリプション開始日より前の場合はスキップ
                    try:
                        if len(fy_end) == 8:  # YYYYMMDD形式
                            fy_end_date = datetime.strptime(fy_end, "%Y%m%d")
                        elif len(fy_end) >= 10:  # YYYY-MM-DD形式
                            fy_end_date = datetime.strptime(fy_end[:10], "%Y-%m-%d")
                        else:
                            fy_end_date = None
                        
                        if fy_end_date and fy_end_date < subscription_start_date:
                            # サブスクリプション開始日より前のデータはスキップ
                            price_errors.append(f"{fy_end_formatted} (サブスクリプション範囲外)")
                            continue
                    except (ValueError, TypeError):
                        # 日付パースに失敗した場合は続行
                        pass
                    
                    # 休日の場合は直前の営業日を使用
                    try:
                        price = self.api_client.get_price_at_date(
                            code, 
                            fy_end_formatted,
                            use_nearest_trading_day=True
                        )
                        if price:
                            prices[fy_end_formatted] = price
                            prices[fy_end.replace("-", "")] = price  # YYYYMMDD形式も保存
                    except Exception as e:
                        # 株価取得エラーを記録（サブスクリプション範囲外など）
                        error_msg = str(e)
                        if "subscription" in error_msg.lower() or "400" in error_msg:
                            price_errors.append(f"{fy_end_formatted} (サブスクリプション範囲外)")
                        else:
                            price_errors.append(f"{fy_end_formatted} ({error_msg[:50]})")
            
            if price_errors:
                print(f"⚠️ 株価取得エラー: {len(price_errors)}件（サブスクリプション範囲外の可能性）{name_display}")
                print(f"   エラー詳細: {', '.join(price_errors[:5])}")
            
            # 指標計算（柔軟な年数対応）
            try:
                print(f"🔧 指標計算開始: 年度データ {len(annual_data)}件, 分析年数 {analysis_years}年, 株価データ {len(prices)}件{name_display}")
                metrics = calculate_metrics_flexible(annual_data, prices, analysis_years)
                print(f"✅ 指標計算完了: metrics={'あり' if metrics else 'なし'}, years={'あり' if metrics and metrics.get('years') else 'なし'}{name_display}")
            except Exception as e:
                logger.error(f"銘柄コード {code}: 指標計算中にエラーが発生しました - {e}", exc_info=True)
                print(f"❌ 銘柄コード {code}: 指標計算中にエラーが発生しました - {e}")
                import traceback
                error_traceback = traceback.format_exc()
                print(error_traceback)
                # エラーの詳細をログに出力
                logger.error(f"銘柄コード {code} の指標計算エラー詳細:\n{error_traceback}")
                return None
            
            if not metrics or not metrics.get("years"):
                logger.warning(f"銘柄コード {code}: 指標が計算できませんでした。年度データは {len(annual_data)}件ありました。")
                print(f"⚠️ 銘柄コード {code}: 指標が計算できませんでした。")
                print(f"   metrics: {metrics}")
                print(f"   年度データ数: {len(annual_data)}件")
                print(f"   分析年数: {analysis_years}年")
                print(f"   株価データ数: {len(prices)}件")
                if annual_data:
                    print(f"   年度データのサンプル（最初の3件）:")
                    for i, year_data in enumerate(annual_data[:3]):
                        fy_end = year_data.get("CurFYEn", "")
                        disc_date = year_data.get("DiscDate", "")
                        sales = year_data.get("Sales")
                        op = year_data.get("OP")
                        np = year_data.get("NP")
                        eq = year_data.get("Eq")
                        print(f"     {i+1}. 年度終了日: {fy_end}, 開示日: {disc_date}")
                        print(f"        売上高: {sales}, 営業利益: {op}, 当期純利益: {np}, 純資産: {eq}")
                return None
            
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
            
            # EDINET統合: 有価証券報告書を取得
            if self.edinet_client:
                try:
                    logger.info(f"EDINET検索開始: code={code}")
                    # J-QUANTSの年度データを渡して検索を効率化
                    # FYと2Qを区別せず、開示日基準で最新4データを取得
                    from ..utils.financial_data import _calculate_quarter_end_date
                    
                    # FYと2Qのデータのみを抽出
                    fy_and_q2_records = [
                        r for r in financial_data 
                        if r.get("CurPerType") in ["FY", "2Q"]
                    ]
                    
                    # DiscDateでソート（降順、最新が最初）
                    all_records_sorted = sorted(
                        fy_and_q2_records,
                        key=lambda x: x.get("DiscDate", ""),
                        reverse=True
                    )
                    
                    # 最新4データを取得
                    latest_4_records = all_records_sorted[:4]
                    
                    annual_data_for_edinet = []
                    for record in latest_4_records:
                        fy_end = record.get("CurFYEn", "")
                        disc_date = record.get("DiscDate", "")
                        period_type = record.get("CurPerType", "FY")
                        
                        # 年度を計算
                        fiscal_year = None
                        period_date = None
                        period_end_str = fy_end  # デフォルトは年度終了日
                        
                        if fy_end:
                            try:
                                if len(fy_end) >= 10:
                                    period_date = datetime.strptime(fy_end[:10], "%Y-%m-%d")
                                elif len(fy_end) >= 8:
                                    period_date = datetime.strptime(fy_end[:8], "%Y%m%d")
                                
                                if period_date:
                                    # 3月末が年度終了日の場合、その年度は前年
                                    if period_date.month == 3:
                                        fiscal_year = period_date.year - 1
                                    else:
                                        fiscal_year = period_date.year
                                    
                                    # 2Qの場合は期間終了日を計算
                                    if period_type == "2Q":
                                        period_end_str = _calculate_quarter_end_date(fy_end, "2Q")
                                        if not period_end_str:
                                            period_end_str = fy_end  # 計算失敗時は年度終了日を使用
                            except (ValueError, TypeError):
                                pass
                        
                        # EDINET検索用データとして保存
                        if fy_end and disc_date:
                            annual_data_for_edinet.append({
                                "CurFYEn": period_end_str,  # 2Qの場合は期間終了日、FYの場合は年度終了日
                                "DiscDate": disc_date,
                                "CurPerType": period_type,
                                "fiscal_year": fiscal_year,
                                "period_type": period_type
                            })
                    
                    logger.info(f"EDINET検索用データ準備完了: {len(annual_data_for_edinet)}件（最新4データ、開示日基準）")
                    logger.info(f"  - FYデータ: {len([d for d in annual_data_for_edinet if d.get('CurPerType') == 'FY'])}件")
                    logger.info(f"  - 2Qデータ: {len([d for d in annual_data_for_edinet if d.get('CurPerType') == '2Q'])}件")
                    
                    # 年度リストを作成（J-QUANTSデータから直接取得）
                    years_list = []
                    seen_years = set()
                    for data in annual_data_for_edinet:
                        fiscal_year = data.get("fiscal_year")
                        if fiscal_year and fiscal_year not in seen_years:
                            years_list.append(fiscal_year)
                            seen_years.add(fiscal_year)
                    
                    if not years_list:
                        # 年度が取得できない場合は、直近3年を試す
                        current_year = datetime.now().year
                        years_list = [current_year, current_year - 1, current_year - 2]
                        logger.warning(f"J-QUANTSデータから年度が取得できなかったため、直近3年を使用: {years_list}")
                    else:
                        # 降順にソート（最新年度を優先）
                        years_list = sorted(years_list, reverse=True)
                        logger.info(f"EDINET検索対象年度（最新優先）: {years_list}（最新年度: {years_list[0]}年度）")
                    
                    edinet_data = self.fetch_edinet_reports(code, years_list, jquants_annual_data=annual_data_for_edinet, progress_callback=progress_callback)
                    if edinet_data:
                        result["edinet_data"] = edinet_data
                        logger.info(f"EDINETデータ取得成功: code={code}, years={list(edinet_data.keys())}")
                    else:
                        logger.warning(f"EDINETデータが見つかりませんでした: code={code}, years={years_list}")
                except Exception as e:
                    logger.error(f"EDINETデータ取得エラー: {code} - {e}", exc_info=True)
            
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
    
    def fetch_edinet_reports(
        self,
        code: str,
        years: List[int],
        jquants_annual_data: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[int, Dict[str, Any]]:
        """
        指定年度の有価証券報告書を取得し、要約を生成
        最新年度から順に検索し、見つかったら次の年度は検索しない

        Args:
            code: 銘柄コード
            years: 年度のリスト（降順、最新年度が最初）
            jquants_annual_data: J-QUANTSの年度データ（検索効率化のため）
            progress_callback: 進捗を更新するコールバック関数

        Returns:
            {year: {docID, submitDate, pdf_path, management_policy}} の辞書
        """
        if not self.edinet_client:
            error_msg = f"EDINETクライアントが初期化されていません: code={code}"
            logger.warning(error_msg)
            if progress_callback:
                progress_callback(f"⚠️ **EDINET APIエラー**\n- EDINETクライアントが初期化されていません\n- EDINET_API_KEYが設定されているか確認してください")
            return {}
        
        # APIキーの確認
        if not self.edinet_client.api_key:
            error_msg = f"EDINET_API_KEYが設定されていません: code={code}"
            logger.warning(error_msg)
            if progress_callback:
                progress_callback(f"⚠️ **EDINET APIエラー**\n- EDINET_API_KEYが設定されていません\n- 環境変数EDINET_API_KEYを設定してください")
            return {}
        
        try:
            # 最新年度から順に検索（1年度ずつ）
            all_reports = {}
            # 年度リストが降順でソートされていることを確認
            sorted_years = sorted(years, reverse=True) if years else []
            latest_year = sorted_years[0] if sorted_years else None
            
            for year in sorted_years:
                # 最新年度の場合は明示的に表示
                year_label = f"{year}年度" + ("（最新年度）" if year == latest_year else "")
                if progress_callback:
                    progress_callback(f"📄 **EDINET APIで有価証券報告書／半期報告書を取得中...**\n- {year_label}の有価証券報告書・半期報告書を検索中")
                logger.info(f"EDINET有価証券報告書・半期報告書取得開始: code={code}, year={year}（最新年度から順に検索）")
                # 1年度ずつ検索
                reports = self.edinet_client.fetch_reports(code, [year], jquants_annual_data=jquants_annual_data)
                
                if reports:
                    all_reports.update(reports)
                    report_types = [r.get('docType', '不明') for r in reports.values()]
                    logger.info(f"EDINET有価証券報告書・半期報告書が見つかりました: code={code}, year={year}, docIDs={[r.get('docID') for r in reports.values()]}, 書類種別={report_types}")
                    # 最新年度の有価証券報告書・半期報告書が見つかったら、次の年度は検索しない
                    # 最初は最新年度だけを探す（ユーザー要求）
                    if progress_callback and year == latest_year:
                        progress_callback(f"✅ **{year_label}の有価証券報告書・半期報告書が見つかりました**\n- 書類種別: {', '.join(report_types) if report_types else '不明'}")
                    break
                else:
                    logger.info(f"EDINET有価証券報告書・半期報告書が見つかりませんでした: code={code}, year={year}（次の年度を検索します）")
            
            if not all_reports:
                error_msg = f"EDINET有価証券報告書・半期報告書が見つかりませんでした: code={code}, years={years}"
                logger.warning(error_msg)
                logger.warning(f"検索条件の詳細:")
                logger.warning(f"  - 銘柄コード: {code}")
                logger.warning(f"  - 検索対象年度: {years}")
                logger.warning(f"  - J-QUANTSデータ: {'あり' if jquants_annual_data else 'なし'}")
                if jquants_annual_data:
                    for record in jquants_annual_data[:3]:  # 最初の3件を表示
                        logger.warning(f"    - CurFYEn={record.get('CurFYEn')}, DiscDate={record.get('DiscDate')}, CurPerType={record.get('CurPerType')}, fiscal_year={record.get('fiscal_year')}")
                if progress_callback:
                    progress_callback(f"⚠️ **EDINET API検索結果**\n- {years}年度の有価証券報告書・半期報告書が見つかりませんでした\n- 検索条件を確認してください\n- ターミナルのログを確認してください")
                return {}
            
            logger.info(f"EDINET有価証券報告書・半期報告書取得成功: code={code}, years={list(all_reports.keys())}")
            
            # 各年度の有価証券報告書・半期報告書を解析・要約
            results = {}
            
            for year, report_info in tqdm(all_reports.items(), desc="有価証券報告書・半期報告書解析中", leave=False):
                doc_id = report_info.get("docID")
                
                if not doc_id:
                    logger.warning(f"docIDが存在しません: year={year}, report_info={report_info}")
                    continue
                
                result = {
                    "docID": doc_id,
                    "submitDate": report_info.get("submitDate", ""),
                    "pdf_path": report_info.get("pdf_path"),
                    "management_policy": "",
                    "docType": report_info.get("docType", "不明"),
                    "docTypeCode": report_info.get("docTypeCode", ""),
                    "docDescription": report_info.get("docDescription", ""),
                    "filerName": report_info.get("filerName", ""),  # 提出者名を追加
                }
                
                # XBRL解析と要約（PDFはダウンロード用のみ、要約にはXBRLを使用）
                xbrl_path = report_info.get("xbrl_path")
                pdf_path = report_info.get("pdf_path")  # PDFはダウンロード用のみ
                
                # 書類種別を取得
                doc_type = result.get("docType", "不明")
                doc_description = result.get("docDescription", "")
                if doc_type == "不明" and doc_description:
                    if "有価証券報告書" in doc_description:
                        doc_type = "有価証券報告書"
                    elif "半期報告書" in doc_description:
                        doc_type = "半期報告書"
                
                # 年度を取得（年度ラベル用）
                year_label = f"{year}年度"
                
                # XBRLからテキストを抽出
                if xbrl_path and self.xbrl_parser:
                    xbrl_dir = Path(xbrl_path)
                    
                    if not xbrl_dir.exists():
                        logger.warning(f"XBRLディレクトリが存在しません: {xbrl_path}")
                        results[year] = result
                        continue
                    
                    logger.info(f"XBRL解析開始: code={code}, docID={doc_id}, xbrl_path={xbrl_path}, filerName={report_info.get('filerName', '不明')}")
                    
                    if progress_callback:
                        progress_callback(f"📄 **{year_label}{doc_type}を読み込み中...**\n- XBRLを解析中")
                    
                    # XBRLから指定セクションを抽出
                    try:
                        logger.info(f"XBRLセクション抽出開始: docID={doc_id}")
                        sections = self.xbrl_parser.extract_sections_by_type(xbrl_dir)
                        logger.info(f"XBRLセクション抽出結果: docID={doc_id}, セクション数={len(sections)}")
                        
                        # セクションを順序付きで結合（A→B→C...の順）
                        section_order = sorted(sections.keys())
                        xbrl_text_parts = []
                        for section_id in section_order:
                            text = sections[section_id]
                            if text:
                                xbrl_text_parts.append(text)
                        
                        xbrl_text = '\n\n'.join(xbrl_text_parts)
                        logger.info(f"XBRLテキスト結合結果: docID={doc_id}, 文字数={len(xbrl_text) if xbrl_text else 0}")
                        
                        if xbrl_text:
                            # 圧縮前のテキストを直接LLMに渡す（圧縮処理をスキップ）
                            logger.info(f"XBRLテキストをLLMに直接渡します（圧縮処理をスキップ）: docID={doc_id}, 文字数={len(xbrl_text)}")
                            
                            if self.llm_summarizer:
                                # LLMモデル名を取得
                                llm_model = self.llm_summarizer.model if self.llm_summarizer else "不明"
                                if progress_callback:
                                    progress_callback(f"📄 **{year_label}{doc_type}を{llm_model}で分析中...**")
                                logger.info(f"LLM要約開始: docID={doc_id}, モデル={llm_model}, 入力文字数={len(xbrl_text)}")
                                summary = self.llm_summarizer.summarize_text(
                                    xbrl_text,
                                    "経営方針・課題",
                                    doc_id=doc_id
                                )
                                logger.info(f"LLM要約完了: docID={doc_id}, 文字数={len(summary) if summary else 0}")
                                result["management_policy"] = summary
                            else:
                                logger.warning(f"LLM要約クラスが初期化されていません: docID={doc_id}")
                                result["management_policy"] = xbrl_text[:500] + "..." if len(xbrl_text) > 500 else xbrl_text
                        else:
                            logger.warning(f"XBRLテキストが抽出できませんでした: docID={doc_id}")
                    except Exception as e:
                        logger.error(f"XBRL解析エラー: docID={doc_id}, error={e}", exc_info=True)
                else:
                    logger.warning(f"XBRLディレクトリが見つかりません: docID={doc_id}, xbrl_path={xbrl_path}, xbrl_parser={self.xbrl_parser is not None}")
                
                results[year] = result
            
            logger.info(f"EDINET要約完了: code={code}, years={list(results.keys())}")
            return results
        
        except Exception as e:
            logger.error(f"EDINETレポート取得エラー: {code} - {e}", exc_info=True)
            return {}
    
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
        
        # 四半期データ取得・分析（機能削除済み）
        quarterly_metrics = None
        
        report_data = {
            **result,
            "comparison": comparison,
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

