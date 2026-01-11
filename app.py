"""
Educe - Streamlitアプリケーション
投資判断分析ツールのWebインターフェース
"""

import streamlit as st
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import time
import threading

logger = logging.getLogger(__name__)

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.analysis.individual import IndividualAnalyzer
from src.report.graph_generator import GraphGenerator
from src.utils.formatters import format_currency, extract_fiscal_year_from_fy_end
from src.ui.styles import get_custom_css
from src.ui.sidebar import render_sidebar
from src.ui.components import display_analysis_results
from src.ui.analysis_handler import run_analysis
from src.ui.table import create_financial_data_table

st.set_page_config(
    page_title="Educe - 投資判断分析ツール",
    page_icon="📊",
    layout="wide"
)

# カスタムCSS
st.markdown(get_custom_css(), unsafe_allow_html=True)

# 履歴管理の初期化
if 'analysis_history' not in st.session_state:
    st.session_state['analysis_history'] = {}
    
    # キャッシュから分析結果を読み込んで履歴に追加
    from src.utils.cache import CacheManager
    cache_manager = CacheManager()
    
    # キャッシュディレクトリから分析結果を検索
    cache_dir = Path("cache")
    if cache_dir.exists():
        for cache_file in cache_dir.glob("individual_analysis_*.pkl"):
            # キャッシュキーを抽出（例: individual_analysis_6501.pkl -> 6501）
            cache_key = cache_file.stem.replace("individual_analysis_", "")
            
            # キャッシュからデータを取得
            cached_data = cache_manager.get(f"individual_analysis_{cache_key}")
            if cached_data:
                # 銘柄コードと名前を取得
                code = cache_key
                name = cached_data.get("name", "")
                
                # タイムスタンプを取得（キャッシュファイルの更新日時を使用）
                try:
                    cache_mtime = cache_file.stat().st_mtime
                    timestamp = datetime.fromtimestamp(cache_mtime).isoformat()
                except (OSError, ValueError):
                    timestamp = datetime.now().isoformat()
                
                # 履歴に追加
                st.session_state['analysis_history'][code] = {
                    'timestamp': timestamp,
                    'code': code,
                    'name': name,
                    'report_data': cached_data
                }
        
        if st.session_state['analysis_history']:
            logger.info(f"キャッシュから履歴を読み込みました: {len(st.session_state['analysis_history'])}件")

# サイドバー: ロゴ + 検索フォーム + ボタン + 履歴
code_input, analyze_button, selected_history_code = render_sidebar()

def create_graph_from_html(html_content):
    """HTMLからPlotlyグラフを抽出（簡易版）"""
    # GraphGeneratorが生成するHTMLから直接表示するため、
    # ここではHTMLコンテンツをそのまま返す
    return html_content

# メインコンテンツ
# 分析結果をsession_stateに保存して、ボタンクリック時も保持
# 分析進行状況の表示制御
analysis_in_progress_key = "analysis_in_progress"
# 分析中フラグの初期化
if analysis_in_progress_key not in st.session_state:
    st.session_state[analysis_in_progress_key] = False

# 再分析フラグの確認
force_reanalysis = st.session_state.get('force_reanalysis', False)
reanalysis_code = None
if force_reanalysis:
    reanalysis_code = st.session_state.get('reanalysis_code')
    st.session_state['force_reanalysis'] = False
    if 'reanalysis_code' in st.session_state:
        del st.session_state['reanalysis_code']

# サイドバーから履歴が選択された場合
if selected_history_code:
    code = selected_history_code
    if code in st.session_state['analysis_history']:
        history_entry = st.session_state['analysis_history'][code]
        report_data = history_entry['report_data'].copy()
        report_data['timestamp'] = history_entry['timestamp']
        st.session_state['analysis_results'] = [(code, report_data)]
        st.session_state['analysis_codes'] = code

# 再分析が要求された場合
if reanalysis_code:
    code = reanalysis_code
    st.session_state[analysis_in_progress_key] = True
    
    # キャッシュを削除してから再分析
    from src.utils.cache import CacheManager
    from pathlib import Path
    
    cache_manager = CacheManager()
    cache_key = f"individual_analysis_{code}"
    
    # EDINET要約のキャッシュを削除（cache/edinetディレクトリ全体を削除）
    # キャッシュはpklに統合済みのため、cache/edinetディレクトリは不要
    edinet_cache_dir = Path("cache/edinet")
    if edinet_cache_dir.exists():
        import shutil
        try:
            shutil.rmtree(edinet_cache_dir)
            logger.info(f"EDINETキャッシュディレクトリを削除しました: code={code}, パス={edinet_cache_dir}")
        except Exception as e:
            logger.warning(f"EDINETキャッシュディレクトリの削除に失敗しました: {e}")
    
    # 分析結果のキャッシュを削除（pklキャッシュ）
    cache_manager.clear(cache_key)
    logger.info(f"分析結果キャッシュを削除しました: code={code}")
    
    # 進捗表示コンテナ（分析中のみ表示）
    progress_container = st.container()
    with progress_container:
        st.markdown("### 📊 分析進行状況")
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
    
    try:
        # 分析ハンドラーを使用して分析を実行（キャッシュなしで実行）
        report_data = run_analysis(code, status_placeholder, progress_bar)
        
        if report_data:
            # タイムスタンプを追加
            timestamp = datetime.now().isoformat()
            report_data['timestamp'] = timestamp
            
            # 履歴に保存（既存の場合は上書き）
            st.session_state['analysis_history'][code] = {
                'timestamp': timestamp,
                'code': code,
                'name': report_data.get('name', ''),
                'report_data': report_data
            }
            
            # 分析結果をsession_stateに保存（ボタンクリック時も保持）
            st.session_state['analysis_results'] = [(code, report_data)]
            st.session_state['analysis_codes'] = code
            
            # 分析完了後、進行状況セクションを非表示にする
            if progress_bar:
                progress_bar.progress(100)
            if status_placeholder:
                stock_name = report_data.get("name", code)
                status_placeholder.markdown(f"✅ **{code} ({stock_name}) の分析完了**")
            time.sleep(0.5)  # 完了表示を少し見せる
            # 分析完了フラグを設定（次のrerunで進行状況バーを非表示にする）
            st.session_state[analysis_in_progress_key] = False
            # ページを再読み込みして進行状況セクションを非表示にする
            st.rerun()
        
    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")
        import traceback
        error_traceback = traceback.format_exc()
        st.code(error_traceback)
        # ログにも出力
        import logging
        logging.error(f"Streamlitアプリエラー: {error_traceback}")
        # エラー時も分析中フラグをリセット
        st.session_state[analysis_in_progress_key] = False

if analyze_button:
    # 分析ボタンがクリックされた時、分析中フラグを設定
    st.session_state[analysis_in_progress_key] = True
    if not code_input:
        st.error("銘柄コードを入力してください")
        st.session_state[analysis_in_progress_key] = False
    else:
        # 銘柄コードを取得
        code = code_input.strip()
        
        if not code:
            st.error("有効な銘柄コードを入力してください")
            st.session_state[analysis_in_progress_key] = False
        else:
            # 履歴がある場合で、再分析フラグが立っていない場合は履歴を表示
            if code in st.session_state['analysis_history'] and not force_reanalysis:
                history_entry = st.session_state['analysis_history'][code]
                report_data = history_entry['report_data'].copy()
                report_data['timestamp'] = history_entry['timestamp']
                st.session_state['analysis_results'] = [(code, report_data)]
                st.session_state['analysis_codes'] = code_input
                st.session_state[analysis_in_progress_key] = False
                st.rerun()
            else:
                # 進捗表示コンテナ（分析中のみ表示）
                progress_container = st.container()
                with progress_container:
                    st.markdown("### 📊 分析進行状況")
                    status_placeholder = st.empty()
                    progress_bar = st.progress(0)
                
                try:
                    # 分析ハンドラーを使用して分析を実行
                    report_data = run_analysis(code, status_placeholder, progress_bar)
                    
                    if report_data:
                        # タイムスタンプを追加
                        timestamp = datetime.now().isoformat()
                        report_data['timestamp'] = timestamp
                        
                        # edinet_dataが含まれているか確認（デバッグ用）
                        edinet_data = report_data.get('edinet_data', {})
                        if edinet_data:
                            logger.info(f"履歴保存: edinet_dataが含まれています (年度: {list(edinet_data.keys())})")
                            # 各年度のmanagement_policyを確認
                            for year, year_data in edinet_data.items():
                                if 'management_policy' in year_data:
                                    policy_len = len(year_data['management_policy']) if isinstance(year_data['management_policy'], str) else 0
                                    logger.info(f"  年度 {year}: management_policyの長さ = {policy_len}文字")
                                else:
                                    logger.warning(f"  年度 {year}: management_policyが含まれていません")
                        else:
                            logger.warning(f"履歴保存: edinet_dataが含まれていません")
                        
                        # 履歴に保存（既存の場合は上書き）
                        st.session_state['analysis_history'][code] = {
                            'timestamp': timestamp,
                            'code': code,
                            'name': report_data.get('name', ''),
                            'report_data': report_data
                        }
                        
                        # 分析結果をsession_stateに保存（ボタンクリック時も保持）
                        st.session_state['analysis_results'] = [(code, report_data)]
                        st.session_state['analysis_codes'] = code_input
                        
                        # 分析完了後、進行状況セクションを非表示にする
                        if progress_bar:
                            progress_bar.progress(100)
                        if status_placeholder:
                            stock_name = report_data.get("name", code)
                            status_placeholder.markdown(f"✅ **{code} ({stock_name}) の分析完了**")
                        time.sleep(0.5)  # 完了表示を少し見せる
                        # 分析完了フラグを設定（次のrerunで進行状況バーを非表示にする）
                        st.session_state[analysis_in_progress_key] = False
                        # ページを再読み込みして進行状況セクションを非表示にする
                        st.rerun()
                    
                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}")
                    import traceback
                    error_traceback = traceback.format_exc()
                    st.code(error_traceback)
                    # ログにも出力
                    import logging
                    logging.error(f"Streamlitアプリエラー: {error_traceback}")
                    # エラー時も分析中フラグをリセット
                    st.session_state[analysis_in_progress_key] = False

# 分析結果を表示（session_stateから取得、ボタンクリック時も保持）
if 'analysis_results' in st.session_state and st.session_state['analysis_results']:
    all_report_data = st.session_state['analysis_results']
    if all_report_data:
        code, report_data = all_report_data[0]
        
        report_generator = GraphGenerator()
        
        # グラフを生成
        graphs = report_generator._create_interactive_graphs(report_data)
        
        # 分析結果を表示（「最新情報で再分析」ボタンはcomponents.py内で表示）
        display_analysis_results(report_data, graphs)

elif not analyze_button:
    st.info("👈 サイドバーから銘柄コードを入力して「分析」ボタンをクリックしてください。")