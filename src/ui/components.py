"""
UIコンポーネント

分析結果の表示コンポーネントを提供します。
"""

import streamlit as st
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from src.utils.formatters import extract_fiscal_year_from_fy_end


def display_analysis_results(report_data: Dict[str, Any], graphs: List[Dict[str, Any]]):
    """
    データを表示
    
    Args:
        report_data: レポートデータ
        graphs: グラフデータのリスト
    """
    code = report_data.get("code", "")
    name = report_data.get("name", "")
    sector_name = report_data.get("sector_33_name", "")
    market_name = report_data.get("market_name", "")
    metrics = report_data.get("metrics", {})
    years = metrics.get("years", [])
    edinet_data = report_data.get("edinet_data", {})
    
    # 年度を事前計算してyearsデータに追加
    for year in years:
        if "fiscal_year" not in year:
            year["fiscal_year"] = extract_fiscal_year_from_fy_end(year.get("fy_end", ""))
    
    # 最新年度のEDINETデータ
    latest_edinet_data = None
    latest_edinet_year = None
    if edinet_data:
        latest_edinet_year = max(edinet_data.keys())
        latest_edinet_data = edinet_data[latest_edinet_year]
    
    # グラフをセクションタイトルでグループ化
    graph_dict = {}
    for graph in graphs:
        section_title = graph.get('section_title', '')
        if section_title not in graph_dict:
            graph_dict[section_title] = []
        graph_dict[section_title].append(graph)
    
    # ①上部：銘柄名・業種・市場・作成日
    with st.container():
        col_info, col_pdf = st.columns([3, 1])
        with col_info:
            st.header(f"{code} {name}")
            if sector_name or market_name:
                st.markdown(f"**{sector_name} | {market_name}**")
            
            # 最新分析日の表示
            timestamp = report_data.get('timestamp')
            if timestamp:
                # ISO形式のタイムスタンプを日付のみに変換
                try:
                    if isinstance(timestamp, str):
                        dt = datetime.fromisoformat(timestamp)
                    else:
                        dt = timestamp
                    date_str = dt.strftime('%Y年%m月%d日')
                    st.markdown(f"*最新分析日: {date_str}*")
                except (ValueError, AttributeError):
                    # パースに失敗した場合は現在日時を使用
                    st.markdown(f"*最新分析日: {datetime.now().strftime('%Y年%m月%d日')}*")
            else:
                # タイムスタンプがない場合は現在日時を使用
                st.markdown(f"*最新分析日: {datetime.now().strftime('%Y年%m月%d日')}*")
        with col_pdf:
            # 有報PDFダウンロードボタン（keyを指定してページリロードを防ぐ）
            if latest_edinet_data and latest_edinet_data.get("pdf_path"):
                pdf_path = Path(latest_edinet_data.get("pdf_path"))
                if pdf_path.exists():
                    pdf_absolute_path = pdf_path.resolve()
                    try:
                        # ファイルを事前に読み込む（ボタンクリック時に読み込まない）
                        pdf_data_key = f"pdf_data_{code}_{latest_edinet_year}"
                        if pdf_data_key not in st.session_state:
                            with open(pdf_absolute_path, "rb") as pdf_file:
                                st.session_state[pdf_data_key] = pdf_file.read()
                        
                        st.download_button(
                            label="📥 有報PDF",
                            data=st.session_state[pdf_data_key],
                            file_name=pdf_path.name,
                            mime="application/pdf",
                            key=f"pdf_download_{code}_{latest_edinet_year}",
                            width='stretch'
                        )
                    except Exception as e:
                        st.error(f"PDF読み込みエラー: {e}")
            
            # 履歴がある場合、「最新情報で再分析」ボタンを表示
            if code in st.session_state.get('analysis_history', {}):
                if st.button("🔄 最新情報で再分析", width='stretch', key=f"reanalysis_button_{code}"):
                    st.session_state['force_reanalysis'] = True
                    st.session_state['reanalysis_code'] = code
                    st.session_state['analysis_codes'] = code
                    st.rerun()
    
    # ②年度別財務データを銘柄名セクションの下に表示
    st.markdown("---")
    st.subheader("📊 年度別財務データ")
    from src.ui.table import display_financial_data_table
    display_financial_data_table(years)
    
    st.markdown("---")
    
    # ③左下、④〜⑨右下の2列レイアウト
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        _display_business_overview(col_left, edinet_data, latest_edinet_data, latest_edinet_year)
    
    with col_right:
        _display_graphs(col_right, graphs, graph_dict)


def _display_business_overview(
    col: Any,  # st.delta_generator.DeltaGenerator
    edinet_data: Dict[str, Any],
    latest_edinet_data: Optional[Dict[str, Any]],
    latest_edinet_year: Optional[str]
) -> None:
    """
    事業概要・課題を表示
    
    Args:
        col: Streamlitのカラムコンテナ
        edinet_data: EDINETデータの辞書
        latest_edinet_data: 最新年度のEDINETデータ
        latest_edinet_year: 最新年度の文字列
    """
    with col:
        st.subheader("📋 有価証券報告書の要約")
        
        if latest_edinet_data and latest_edinet_data.get("management_policy"):
            # 副題：年度と提出日を表示
            submit_date = latest_edinet_data.get("submitDate", "")
            if submit_date:
                if len(submit_date) == 8:  # YYYYMMDD形式
                    submit_date_formatted = f"{submit_date[:4]}-{submit_date[4:6]}-{submit_date[6:8]}"
                elif len(submit_date) >= 10:  # YYYY-MM-DD形式
                    submit_date_formatted = submit_date[:10]
                else:
                    submit_date_formatted = submit_date
            else:
                submit_date_formatted = "不明"
            
            # 書類種別を表示（有価証券報告書または半期報告書）
            doc_type = latest_edinet_data.get("docType", "不明")
            doc_description = latest_edinet_data.get("docDescription", "")
            if doc_type == "不明" and doc_description:
                # docDescriptionから書類種別を判定
                if "有価証券報告書" in doc_description:
                    doc_type = "有価証券報告書"
                elif "半期報告書" in doc_description:
                    doc_type = "半期報告書"
            
            st.markdown(f"**{latest_edinet_year}年度{doc_type}より（提出日: {submit_date_formatted}）**")
            
            policy_text = latest_edinet_data.get("management_policy", "")
            if policy_text:
                # 注意書きを追加
                disclaimer = "\n\n---\n\n*注: 本要約はAIによる自動生成です。正確な情報については、有価証券報告書の原本をご確認ください。*"
                policy_text = policy_text + disclaimer
                
                import re
                # 見出し行（## で始まる行）をすべて削除し、空行も削除
                lines = policy_text.split('\n')
                filtered_lines = []
                for line in lines:
                    stripped = line.strip()
                    # 見出し行をスキップ
                    if stripped.startswith('##'):
                        continue
                    # <br>タグを改行に変換
                    line = line.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
                    filtered_lines.append(line)
                # 連続する空行を1つにまとめる
                policy_text = '\n'.join(filtered_lines)
                policy_text = re.sub(r'\n{3,}', '\n\n', policy_text)  # 3つ以上の連続する改行を2つに
                policy_text = policy_text.strip()  # 先頭と末尾の空白を削除
                
                # マークダウンをそのまま表示（Streamlitが自動的にレンダリング）
                st.markdown(policy_text)
        else:
            if edinet_data:
                st.warning(f"EDINETデータは取得されましたが、要約が生成されていません（年度: {list(edinet_data.keys())}）")
                st.info("""
                **考えられる原因:**
                - PDFの解析に失敗した
                - LLM要約の生成に失敗した（Ollamaが起動していない可能性）
                - 経営方針セクションがPDFに含まれていない
                
                **確認方法:**
                - ターミナルのログでエラーメッセージを確認してください
                - Ollamaが起動しているか確認: `ollama list`
                """)
            else:
                # 環境変数の確認
                from src.config import config
                edinet_api_key = config.edinet_api_key
                
                if not edinet_api_key:
                    st.error("**EDINET_API_KEYが設定されていません**")
                    st.info("""
                    `.env`ファイルに`EDINET_API_KEY`を設定してください。
                    EDINET APIキーは[EDINET API](https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1)から取得できます。
                    """)
                else:
                    st.warning("**EDINETデータが取得できませんでした**")
                    st.info("""
                    **考えられる原因:**
                    - 有価証券報告書・半期報告書がEDINETに登録されていない
                    - 検索対象年度に該当する書類がない
                    - EDINET APIのレート制限に達している
                    - ネットワークエラー
                    
                    **確認方法:**
                    - ターミナルのログを確認してください
                    - EDINET APIの利用状況を確認してください
                    - 右カラムの「診断情報とトラブルシューティング」を展開して詳細を確認してください
                    """)


def _display_graphs(
    col: Any,  # st.delta_generator.DeltaGenerator
    graphs: List[Dict[str, Any]],
    graph_dict: Dict[str, List[Dict[str, Any]]]
) -> None:
    """
    グラフをタブ形式で表示
    
    Args:
        col: Streamlitのカラムコンテナ
        graphs: グラフデータのリスト
        graph_dict: セクションタイトルでグループ化されたグラフ辞書
    """
    with col:
        # タブ用のセクションリストを作成
        tab_labels = []
        tab_contents = []
        
        # グラフセクションを順番に追加
        section_order = [
            "事業効率",
            "キャッシュフロー",
            "株主価値の蓄積",
            "配当政策と市場評価",
            "市場評価",
            "株価とEPSの乖離"
        ]
        
        for section_title in section_order:
            if section_title in graph_dict:
                for graph in graph_dict[section_title]:
                    # タブラベルを作成
                    tab_label = f"📈 {graph.get('section_title', section_title)}"
                    tab_labels.append(tab_label)
                    
                    # グラフコンテンツを作成
                    title = graph.get('title', '')
                    title_html = title.replace('<br>', '<br>').replace('<br/>', '<br>').replace('<br />', '<br>')
                    html_content = graph.get('html', '')
                    
                    # JavaScriptでデータラベルを追加（Plotlyグラフが読み込まれた後に実行）
                    html_with_labels = f"""
                    {html_content}
                    <script>
                        (function() {{
                            function addDataLabels() {{
                                // すべてのPlotlyグラフを取得
                                const plotlyDivs = document.querySelectorAll('[id^="graph_"]');
                                plotlyDivs.forEach(div => {{
                                    // Plotlyのデータを取得
                                    if (window.Plotly && div.id) {{
                                        Plotly.d3.json(div.id).then(function(gd) {{
                                            if (gd && gd.data) {{
                                                // 各トレースにデータラベルを追加
                                                gd.data.forEach(trace => {{
                                                    if (trace.y && Array.isArray(trace.y)) {{
                                                        // 数値をテキストとして追加
                                                        trace.text = trace.y.map(y => {{
                                                            if (y === null || y === undefined || isNaN(y)) return '';
                                                            // 数値のフォーマット（小数点以下1桁）
                                                            return y.toFixed(1);
                                                        }});
                                                        trace.textposition = 'top center';
                                                        trace.textfont = {{ size: 10, color: trace.line ? trace.line.color : '#000' }};
                                                    }}
                                                }});
                                                // グラフを更新
                                                Plotly.redraw(div, gd.data, gd.layout);
                                            }}
                                        }}).catch(function() {{
                                            // JSON取得に失敗した場合は、直接データを操作
                                            if (div.data) {{
                                                div.data.forEach(trace => {{
                                                    if (trace.y && Array.isArray(trace.y)) {{
                                                        trace.text = trace.y.map(y => {{
                                                            if (y === null || y === undefined || isNaN(y)) return '';
                                                            return y.toFixed(1);
                                                        }});
                                                        trace.textposition = 'top center';
                                                        trace.textfont = {{ size: 10 }};
                                                    }}
                                                }});
                                                Plotly.redraw(div);
                                            }}
                                        }});
                                    }}
                                }});
                            }}
                            
                            // Plotlyが読み込まれるまで待機してから実行
                            if (typeof Plotly !== 'undefined') {{
                                setTimeout(addDataLabels, 1000);
                            }} else {{
                                window.addEventListener('load', function() {{
                                    setTimeout(addDataLabels, 2000);
                                }});
                            }}
                        }})();
                    </script>
                    """
                    # タイトルとグラフコンテンツを分けて保存
                    tab_contents.append({
                        'title': title_html,
                        'html': html_with_labels
                    })
        
        # タブ形式で表示
        if tab_labels:
            tabs = st.tabs(tab_labels)
            for i, tab in enumerate(tabs):
                with tab:
                    content = tab_contents[i]
                    # タイトルを表示
                    if isinstance(content, dict) and 'title' in content:
                        st.markdown(f"**{content['title']}**", unsafe_allow_html=True)
                        html_content = content['html']
                    else:
                        html_content = content
                    # HTMLグラフコンテンツを表示（scrolling=Trueで軸が正しく表示される）
                    st.components.v1.html(html_content, height=600, scrolling=True)
        else:
            st.info("グラフデータがありません")

