"""
XBRL解析モジュール

インラインXBRL（HTML形式）からセクションを抽出します。
"""

import logging
from typing import Optional
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logging.warning("beautifulsoup4がインストールされていません。XBRL解析機能は使用できません。")

logger = logging.getLogger(__name__)


class XBRLParser:
    """XBRL解析クラス"""
    
    def __init__(self):
        """初期化"""
        if not BS4_AVAILABLE:
            logger.warning("beautifulsoup4がインストールされていません。")
    
    def _find_section(self, soup: BeautifulSoup, section_title: str) -> Optional[str]:
        """
        セクションを検索してテキストを抽出

        Args:
            soup: BeautifulSoupオブジェクト
            section_title: セクションタイトル（部分一致）

        Returns:
            セクションテキスト（見つからない場合はNone）
        """
        if not BS4_AVAILABLE:
            return None
        
        # セクションタイトルを含む要素を検索
        # 有価証券報告書の構造に応じて検索パターンを調整
        
        # パターン1: 見出しタグ（h1-h6）で検索
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            if section_title in heading.get_text():
                # 次の見出しまでを取得
                content = []
                current = heading.next_sibling
                while current:
                    if current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        # 次の見出しが見つかったら終了
                        break
                    if hasattr(current, 'get_text'):
                        text = current.get_text(strip=True)
                        if text:
                            content.append(text)
                    elif isinstance(current, str):
                        text = current.strip()
                        if text:
                            content.append(text)
                    current = current.next_sibling
                
                if content:
                    return "\n".join(content)
        
        # パターン2: divやpタグ内で検索
        elements = soup.find_all(['div', 'p', 'section'])
        for elem in elements:
            text = elem.get_text()
            if section_title in text:
                # セクションタイトルを含む要素のテキストを取得
                return elem.get_text(separator="\n", strip=True)
        
        return None
    
    def extract_section(
        self,
        xbrl_dir: Path,
        section_name: str
    ) -> Optional[str]:
        """
        XBRLディレクトリから指定セクションを抽出

        Args:
            xbrl_dir: XBRL展開ディレクトリのパス
            section_name: セクション名（例: "経営方針、経営環境及び対処すべき課題等"）

        Returns:
            セクションテキスト（見つからない場合はNone）
        """
        if not BS4_AVAILABLE:
            logger.warning("beautifulsoup4がインストールされていないため、XBRL解析をスキップします。")
            return None
        
        if not xbrl_dir.exists() or not xbrl_dir.is_dir():
            logger.warning(f"XBRLディレクトリが存在しません: {xbrl_dir}")
            return None
        
        # インラインXBRLファイルを検索（通常はPublicDocディレクトリ内）
        public_doc_dir = xbrl_dir / "PublicDoc"
        if not public_doc_dir.exists():
            # PublicDocがない場合は、xbrl_dir直下を検索
            public_doc_dir = xbrl_dir
        
        # HTMLファイルを検索
        html_files = list(public_doc_dir.glob("*.html")) + list(public_doc_dir.glob("*.htm"))
        
        if not html_files:
            logger.warning(f"HTMLファイルが見つかりませんでした: {xbrl_dir}")
            return None
        
        # 最初のHTMLファイルを解析
        html_file = html_files[0]
        
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            soup = BeautifulSoup(content, "lxml")
            
            # セクションを検索
            section_text = self._find_section(soup, section_name)
            
            if section_text:
                # テキスト整形
                # HTMLタグ除去、余分な空白・改行削除
                lines = section_text.split("\n")
                cleaned_lines = []
                for line in lines:
                    line = line.strip()
                    if line:
                        cleaned_lines.append(line)
                
                result = "\n".join(cleaned_lines)
                
                # 長すぎる場合は切り詰め（10,000文字まで）
                if len(result) > 10000:
                    result = result[:10000] + "..."
                
                logger.info(f"セクション抽出成功: {section_name} ({len(result)}文字)")
                return result
            else:
                logger.warning(f"セクションが見つかりませんでした: {section_name}")
                return None
        
        except Exception as e:
            logger.error(f"XBRL解析エラー: {html_file} - {e}")
            return None
    
    def extract_mda(self, xbrl_dir: Path) -> Optional[str]:
        """
        経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析（MD&A）を抽出

        Args:
            xbrl_dir: XBRL展開ディレクトリのパス

        Returns:
            MD&Aテキスト
        """
        return self.extract_section(
            xbrl_dir,
            "経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析"
        )
    
    def extract_management_policy(self, xbrl_dir: Path) -> Optional[str]:
        """
        経営方針、経営環境及び対処すべき課題等を抽出

        Args:
            xbrl_dir: XBRL展開ディレクトリのパス

        Returns:
            経営方針テキスト
        """
        return self.extract_section(
            xbrl_dir,
            "経営方針、経営環境及び対処すべき課題等"
        )

