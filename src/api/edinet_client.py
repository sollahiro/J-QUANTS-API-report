"""
EDINET API クライアント

有価証券報告書の取得機能を提供します。
"""

import time
import zipfile
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from pathlib import Path

import requests
from ..config import config

logger = logging.getLogger(__name__)


class EdinetAPIClient:
    """EDINET API クライアントクラス"""

    BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    RATE_LIMIT_WAIT = 60  # レート制限時の待機時間（秒）

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        初期化

        Args:
            api_key: APIキー。Noneの場合はconfigから取得
            base_url: APIベースURL。Noneの場合はデフォルト値を使用
        """
        self.api_key = api_key or config.edinet_api_key
        
        if not self.api_key:
            logger.warning(
                "EDINET_API_KEYが設定されていません。"
                "有価証券報告書の取得機能は使用できません。"
            )
        
        self.base_url = base_url or self.BASE_URL
        
        if self.api_key:
            self.api_key = self.api_key.strip()
        
        self.session = requests.Session()
        if self.api_key:
            # EDINET APIの認証ヘッダー名を試行
            # Azure API Managementを使用している場合、Ocp-Apim-Subscription-Keyを使用
            # その他の場合、X-API-KEYを使用
            self.session.headers.update({
                "Ocp-Apim-Subscription-Key": self.api_key,  # Azure API Management形式
                # "X-API-KEY": self.api_key,  # 一般的な形式（必要に応じてコメントアウト解除）
            })
        
        # キャッシュディレクトリ
        cache_dir = Path(config.cache_dir)
        self.cache_dir = cache_dir / "edinet"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> requests.Response:
        """
        APIリクエストを実行（リトライ機能付き）

        Args:
            endpoint: エンドポイントパス
            params: クエリパラメータ
            retry_count: 現在のリトライ回数

        Returns:
            APIレスポンス

        Raises:
            requests.RequestException: リクエストエラー
        """
        if not self.api_key:
            raise ValueError("EDINET_API_KEYが設定されていません。")
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=60)
            
            # 404は有報が存在しない場合なので、エラーにしない
            if response.status_code == 404:
                return response
            
            response.raise_for_status()
            return response
        
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                # レート制限エラー
                if retry_count < self.MAX_RETRIES:
                    wait_time = self.RETRY_DELAY * (2 ** retry_count) + self.RATE_LIMIT_WAIT
                    logger.warning(f"レート制限に達しました。{wait_time:.0f}秒待機してからリトライします...")
                    time.sleep(wait_time)
                    return self._request(endpoint, params, retry_count + 1)
                else:
                    raise requests.RequestException(
                        f"レート制限に達しました。リトライ回数上限に達しました。"
                    )
            else:
                raise requests.RequestException(
                    f"APIリクエストエラー: {response.status_code} - {response.text}"
                )
        
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            # 一時的なネットワークエラー
            if retry_count < self.MAX_RETRIES:
                wait_time = self.RETRY_DELAY * (2 ** retry_count)
                logger.warning(f"ネットワークエラー: {str(e)}。{wait_time:.0f}秒待機してからリトライします...")
                time.sleep(wait_time)
                return self._request(endpoint, params, retry_count + 1)
            else:
                raise requests.RequestException(
                    f"ネットワークエラー: {str(e)}"
                )

    def search_documents(
        self,
        code: str,
        years: List[int],
        doc_type_code: str = "030",
        form_code: Optional[str] = None,
        jquants_data: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        有価証券報告書を検索

        Args:
            code: 銘柄コード（4桁または5桁）
            years: 年度のリスト（例: [2023, 2024]）
            doc_type_code: 法令コード（デフォルト: "030"=有価証券報告書）
            form_code: 様式コード（オプション、指定しない場合は全様式）
            jquants_data: J-QUANTSの年度データ（CurFYEn, DiscDateを含む）。指定すると検索を効率化

        Returns:
            書類情報のリスト
        """
        if not self.api_key:
            logger.warning("EDINET_API_KEYが設定されていないため、有報検索をスキップします。")
            return []
        
        all_documents = []
        
        # J-QUANTSデータから年度終了日と開示日のマッピングを作成
        # 年度終了日から3ヶ月以内、かつ開示日以降の範囲で検索するために使用
        # 年度情報はJ-QUANTSデータに含まれている場合はそれを使用、なければ年度終了日から計算
        # 半期報告書（2Q）の検索のため、2Qデータも処理
        fy_end_to_disc_date = {}
        fy_end_to_period_end = {}  # 年度終了日も保存
        if jquants_data:
            now = datetime.now()
            for record in jquants_data:
                fy_end = record.get("CurFYEn", "")
                disc_date = record.get("DiscDate", "")
                period_type = record.get("CurPerType") or record.get("period_type", "FY")  # 期間種別（FYまたは2Q）
                
                # 年度情報が直接含まれている場合はそれを使用（J-QUANTSデータにfiscal_yearが含まれる場合）
                fiscal_year = record.get("fiscal_year")  # J-QUANTSデータに年度が含まれている場合
                
                if fy_end and disc_date:
                    # 年度情報がない場合は年度終了日から計算
                    if fiscal_year is None:
                        try:
                            if len(fy_end) >= 10:
                                period_date = datetime.strptime(fy_end[:10], "%Y-%m-%d")
                            elif len(fy_end) >= 8:
                                period_date = datetime.strptime(fy_end[:8], "%Y%m%d")
                            else:
                                continue
                            
                            # 3月末が年度終了日の場合、その年度は前年
                            if period_date.month == 3:
                                fiscal_year = period_date.year - 1
                            else:
                                fiscal_year = period_date.year
                        except (ValueError, TypeError):
                            continue
                    else:
                        # 年度情報がある場合でも、年度終了日をパースしてperiod_endを取得
                        try:
                            if len(fy_end) >= 10:
                                period_date = datetime.strptime(fy_end[:10], "%Y-%m-%d")
                            elif len(fy_end) >= 8:
                                period_date = datetime.strptime(fy_end[:8], "%Y%m%d")
                            else:
                                continue
                        except (ValueError, TypeError):
                            continue
                    
                    # 開示日を正規化（YYYY-MM-DD形式）
                    if len(disc_date) == 8:  # YYYYMMDD形式
                        disc_date_formatted = f"{disc_date[:4]}-{disc_date[4:6]}-{disc_date[6:8]}"
                    elif len(disc_date) >= 10:  # YYYY-MM-DD形式
                        disc_date_formatted = disc_date[:10]
                    else:
                        continue
                    
                    # 開示日が未来の場合は除外（未来の年度データは除外）
                    try:
                        disc_date_obj = datetime.strptime(disc_date_formatted, "%Y-%m-%d")
                        if disc_date_obj > now:
                            logger.debug(f"開示日が未来のため除外: fiscal_year={fiscal_year}, period_type={period_type}, disc_date={disc_date_formatted}")
                            continue
                    except (ValueError, TypeError):
                        pass
                    
                    # 半期報告書（2Q）の場合は、年度情報に"2Q"を付与して区別
                    # FYと2Qが同じ年度の場合、両方の検索期間を保持
                    # 2Qの場合は、期間終了日（period_end_str）をパースして使用
                    if period_type == "2Q":
                        # 2Qの場合は、CurFYEnが期間終了日（例: 2025-06-30）になっている
                        # これをperiod_endとして使用
                        try:
                            if len(fy_end) >= 10:
                                period_end_date = datetime.strptime(fy_end[:10], "%Y-%m-%d")
                            elif len(fy_end) >= 8:
                                period_end_date = datetime.strptime(fy_end[:8], "%Y%m%d")
                            else:
                                period_end_date = period_date  # フォールバック
                        except (ValueError, TypeError):
                            period_end_date = period_date  # フォールバック
                    else:
                        period_end_date = period_date
                    
                    key = f"{fiscal_year}_{period_type}" if period_type == "2Q" else fiscal_year
                    fy_end_to_disc_date[key] = disc_date_formatted
                    fy_end_to_period_end[key] = period_end_date  # 期間終了日を保存（2Qの場合は期間終了日、FYの場合は年度終了日）
                    
                    logger.debug(f"J-QUANTSデータをマッピング: fiscal_year={fiscal_year}, period_type={period_type}, period_end={period_date.strftime('%Y-%m-%d')}, disc_date={disc_date_formatted}")
        
        # 年度ごとに検索（提出日を基準に検索）
        for year in years:
            try:
                search_dates = []
                
                # J-QUANTSの開示日と年度終了日がある場合は、最適化された範囲で検索
                # FYと2Qの両方をチェックし、最新の開示日を持つデータを優先
                search_keys = [year, f"{year}_2Q"]  # FYと2Qの両方をチェック
                available_data = []
                
                for key in search_keys:
                    if key in fy_end_to_disc_date and key in fy_end_to_period_end:
                        disc_date_str = fy_end_to_disc_date[key]
                        period_end = fy_end_to_period_end[key]
                        try:
                            disc_date_obj = datetime.strptime(disc_date_str, "%Y-%m-%d")
                            
                            # period_endがdatetimeオブジェクトでない場合は変換
                            if isinstance(period_end, str):
                                if len(period_end) >= 10:
                                    period_end_obj = datetime.strptime(period_end[:10], "%Y-%m-%d")
                                elif len(period_end) >= 8:
                                    period_end_obj = datetime.strptime(period_end[:8], "%Y%m%d")
                                else:
                                    logger.debug(f"period_endの形式が不正: {period_end}")
                                    continue
                            elif isinstance(period_end, datetime):
                                period_end_obj = period_end
                            else:
                                logger.debug(f"period_endがdatetimeでもstrでもありません: {type(period_end)}")
                                continue
                            
                            available_data.append({
                                "key": key,
                                "disc_date_str": disc_date_str,
                                "disc_date_obj": disc_date_obj,
                                "period_end": period_end_obj
                            })
                            logger.debug(f"J-QUANTSデータを発見: year={year}, key={key}, period_end={period_end_obj.strftime('%Y-%m-%d')}, disc_date={disc_date_str}")
                        except (ValueError, TypeError) as e:
                            logger.debug(f"日付パースエラー: key={key}, disc_date={disc_date_str}, period_end={period_end}, error={e}")
                            continue
                
                # 最新の開示日を持つデータを優先（FY/2Q区別なし）
                disc_date_str = None
                period_end = None
                selected_key = None
                
                if available_data:
                    # 開示日でソート（新しい順）
                    available_data.sort(key=lambda x: x["disc_date_obj"], reverse=True)
                    # 最新のデータを使用
                    latest_data = available_data[0]
                    disc_date_str = latest_data["disc_date_str"]
                    period_end = latest_data["period_end"]
                    selected_key = latest_data["key"]
                    
                    # period_endの型を確認
                    if not isinstance(period_end, datetime):
                        logger.error(f"period_endがdatetimeオブジェクトではありません: type={type(period_end)}, value={period_end}")
                        # 変換を試みる
                        if isinstance(period_end, str):
                            try:
                                if len(period_end) >= 10:
                                    period_end = datetime.strptime(period_end[:10], "%Y-%m-%d")
                                elif len(period_end) >= 8:
                                    period_end = datetime.strptime(period_end[:8], "%Y%m%d")
                            except (ValueError, TypeError) as e:
                                logger.error(f"period_endの変換に失敗: {e}")
                                period_end = None
                        else:
                            period_end = None
                    
                    if period_end:
                        logger.debug(f"J-QUANTSデータを使用（最新優先）: year={year}, key={selected_key}, period_end={period_end.strftime('%Y-%m-%d')}, disc_date={disc_date_str}")
                    if len(available_data) > 1:
                        logger.debug(f"  他の候補: {[str(d['key']) + ' (' + d['disc_date_str'] + ')' for d in available_data[1:]]}")
                
                if disc_date_str and period_end:
                    try:
                        disc_date = datetime.strptime(disc_date_str, "%Y-%m-%d")
                        now = datetime.now()
                        
                        # period_endがdatetimeオブジェクトでない場合は変換
                        if isinstance(period_end, str):
                            if len(period_end) >= 10:
                                period_end = datetime.strptime(period_end[:10], "%Y-%m-%d")
                            elif len(period_end) >= 8:
                                period_end = datetime.strptime(period_end[:8], "%Y%m%d")
                            else:
                                raise ValueError(f"Invalid period_end format: {period_end}")
                        elif not isinstance(period_end, datetime):
                            raise ValueError(f"period_end must be datetime or str, got {type(period_end)}")
                        
                        # 検索範囲の開始日：開示日の7日前から開始（有報は開示日の前後で提出されることが多い）
                        # ただし、期間終了日より前の場合は期間終了日から開始
                        search_start = disc_date - timedelta(days=7)
                        if search_start < period_end:
                            search_start = period_end
                        
                        # 検索範囲の終了日：開示日の60日後、または期間終了日から90日後、または現在日時のいずれか早い方
                        # 最新の開示日を基準に検索（FY/2Q区別なし、11月提出の半期報告書にも対応）
                        search_end_from_disc_date = disc_date + timedelta(days=60)
                        search_end_from_period = period_end + timedelta(days=90)
                        search_end = min(search_end_from_disc_date, search_end_from_period, now)
                        
                        # 検索開始日が終了日を超える場合は調整
                        if search_start > search_end:
                            # 開示日を中心に検索範囲を設定
                            search_start = disc_date - timedelta(days=7)
                            search_end = min(disc_date + timedelta(days=30), now)
                        
                        # 検索範囲内の日付を生成（1日ごと）
                        current_date = search_start
                        while current_date <= search_end:
                            search_dates.append(current_date.strftime("%Y-%m-%d"))
                            current_date += timedelta(days=1)
                        
                        logger.info(f"J-QUANTSデータを活用（最適化検索）: code={code}, year={year}, disc_date={disc_date_str}, period_end={period_end.strftime('%Y-%m-%d')}, 検索範囲={search_start.strftime('%Y-%m-%d')}～{search_end.strftime('%Y-%m-%d')}, 検索日数={len(search_dates)}")
                    except (ValueError, TypeError) as e:
                        logger.debug(f"日付パースエラー: {e}")
                        pass
                
                # J-QUANTSデータがない場合、または検索結果が0件の場合はフォールバック
                if not search_dates:
                    # フォールバック: 年度終了後の提出期間を推定（4-6月の主要日のみ）
                    # 有価証券報告書は通常、年度終了後3ヶ月以内（5-6月）に提出される
                    for month in [4, 5, 6]:  # 4-6月のみ
                        # 月初、15日、月末を検索
                        search_dates.append(datetime(year+1, month, 1).strftime("%Y-%m-%d"))
                        search_dates.append(datetime(year+1, month, 15).strftime("%Y-%m-%d"))
                        # 月末日
                        try:
                            if month in [4, 6]:
                                last_day = 30
                            else:
                                last_day = 31
                            search_dates.append(datetime(year+1, month, last_day).strftime("%Y-%m-%d"))
                        except ValueError:
                            pass
                    logger.info(f"フォールバック検索: code={code}, year={year}, 検索日数={len(search_dates)}")
                
                logger.info(f"有報検索開始: code={code}, year={year}, dates={len(search_dates)}件, type={doc_type_code}")
                
                year_documents = []
                # 2024年6月25日の検索結果を特別に記録
                june_25_docs = []
                for search_date in search_dates:
                    # EDINET API v2のパラメータ形式
                    # type: 取得情報の種類（1=メタデータのみ、2=提出書類一覧+メタデータ）
                    # 書類種別コード（030=有価証券報告書）は別のパラメータで指定
                    # EDINET API v2のパラメータ形式（確定）
                    # type: 取得情報の種類（2=提出書類一覧+メタデータ）
                    # docTypeCode: 書類種別コード（030=有価証券報告書）
                    # 注意: docTypeCodeでフィルタリングすると、上場企業の有価証券報告書が
                    # 含まれない可能性があるため、一旦フィルタリングを外して全書類を取得
                    params = {
                        "date": search_date,
                        "type": "2",  # 書類一覧取得
                        # docTypeCodeはフィルタリングで後から適用
                        # "docTypeCode": doc_type_code,  # 有価証券報告書
                    }
                    
                    logger.debug(f"APIリクエスト: /documents.json, params={params}")
                    
                    try:
                        response = self._request("/documents.json", params)
                    except Exception as e:
                        logger.warning(f"検索エラー（日付={search_date}）: {e}")
                        continue
                    
                    if response.status_code == 404:
                        logger.debug(f"404エラー（日付={search_date}）")
                        continue
                    
                    if response.status_code != 200:
                        logger.warning(f"HTTPエラー（status={response.status_code}, 日付={search_date}）: {response.text[:200]}")
                        continue
                    
                    try:
                        data = response.json()
                    except Exception as e:
                        logger.warning(f"JSON解析エラー（日付={search_date}）: {e}, レスポンス: {response.text[:200]}")
                        continue
                    
                    # エラーレスポンスの確認
                    if "statusCode" in data:
                        error_message = data.get("message", "不明なエラー")
                        logger.warning(f"EDINET APIエラー（日付={search_date}）: statusCode={data.get('statusCode')}, message={error_message}")
                        continue
                    
                    # レスポンス構造の確認
                    # EDINET API v2のレスポンス構造: {"metadata": {...}, "results": [...]}
                    # または {"metadata": {...}} のみの場合もある
                    
                    if "results" in data:
                        documents = data["results"]
                        result_count = len(documents)
                        logger.info(f"APIレスポンス（日付={search_date}）: {result_count}件")
                        year_documents.extend(documents)
                        # 2024年6月25日の検索結果を特別に記録
                        if search_date == f"{year+1}-06-25":
                            june_25_docs = documents
                            logger.info(f"  2024-06-25の検索結果: {len(june_25_docs)}件")
                            # 7203を含む書類を検索
                            for doc in june_25_docs:
                                sec_code = doc.get("secCode")
                                filer_name = doc.get("filerName", "")
                                doc_type = doc.get("docTypeCode", "")
                                ordinance_code = doc.get("ordinanceCode", "")
                                if sec_code and (str(sec_code) == '7203' or '7203' in str(sec_code) or 'トヨタ自動車' in filer_name):
                                    logger.info(f"    7203関連: secCode={sec_code}, filerName={filer_name}, docTypeCode={doc_type}, ordinanceCode={ordinance_code}, docID={doc.get('docID')}")
                            # 有価証券報告書（docTypeCodeの先頭3桁が030）を検索
                            securities_reports = [doc for doc in june_25_docs 
                                                 if doc.get("ordinanceCode") in ["010", "020"] 
                                                 and doc.get("docTypeCode", "") and len(doc.get("docTypeCode", "")) >= 3 
                                                 and doc.get("docTypeCode", "")[:3] == "030"]
                            logger.info(f"  2024-06-25の有価証券報告書（docTypeCode先頭3桁=030）: {len(securities_reports)}件")
                            for doc in securities_reports[:5]:  # 最初の5件を表示
                                logger.info(f"    有報: secCode={doc.get('secCode')}, filerName={doc.get('filerName')}, docTypeCode={doc.get('docTypeCode')}, docID={doc.get('docID')}")
                        if documents:
                            logger.info(f"  取得件数: {len(documents)}件（日付={search_date}）")
                    elif "metadata" in data:
                        # メタデータのみの場合、結果が0件の可能性
                        metadata = data["metadata"]
                        logger.info(f"メタデータ（日付={search_date}）: {metadata}")
                        
                        # メタデータから結果数を取得
                        result_count = 0
                        if isinstance(metadata, dict):
                            result_count = metadata.get("resultset", {}).get("count", 0)
                            if result_count == 0:
                                # 別の形式を確認
                                result_count = metadata.get("count", 0)
                        
                        logger.info(f"APIレスポンス（日付={search_date}）: {result_count}件（メタデータから取得）")
                        
                        # メタデータに結果が含まれている場合
                        if result_count > 0:
                            # resultsキーが存在しない場合、別のキーを確認
                            for key in data.keys():
                                if key != "metadata" and isinstance(data[key], list):
                                    documents = data[key]
                                    logger.info(f"  結果を発見: key={key}, 件数={len(documents)}")
                                    year_documents.extend(documents)
                                    break
                        else:
                            logger.debug(f"  結果が0件です（メタデータ: {metadata}）")
                    else:
                        logger.warning(f"  レスポンス構造が異なります: keys={list(data.keys())}")
                        # エラーメッセージを表示
                        if "message" in data:
                            logger.warning(f"  エラーメッセージ: {data['message']}")
                
                # 重複を除去（docIDで）& 有価証券報告書のみをフィルタリング
                # EDINET APIの仕様:
                # - ordinanceCode: 法令コード（030=有価証券報告書）
                # - docTypeCode: 書類種別コード（有価証券報告書の場合は様々な値がある）
                # - secCode: 証券コード（上場企業の場合は銘柄コードが入る）
                seen_doc_ids = set()
                unique_documents = []
                sec_code_count = 0
                no_sec_code_count = 0
                
                # 全書類のsecCode分布を確認（ordinanceCodeに関係なく）
                all_sec_code_count = 0
                all_no_sec_code_count = 0
                sec_code_samples = []  # secCodeが存在する書類のサンプル
                doc_type_030_with_sec_code = []  # ordinanceCode=010かつdocTypeCode=030の書類
                toyota_in_all_docs = []  # 7203を含む全書類
                for doc in year_documents:
                    sec_code = doc.get("secCode")
                    doc_type = doc.get("docTypeCode", "")
                    ordinance_code = doc.get("ordinanceCode", "")
                    filer_name = doc.get("filerName", "")
                    
                    # 7203を含む書類を収集
                    if sec_code and (str(sec_code) == '7203' or '7203' in str(sec_code) or 'トヨタ自動車' in filer_name):
                        toyota_in_all_docs.append({
                            "filerName": filer_name,
                            "secCode": sec_code,
                            "docTypeCode": doc_type,
                            "ordinanceCode": ordinance_code,
                            "periodEnd": doc.get("periodEnd"),
                            "edinetCode": doc.get("edinetCode", ""),
                            "docID": doc.get("docID")
                        })
                    
                    if sec_code is not None:
                        all_sec_code_count += 1
                        # secCodeが存在する書類のサンプルを収集（最大10件）
                        if len(sec_code_samples) < 10:
                            sec_code_samples.append({
                                "filerName": doc.get("filerName", ""),
                                "secCode": sec_code,
                                "docTypeCode": doc_type,
                                "ordinanceCode": ordinance_code,
                                "periodEnd": doc.get("periodEnd"),
                                "edinetCode": doc.get("edinetCode", "")
                            })
                        # ordinanceCode=010または020かつdocTypeCodeの先頭3桁が030の書類を収集
                        if (ordinance_code in ["010", "020"] and 
                            doc_type and len(doc_type) >= 3 and doc_type[:3] == "030" and
                            len(doc_type_030_with_sec_code) < 10):
                            doc_type_030_with_sec_code.append({
                                "filerName": doc.get("filerName", ""),
                                "secCode": sec_code,
                                "periodEnd": doc.get("periodEnd"),
                                "edinetCode": doc.get("edinetCode", "")
                            })
                    else:
                        all_no_sec_code_count += 1
                
                logger.info(f"  全書類のsecCode分布: secCodeあり={all_sec_code_count}件, secCodeなし={all_no_sec_code_count}件")
                
                if toyota_in_all_docs:
                    logger.info(f"  全書類中の7203関連書類: {len(toyota_in_all_docs)}件")
                    for sample in toyota_in_all_docs:
                        logger.info(f"    filerName={sample['filerName']}, secCode={sample['secCode']}, docTypeCode={sample['docTypeCode']}, ordinanceCode={sample['ordinanceCode']}, periodEnd={sample['periodEnd']}, docID={sample['docID']}")
                else:
                    logger.warning(f"  全書類中に7203関連書類が見つかりませんでした（全{len(year_documents)}件中）")
                
                if doc_type_030_with_sec_code:
                    logger.info(f"  ordinanceCode=010かつdocTypeCode=030の書類（secCodeあり、最大10件）:")
                    for sample in doc_type_030_with_sec_code:
                        logger.info(f"    filerName={sample['filerName']}, secCode={sample['secCode']}, periodEnd={sample['periodEnd']}, edinetCode={sample['edinetCode']}")
                else:
                    logger.info(f"  ordinanceCode=010かつdocTypeCode=030の書類（secCodeあり）: 0件")
                
                if sec_code_samples:
                    logger.info(f"  secCodeが存在する書類のサンプル（最大10件）:")
                    for sample in sec_code_samples:
                        logger.info(f"    filerName={sample['filerName']}, secCode={sample['secCode']}, docTypeCode={sample['docTypeCode']}, ordinanceCode={sample['ordinanceCode']}, periodEnd={sample['periodEnd']}, edinetCode={sample['edinetCode']}")
                else:
                    logger.warning(f"  secCodeが存在する書類が見つかりませんでした（全{len(year_documents)}件中）")
                
                # ordinanceCode別のdocTypeCode分布を確認
                ordinance_distribution = {}
                for doc in year_documents:
                    doc_type = doc.get("docTypeCode", "")
                    ordinance_code = doc.get("ordinanceCode", "")
                    if ordinance_code not in ordinance_distribution:
                        ordinance_distribution[ordinance_code] = {}
                    ordinance_distribution[ordinance_code][doc_type] = ordinance_distribution[ordinance_code].get(doc_type, 0) + 1
                
                for ord_code, dist in ordinance_distribution.items():
                    logger.info(f"  ordinanceCode={ord_code}のdocTypeCode分布: {dist}")
                
                for doc in year_documents:
                    doc_id = doc.get("docID")
                    ordinance_code = doc.get("ordinanceCode", "")
                    doc_type = doc.get("docTypeCode", "")
                    sec_code = doc.get("secCode")
                    doc_description = doc.get("docDescription", "")
                    
                    # 有価証券報告書と半期報告書を対象
                    # EDINET APIの仕様:
                    # - ordinanceCode=010: 金融商品取引法（内国会社）
                    # - ordinanceCode=020: 金融商品取引法（外国会社等）
                    # - ordinanceCode=030: 金融商品取引法（特定有価証券）
                    # - docTypeCode: 6桁または3桁の文字列
                    #   先頭3桁が030のものが有価証券報告書
                    #   先頭3桁が050のものが半期報告書
                    #   ただし、実際のAPIレスポンスではdocTypeCodeが3桁の場合もある
                    #   書類名（docDescription）に「有価証券報告書」または「半期報告書」が含まれる場合も対象として扱う
                    # 上場企業の有価証券報告書・半期報告書はordinanceCode=010または020で、docTypeCodeの先頭3桁が030または050
                    is_target_report = False
                    if ordinance_code in ["010", "020"]:
                        # docTypeCodeの先頭3桁が030（有価証券報告書）または050（半期報告書）を判定
                        if doc_type and len(doc_type) >= 3:
                            if doc_type[:3] == "030":  # 有価証券報告書
                                is_target_report = True
                            elif doc_type[:3] == "050":  # 半期報告書
                                is_target_report = True
                        # docDescriptionに「有価証券報告書」または「半期報告書」が含まれる場合も対象として扱う
                        if doc_description:
                            if "有価証券報告書" in doc_description:
                                is_target_report = True
                            elif "半期報告書" in doc_description:
                                is_target_report = True
                    
                    if not is_target_report:
                        continue
                    
                    # 訂正報告書などの補足書類を除外
                    # docDescriptionに「訂正」が含まれる場合は除外
                    if doc_description and ("訂正" in doc_description or "補正" in doc_description):
                        logger.debug(f"訂正報告書のため除外: docID={doc_id}, docDescription={doc_description}")
                        continue
                    
                    # secCodeの有無をカウント
                    if sec_code is None:
                        no_sec_code_count += 1
                    else:
                        sec_code_count += 1
                    
                    # 上場企業の有価証券報告書のみを対象（secCodeが存在する）
                    # 投資信託などはsecCodeがNoneのため除外
                    if sec_code is None:
                        continue
                    
                    if doc_id and doc_id not in seen_doc_ids:
                        seen_doc_ids.add(doc_id)
                        unique_documents.append(doc)
                
                logger.info(f"有価証券報告書・半期報告書の内訳: secCodeあり={sec_code_count}件, secCodeなし={no_sec_code_count}件")
                
                # デバッグ: secCodeがNoneの書類のサンプルを表示（上場企業の有報が含まれている可能性）
                if no_sec_code_count > 0:
                    sample_no_sec = []
                    for doc in year_documents:
                        ordinance_code = doc.get("ordinanceCode", "")
                        doc_type = doc.get("docTypeCode", "")
                        sec_code = doc.get("secCode")
                        if (ordinance_code in ["010", "020"] and 
                            doc_type and len(doc_type) >= 3 and doc_type[:3] == "030" and
                            sec_code is None):
                            sample_no_sec.append(doc)
                            if len(sample_no_sec) >= 3:
                                break
                    for sample in sample_no_sec:
                        logger.info(f"  secCodeなしのサンプル: filerName={sample.get('filerName')}, docTypeCode={sample.get('docTypeCode')}, periodEnd={sample.get('periodEnd')}, edinetCode={sample.get('edinetCode')}")
                
                logger.info(f"EDINET API検索結果: {code} {year}年度 → 全{len(unique_documents)}件（重複除去後）")
                
                # デバッグ: 検索対象の書類の詳細を表示
                if unique_documents:
                    logger.info(f"検索対象書類の詳細（全{len(unique_documents)}件）:")
                    # 7203を含む書類を優先的に表示
                    toyota_docs = [doc for doc in unique_documents if doc.get('secCode') and (str(doc.get('secCode')) == '7203' or 'トヨタ' in doc.get('filerName', ''))]
                    if toyota_docs:
                        logger.info(f"  トヨタ自動車関連書類: {len(toyota_docs)}件")
                        for i, doc in enumerate(toyota_docs):
                            logger.info(f"  [トヨタ{i+1}] secCode={doc.get('secCode')}, filerName={doc.get('filerName')}, periodEnd={doc.get('periodEnd')}, docTypeCode={doc.get('docTypeCode')}, ordinanceCode={doc.get('ordinanceCode')}")
                    # 最初の10件を表示
                    for i, doc in enumerate(unique_documents[:10]):
                        logger.info(f"  [{i+1}] secCode={doc.get('secCode')}, filerName={doc.get('filerName')}, periodEnd={doc.get('periodEnd')}, docTypeCode={doc.get('docTypeCode')}, ordinanceCode={doc.get('ordinanceCode')}")
                
                # 銘柄コードでフィルタリング（会社コードまたは証券コードで一致）
                filtered = []
                code_4digit = code[:4] if len(code) >= 4 else code
                code_5digit = code.zfill(5) if len(code) < 5 else code
                
                # デバッグ: secCodeが存在する書類のサンプルを表示
                if unique_documents:
                    # secCodeが存在する書類を探す（上場企業の有報）
                    sample_doc_with_sec = None
                    for doc in unique_documents[:10]:  # 最初の10件を確認
                        if doc.get("secCode"):
                            sample_doc_with_sec = doc
                            break
                    
                    if sample_doc_with_sec:
                        logger.info(f"サンプル書類情報（secCodeあり）: secCode={sample_doc_with_sec.get('secCode')}, filerName={sample_doc_with_sec.get('filerName')}, periodEnd={sample_doc_with_sec.get('periodEnd')}")
                    else:
                        # secCodeが存在しない書類のサンプルを表示
                        sample_doc = unique_documents[0]
                        logger.info(f"サンプル書類情報（secCodeなし）: keys={list(sample_doc.keys())}")
                        logger.info(f"  サンプル: secCode={sample_doc.get('secCode')}, filerName={sample_doc.get('filerName')}, docTypeCode={sample_doc.get('docTypeCode')}")
                    
                    # secCodeが存在する書類の数をカウント
                    sec_code_count = sum(1 for doc in unique_documents if doc.get("secCode"))
                    logger.info(f"secCodeが存在する書類: {sec_code_count}件 / 全{len(unique_documents)}件")
                
                for doc in unique_documents:
                    # 証券コードで一致を確認
                    # EDINET APIのレスポンス構造:
                    # - secCode: 証券コード（銘柄コード、4桁または5桁）
                    # - edinetCode: EDINETコード（Eで始まる、会社識別用）
                    # - periodEnd: 期間終了日（年度終了日、YYYY-MM-DD形式）
                    sec_code = doc.get("secCode")
                    if sec_code is None:
                        # secCodeがNoneの場合はスキップ（投資信託など）
                        continue
                    
                    sec_code_str = str(sec_code).strip()
                    period_end = doc.get("periodEnd", "")
                    
                    # 年度の確認（periodEndから年度を抽出）
                    doc_year = None
                    doc_description = doc.get("docDescription", "")
                    is_half_year_report = "半期報告書" in doc_description or doc_type[:3] == "050"
                    
                    if period_end:
                        try:
                            # YYYY-MM-DD形式から年度を抽出
                            period_date = datetime.strptime(period_end[:10], "%Y-%m-%d")
                            # 3月末が年度終了日の場合、その年度は前年
                            if period_date.month == 3:
                                doc_year = period_date.year - 1
                            else:
                                doc_year = period_date.year
                            
                            # 半期報告書の場合、periodEndが年度終了日（3月末）になっている可能性がある
                            # その場合、検索対象年度±1年の範囲で許容する
                            if is_half_year_report and period_date.month == 3:
                                # 半期報告書で3月末がperiodEndの場合、前年度または当該年度として扱う
                                # 例: periodEnd=2026-03-31 → 2025年度または2026年度として扱う
                                if doc_year == year or doc_year == year + 1:
                                    # 検索対象年度またはその翌年度として扱う
                                    doc_year = year  # 検索対象年度に合わせる
                        except (ValueError, TypeError):
                            pass
                    
                    # 年度が一致しない場合はスキップ
                    # periodEndがNoneの場合は年度チェックをスキップ（secCodeでマッチングできれば取得）
                    if doc_year is not None and doc_year != year:
                        logger.debug(f"  年度不一致: secCode={sec_code_str}, periodEnd={period_end}, doc_year={doc_year}, target_year={year}, is_half_year={is_half_year_report}")
                        continue
                    
                    # periodEndがNoneの場合は警告を出すが、マッチングは続行
                    # secCodeでマッチングできれば、検索対象年度として取得する
                    if period_end is None or period_end == "":
                        logger.debug(f"  periodEndがNone: secCode={sec_code_str}, filerName={doc.get('filerName')}, 検索対象年度={year}として取得を試みます")
                    
                    # 複数の形式で一致を確認
                    # secCodeでマッチング（4桁・5桁の両形式に対応）
                    # secCodeは文字列または数値の可能性があるため、文字列に変換して比較
                    # EDINET APIではsecCodeが5桁（例: 72030）で返される場合があるが、
                    # 検索コードは4桁（7203）の場合があるため、先頭4桁で一致を確認
                    sec_code_normalized = sec_code_str.zfill(5)  # 5桁に正規化
                    code_normalized = code.zfill(5)  # 5桁に正規化
                    
                    # 複数の形式で一致を確認
                    # 例: secCode=72030とcode=7203は先頭4桁（7203）で一致
                    is_match = (sec_code_str == code_4digit or 
                                sec_code_str == code_5digit or
                                sec_code_str == code or
                                sec_code_normalized == code_normalized or
                                sec_code_str.startswith(code_4digit) or  # secCodeの先頭がcodeと一致（5桁の場合）
                                sec_code_normalized[:4] == code_normalized[:4] or  # 先頭4桁で一致
                                (len(sec_code_str) == 5 and sec_code_str[:4] == code_4digit))  # 5桁の場合、先頭4桁が4桁コードと一致
                    
                    # デバッグ: マッチングを詳細にログ出力（検索コードを含むsecCodeをチェックする場合のみ）
                    # 検索コードがsecCodeに含まれる場合、または検索コードが7203の場合にログ出力
                    if code_4digit in sec_code_str or sec_code_str.startswith(code_4digit) or code == '7203':
                        logger.debug(f"  マッチング確認: secCode={sec_code_str}, code={code}, code_4digit={code_4digit}, code_5digit={code_5digit}, is_match={is_match}, filerName={doc.get('filerName')}, periodEnd={period_end}, doc_year={doc_year}")
                    
                    if is_match:
                        # periodEndがNoneの場合は、検索対象年度をdocに追加
                        if not period_end or period_end == "":
                            doc["_matched_year"] = year  # 検索対象年度を記録
                        filtered.append(doc)
                        logger.info(f"  マッチ: docID={doc.get('docID')}, secCode={sec_code_str}, filerName={doc.get('filerName')}, periodEnd={period_end}, doc_year={doc_year}, 検索対象年度={year}")
                
                if filtered:
                    all_documents.extend(filtered)
                    logger.info(f"有価証券報告書・半期報告書検索結果: {code} {year}年度 → {len(filtered)}件")
                else:
                    logger.info(f"有価証券報告書・半期報告書が見つかりませんでした: {code} {year}年度 (検索対象: {len(unique_documents)}件)")
                    # デバッグ: 最初の数件の会社コード/証券コードを表示
                    if unique_documents:
                        sample_codes = [(doc.get("filerCode"), doc.get("secCode"), doc.get("docID")) 
                                       for doc in unique_documents[:3]]
                        logger.debug(f"  サンプル: {sample_codes}")
                
            except Exception as e:
                logger.error(f"有報検索エラー: {code} {year}年度 - {e}", exc_info=True)
                continue
        
        return all_documents

    def download_document(
        self,
        doc_id: str,
        doc_type: int = 1,
        save_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """
        書類をダウンロード

        Args:
            doc_id: 書類管理番号
            doc_type: 書類種別（1=XBRL, 2=PDF）
            save_dir: 保存先ディレクトリ（Noneの場合はキャッシュディレクトリ）

        Returns:
            保存先パス（失敗時はNone）
        """
        if not self.api_key:
            logger.warning("EDINET_API_KEYが設定されていないため、書類ダウンロードをスキップします。")
            return None
        
        if save_dir is None:
            save_dir = self.cache_dir
        
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # キャッシュチェック
        if doc_type == 1:  # XBRL
            cache_path = save_dir / f"{doc_id}_xbrl"
            if cache_path.exists() and cache_path.is_dir():
                logger.debug(f"キャッシュから取得: {doc_id} XBRL")
                return cache_path
        elif doc_type == 2:  # PDF
            cache_path = save_dir / f"{doc_id}.pdf"
            if cache_path.exists():
                logger.debug(f"キャッシュから取得: {doc_id} PDF")
                return cache_path
        
        try:
            # 書類取得API
            params = {"type": doc_type}
            response = self._request(f"/documents/{doc_id}", params)
            
            if response.status_code == 404:
                logger.warning(f"書類が見つかりませんでした: {doc_id} type={doc_type}")
                return None
            
            # ファイル保存
            if doc_type == 1:  # XBRL (ZIP)
                zip_path = save_dir / f"{doc_id}_xbrl.zip"
                with open(zip_path, "wb") as f:
                    f.write(response.content)
                
                # ZIPを展開
                extract_dir = save_dir / f"{doc_id}_xbrl"
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # ZIPファイルは削除（展開済みなので不要）
                zip_path.unlink()
                
                logger.info(f"XBRLダウンロード完了: {doc_id}")
                return extract_dir
            
            elif doc_type == 2:  # PDF
                pdf_path = save_dir / f"{doc_id}.pdf"
                with open(pdf_path, "wb") as f:
                    f.write(response.content)
                
                logger.info(f"PDFダウンロード完了: {doc_id}")
                return pdf_path
        
        except Exception as e:
            logger.error(f"書類ダウンロードエラー: {doc_id} type={doc_type} - {e}")
            return None

    def fetch_reports(
        self,
        code: str,
        years: List[int],
        reports_dir: Optional[Path] = None,
        jquants_annual_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        """
        指定年度の有価証券報告書と半期報告書を取得

        Args:
            code: 銘柄コード
            years: 年度のリスト
            reports_dir: レポート保存ディレクトリ（Noneの場合はreports/{code}_edinet）
            jquants_annual_data: J-QUANTSの年度データ（検索効率化のため）

        Returns:
            {year: {docID, submitDate, pdf_path, xbrl_path, docType}} の辞書
        """
        if not self.api_key:
            error_msg = f"EDINET_API_KEYが設定されていないため、有価証券報告書・半期報告書取得をスキップします: code={code}"
            logger.warning(error_msg)
            return {}
        
        # 書類検索（J-QUANTSデータを活用して効率化）
        try:
            documents = self.search_documents(code, years, jquants_data=jquants_annual_data)
        except Exception as e:
            error_msg = f"EDINET API検索エラー: code={code}, error={str(e)}"
            logger.error(error_msg, exc_info=True)
            return {}
        
        if not documents:
            error_msg = f"有価証券報告書・半期報告書が見つかりませんでした: code={code}, years={years}"
            logger.warning(error_msg)
            logger.warning(f"検索条件を確認してください:")
            logger.warning(f"  - 銘柄コード: {code}")
            logger.warning(f"  - 検索対象年度: {years}")
            logger.warning(f"  - J-QUANTSデータ: {'あり' if jquants_annual_data else 'なし'}")
            if jquants_annual_data:
                for record in jquants_annual_data[:3]:  # 最初の3件を表示
                    logger.warning(f"    - CurFYEn={record.get('CurFYEn')}, DiscDate={record.get('DiscDate')}, CurPerType={record.get('CurPerType')}")
            return {}
        
        # レポート保存ディレクトリ
        if reports_dir is None:
            project_root = Path(__file__).parent.parent.parent
            reports_dir = project_root / "reports" / f"{code}_edinet"
        
        reports_dir = Path(reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        results = {}
        
        for doc in documents:
            doc_id = doc.get("docID")
            submit_date = doc.get("submitDateTime", "")
            period_end = doc.get("periodEnd", "")
            doc_type = doc.get("docTypeCode", "")
            doc_description = doc.get("docDescription", "")
            
            if not doc_id:
                continue
            
            # 書類種別を判定（有価証券報告書または半期報告書）
            report_type = None
            if doc_type and len(doc_type) >= 3:
                if doc_type[:3] == "030":
                    report_type = "有価証券報告書"
                elif doc_type[:3] == "050":
                    report_type = "半期報告書"
            if not report_type and doc_description:
                if "有価証券報告書" in doc_description:
                    report_type = "有価証券報告書"
                elif "半期報告書" in doc_description:
                    report_type = "半期報告書"
            
            # 年度を特定（periodEndから年度を抽出）
            year = None
            if period_end:
                try:
                    # YYYY-MM-DD形式から年度を抽出
                    period_date = datetime.strptime(period_end[:10], "%Y-%m-%d")
                    # 3月末が年度終了日の場合、その年度は前年
                    if period_date.month == 3:
                        year = period_date.year - 1
                    else:
                        year = period_date.year
                except (ValueError, TypeError):
                    pass
            
            # 年度が特定できない場合の処理
            if year is None:
                # periodEndがNoneの場合でも、secCodeでマッチングできれば検索対象年度を使用
                # 有価証券報告書は通常、年度終了後3ヶ月以内に提出されるため、
                # 検索対象年度と一致する可能性が高い
                if not period_end:
                    # secCodeでマッチングできている場合は、検索対象年度を使用
                    # ただし、検索対象年度のリストから最も近い年度を選択
                    # ここでは、最初に見つかった書類の年度として、検索対象年度の最初を使用
                    # （実際には、secCodeマッチング時に年度が確定しているはず）
                    # とりあえず、検索対象年度の最初の年度を使用（後で改善可能）
                    if years:  # yearsは検索対象年度のリスト
                        # この書類がどの年度の検索結果かは、検索ループのコンテキストから判断できない
                        # そのため、periodEndがNoneの場合は、secCodeマッチング時に年度を確定する必要がある
                        # ここでは、検索対象年度の最初の年度を仮に使用（後で改善）
                        year = years[0] if years else None
                        logger.debug(f"periodEndがNoneのため、検索対象年度を使用: docID={doc_id}, year={year}")
                    else:
                        logger.debug(f"periodEndがNoneかつ検索対象年度も不明のためスキップ: docID={doc_id}")
                        continue
                # periodEndはあるが年度が特定できない場合は、最新年度として扱う
                logger.warning(f"年度が特定できませんでしたが、有報を取得します: docID={doc_id}, periodEnd={period_end}")
                # 最新年度として扱う（検索対象年度の最大値）
                year = max(years) if years else None
                if year is None:
                    continue
            
            # 年度が検索対象に含まれていない場合でも、近い年度の場合は含める（±1年）
            if year not in years:
                # 検索対象年度に近いかチェック
                year_diff = min([abs(year - y) for y in years]) if years else 999
                if year_diff > 1:
                    logger.debug(f"年度が検索対象外のためスキップ: docID={doc_id}, year={year}, target_years={years}")
                    continue
                else:
                    logger.info(f"年度が検索対象に近いため取得: docID={doc_id}, year={year}, target_years={years}")
                    # 最も近い年度にマッピング
                    closest_year = min(years, key=lambda y: abs(year - y))
                    year = closest_year
            
            # XBRLをダウンロード（要約用）
            xbrl_path = self.download_document(doc_id, doc_type=1, save_dir=reports_dir)
            
            # PDFもダウンロード（ダウンロード用のみ）
            pdf_path = self.download_document(doc_id, doc_type=2, save_dir=reports_dir)
            
            if xbrl_path or pdf_path:
                results[year] = {
                    "docID": doc_id,
                    "submitDate": submit_date[:10] if submit_date else "",
                    "pdf_path": str(pdf_path) if pdf_path else None,
                    "xbrl_path": str(xbrl_path) if xbrl_path else None,
                    "docType": report_type or "不明",
                    "docTypeCode": doc_type,
                    "docDescription": doc_description,
                    "filerName": doc.get("filerName", ""),  # 提出者名を追加
                }
        
        return results

