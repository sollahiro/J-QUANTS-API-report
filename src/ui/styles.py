"""
UIスタイル定義

StreamlitアプリケーションのカスタムCSSを提供します。
"""

CUSTOM_CSS = """
<style>
    /* 左カラムにボーダーを追加 */
    [data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-of-type {
        border-right: 2px solid #e0e0e0;
        padding-right: 1.5rem;
    }
    
    /* 右カラムのパディング */
    [data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-of-type {
        padding-left: 1.5rem;
    }
    
    /* 年度別財務データテーブルの年度列を固定 */
    [data-testid="stDataFrame"] table thead tr th:first-child,
    [data-testid="stDataFrame"] table tbody tr td:first-child {
        position: sticky !important;
        left: 0 !important;
        background: white !important;
        background-color: white !important;
        z-index: 10 !important;
        border-right: 2px solid #e0e0e0 !important;
        box-shadow: 2px 0 4px rgba(0,0,0,0.1) !important;
        min-width: 80px !important;
    }
    
    [data-testid="stDataFrame"] table thead tr th:first-child {
        z-index: 11 !important;
    }
    
    /* テーブルの横スクロールを有効化 */
    [data-testid="stDataFrame"] {
        overflow-x: auto !important;
        display: block !important;
    }
    
    /* テーブルコンテナの設定 */
    [data-testid="stDataFrame"] > div {
        overflow-x: auto !important;
        display: block !important;
    }
    
    /* テーブル自体の設定 */
    [data-testid="stDataFrame"] table {
        position: relative !important;
        width: 100% !important;
    }
    
    
    /* スクロールバーのスタイル */
    .left-column::-webkit-scrollbar,
    .right-column::-webkit-scrollbar {
        width: 8px;
    }
    .left-column::-webkit-scrollbar-track,
    .right-column::-webkit-scrollbar-track {
        background: #f1f1f1;
    }
    .left-column::-webkit-scrollbar-thumb,
    .right-column::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 4px;
    }
    .left-column::-webkit-scrollbar-thumb:hover,
    .right-column::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
    
    /* サイドバーのスタイル調整 */
    .css-1d391kg {
        padding-top: 1rem;
    }
    
    /* サイドバーのロゴスタイル */
    [data-testid="stSidebar"] h1 {
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
</style>
"""


def get_custom_css() -> str:
    """
    カスタムCSSを取得
    
    Returns:
        CSS文字列
    """
    return CUSTOM_CSS

