"""
サイドバーコンポーネント

StreamlitアプリケーションのサイドバーUIを提供します。
"""

import streamlit as st
from typing import Tuple, Optional


def render_sidebar() -> Tuple[Optional[str], bool, Optional[str]]:
    """
    サイドバーをレンダリング
    
    Returns:
        銘柄コード入力、分析ボタンのクリック状態、選択された履歴の銘柄コードのタプル
    """
    with st.sidebar:
        st.markdown('<h1 style="color: #1f77b4; margin-bottom: 2rem;">📊 Educe</h1>', unsafe_allow_html=True)

        st.markdown("---")

        # 銘柄コード入力
        code_input = st.text_input(
            "銘柄コード",
            placeholder="例: 6501",
            help="銘柄コードを入力してください"
        )

        # 分析ボタン
        analyze_button = st.button("🔍 分析", type="primary", width='stretch')

        st.markdown("---")
        
        # 履歴セクション
        selected_history_code = _display_history()
    
    return code_input, analyze_button, selected_history_code


def _display_history() -> Optional[str]:
    """
    分析履歴を表示
    
    Returns:
        選択された履歴の銘柄コード（選択されていない場合はNone）
    """
    if 'analysis_history' not in st.session_state or not st.session_state['analysis_history']:
        return None
    
    st.markdown("### 📋 分析履歴")
    
    # 履歴を銘柄コード順（昇順）でソート
    sorted_codes = sorted(st.session_state['analysis_history'].keys())
    
    selected_code = None
    
    for code in sorted_codes:
        history_entry = st.session_state['analysis_history'][code]
        name = history_entry.get('name', '')
        display_text = f"{code} {name}" if name else code
        
        # ボタンで履歴を選択
        button_key = f"history_{code}"
        if st.button(display_text, key=button_key, width='stretch'):
            selected_code = code
            st.session_state['selected_history_code'] = code
            st.rerun()
    
    # セッション状態から選択された履歴コードを取得
    if 'selected_history_code' in st.session_state:
        selected_code = st.session_state['selected_history_code']
        # 一度取得したらクリア（次回の表示時に影響しないように）
        del st.session_state['selected_history_code']
        return selected_code
    
    return None

