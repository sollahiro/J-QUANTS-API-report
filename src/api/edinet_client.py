"""
EDINET API クライアント

有価証券報告書の取得機能を提供します。
"""

import os
import time
import zipfile
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

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
            api_key: APIキー。Noneの場合は環境変数EDINET_API_KEYから取得
            base_url: APIベースURL。Noneの場合はデフォルト値を使用
        """
        load_dotenv()
        self.api_key = api_key or os.getenv("EDINET_API_KEY")
        
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
        form_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        有価証券報告書を検索

        Args:
            code: 銘柄コード（4桁または5桁）
            years: 年度のリスト（例: [2023, 2024]）
            doc_type_code: 法令コード（デフォルト: "030"=有価証券報告書）
            form_code: 様式コード（オプション、指定しない場合は全様式）

        Returns:
            書類情報のリスト
        """
        if not self.api_key:
            logger.warning("EDINET_API_KEYが設定されていないため、有報検索をスキップします。")
            return []
        
        all_documents = []
        
        # 年度ごとに検索（提出日を基準に検索）
        for year in years:
            # 有価証券報告書は通常、年度終了後3ヶ月以内に提出される
            # 例: 2023年度（2023-04-01 ～ 2024-03-31）の有報は2024年5-6月頃に提出
            # 検索期間: 年度終了日の翌月から3ヶ月後まで
            # より広い範囲で検索（5月、6月、7月、8月）
            try:
                # EDINET APIの検索パラメータ
                # date: 提出日（YYYY-MM-DD形式）
                # type: 取得情報の種類（2=提出書類一覧+メタデータ）
                # docTypeCode: 書類種別コード（030=有価証券報告書）
                # 複数の日付で検索を試みる（有報は年度終了後数ヶ月で提出される）
                # EDINET APIの仕様: 書類一覧APIは指定した日付に提出された書類を取得
                # 有価証券報告書は通常、年度終了後3ヶ月以内（5-6月）に提出される
                search_dates = []
                # 年度終了後の提出期間を広く検索
                # 有価証券報告書は通常、年度終了後3ヶ月以内に提出されるが、
                # 企業によって提出時期が異なるため、広い範囲で検索
                # 検索期間: 年度終了日の翌月から6ヶ月後まで
                # 例: 2023年度（2023-04-01 ～ 2024-03-31）の有報は2024年4月～9月頃に提出
                # 検索効率を考慮し、提出が集中する期間（4-6月）は細かく、それ以外は粗く検索
                start_month = 4  # 年度終了日の翌月
                end_month = 9    # 6ヶ月後
                
                for month in range(start_month, end_month + 1):
                    if month <= 6:  # 4-6月は提出が集中するため、毎日検索
                        # 月の日数を取得
                        if month == 2:
                            last_day = 28 if (year+1) % 4 != 0 or ((year+1) % 100 == 0 and (year+1) % 400 != 0) else 29
                        elif month in [4, 6, 9, 11]:
                            last_day = 30
                        else:
                            last_day = 31
                        for day in range(1, last_day + 1):
                            try:
                                search_dates.append(datetime(year+1, month, day).strftime("%Y-%m-%d"))
                            except ValueError:
                                pass
                    else:  # 7-9月は月初日、15日、月末日を検索
                        search_dates.append(datetime(year+1, month, 1).strftime("%Y-%m-%d"))
                        search_dates.append(datetime(year+1, month, 15).strftime("%Y-%m-%d"))
                        # 月末日を追加（月によって日数が異なるため、try-exceptで処理）
                        try:
                            if month == 2:
                                last_day = 28 if (year+1) % 4 != 0 or ((year+1) % 100 == 0 and (year+1) % 400 != 0) else 29
                            elif month in [4, 6, 9, 11]:
                                last_day = 30
                            else:
                                last_day = 31
                            search_dates.append(datetime(year+1, month, last_day).strftime("%Y-%m-%d"))
                        except ValueError:
                            pass
                
                logger.info(f"有報検索開始: code={code}, year={year}, dates={search_dates}, type={doc_type_code}")
                
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
                    
                    # 有価証券報告書のみを対象
                    # EDINET APIの仕様:
                    # - ordinanceCode=010: 金融商品取引法（内国会社）
                    # - ordinanceCode=020: 金融商品取引法（外国会社等）
                    # - ordinanceCode=030: 金融商品取引法（特定有価証券）
                    # - docTypeCode: 6桁または3桁の文字列（例: 030000=第三号様式 有価証券報告書）
                    #   先頭3桁が030のものが有価証券報告書
                    #   ただし、実際のAPIレスポンスではdocTypeCodeが3桁の場合もある
                    #   書類名（docDescription）に「有価証券報告書」が含まれる場合も有価証券報告書として扱う
                    # 上場企業の有価証券報告書はordinanceCode=010または020で、docTypeCodeの先頭3桁が030
                    is_securities_report = False
                    if ordinance_code in ["010", "020"]:
                        # docTypeCodeの先頭3桁が030のものを有価証券報告書として判定
                        if doc_type and len(doc_type) >= 3 and doc_type[:3] == "030":
                            is_securities_report = True
                        # docDescriptionに「有価証券報告書」が含まれる場合も有価証券報告書として扱う
                        # （docTypeCodeが正確でない場合のフォールバック）
                        elif doc_description and "有価証券報告書" in doc_description:
                            is_securities_report = True
                    
                    if not is_securities_report:
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
                
                logger.info(f"有価証券報告書の内訳: secCodeあり={sec_code_count}件, secCodeなし={no_sec_code_count}件")
                
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
                    if period_end:
                        try:
                            # YYYY-MM-DD形式から年度を抽出
                            period_date = datetime.strptime(period_end[:10], "%Y-%m-%d")
                            # 3月末が年度終了日の場合、その年度は前年
                            if period_date.month == 3:
                                doc_year = period_date.year - 1
                            else:
                                doc_year = period_date.year
                        except (ValueError, TypeError):
                            pass
                    
                    # 年度が一致しない場合はスキップ
                    # periodEndがNoneの場合は年度チェックをスキップ（後で確認）
                    if doc_year is not None and doc_year != year:
                        logger.debug(f"  年度不一致: secCode={sec_code_str}, periodEnd={period_end}, doc_year={doc_year}, target_year={year}")
                        continue
                    
                    # periodEndがNoneの場合は警告を出すが、マッチングは続行
                    if period_end is None or period_end == "":
                        logger.debug(f"  periodEndがNone: secCode={sec_code_str}, filerName={doc.get('filerName')}")
                    
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
                    
                    # デバッグ: 7203のマッチングを詳細にログ出力（7203を含む場合のみ）
                    if '7203' in sec_code_str or sec_code_str.startswith('7203') or code == '7203':
                        logger.info(f"  7203マッチング確認: secCode={sec_code_str}, code={code}, code_4digit={code_4digit}, code_5digit={code_5digit}, is_match={is_match}, filerName={doc.get('filerName')}, periodEnd={period_end}, doc_year={doc_year}")
                    
                    if is_match:
                        filtered.append(doc)
                        logger.info(f"  マッチ: docID={doc.get('docID')}, secCode={sec_code_str}, filerName={doc.get('filerName')}, periodEnd={period_end}, doc_year={doc_year}")
                
                if filtered:
                    all_documents.extend(filtered)
                    logger.info(f"有報検索結果: {code} {year}年度 → {len(filtered)}件")
                else:
                    logger.info(f"有報が見つかりませんでした: {code} {year}年度 (検索対象: {len(unique_documents)}件)")
                    # デバッグ: 最初の数件の会社コード/証券コードを表示
                    if unique_documents:
                        sample_codes = [(doc.get("filerCode"), doc.get("secCode"), doc.get("docID")) 
                                       for doc in unique_documents[:3]]
                        logger.debug(f"  サンプル: {sample_codes}")
                
            except Exception as e:
                logger.error(f"有報検索エラー: {code} {year}年度 - {e}")
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
        reports_dir: Optional[Path] = None
    ) -> Dict[int, Dict[str, Any]]:
        """
        指定年度の有価証券報告書を取得

        Args:
            code: 銘柄コード
            years: 年度のリスト
            reports_dir: レポート保存ディレクトリ（Noneの場合はreports/{code}_edinet）

        Returns:
            {year: {docID, submitDate, pdf_path, xbrl_path}} の辞書
        """
        if not self.api_key:
            logger.warning("EDINET_API_KEYが設定されていないため、有報取得をスキップします。")
            return {}
        
        # 書類検索
        documents = self.search_documents(code, years)
        
        if not documents:
            logger.info(f"有報が見つかりませんでした: {code}")
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
            
            if not doc_id:
                continue
            
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
            
            # 年度が特定できない場合はスキップ
            if year is None or year not in years:
                continue
            
            # PDFのみダウンロード（XBRLは廃止）
            pdf_path = self.download_document(doc_id, doc_type=2, save_dir=reports_dir)
            
            if pdf_path:
                results[year] = {
                    "docID": doc_id,
                    "submitDate": submit_date[:10] if submit_date else "",
                    "pdf_path": str(pdf_path) if pdf_path else None,
                    "xbrl_path": None,  # XBRLは廃止
                }
        
        return results

