"""
PDF解析モジュール

有価証券報告書のPDFからセクションを抽出します。
"""

import logging
from typing import Optional
from pathlib import Path

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logging.warning("pdfplumberがインストールされていません。PDF解析機能は使用できません。")

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF解析クラス"""
    
    def __init__(self):
        """初期化"""
        if not PDFPLUMBER_AVAILABLE:
            logger.warning("pdfplumberがインストールされていません。")
    
    def _find_section(self, text: str, section_title: str) -> Optional[str]:
        """
        セクションを検索してテキストを抽出

        Args:
            text: PDFから抽出したテキスト
            section_title: セクションタイトル（部分一致）

        Returns:
            セクションテキスト（見つからない場合はNone）
        """
        if not PDFPLUMBER_AVAILABLE:
            return None
        
        # セクションタイトルを含む行を検索
        lines = text.split('\n')
        section_start = None
        
        for i, line in enumerate(lines):
            if section_title in line:
                section_start = i
                break
        
        if section_start is None:
            return None
        
        # セクションの終了を検出（次の主要な見出しまで）
        # 有価証券報告書の構造に応じて調整
        section_end = None
        next_section_keywords = [
            "経営者による財政状態",
            "経営方針、経営環境",
            "事業の内容",
            "財務諸表",
            "監査報告書",
            "第",  # 次の章番号
        ]
        
        for i in range(section_start + 1, len(lines)):
            line = lines[i].strip()
            # 次のセクションが見つかったら終了
            if any(keyword in line for keyword in next_section_keywords):
                # 現在のセクションタイトルと異なる場合のみ終了
                if section_title not in line:
                    section_end = i
                    break
        
        # セクション終了が見つからない場合は、次の100行まで
        if section_end is None:
            section_end = min(section_start + 100, len(lines))
        
        # セクションテキストを抽出
        section_lines = lines[section_start:section_end]
        section_text = '\n'.join(section_lines)
        
        # テキスト整形
        # 余分な空白・改行を削除
        cleaned_lines = []
        for line in section_text.split('\n'):
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        
        # 長すぎる場合は切り詰め（10,000文字まで）
        if len(result) > 10000:
            result = result[:10000] + "..."
        
        return result if result else None
    
    def extract_section(
        self,
        pdf_path: Path,
        section_name: str
    ) -> Optional[str]:
        """
        PDFから指定セクションを抽出

        Args:
            pdf_path: PDFファイルのパス
            section_name: セクション名（例: "経営方針、経営環境及び対処すべき課題等"）

        Returns:
            セクションテキスト（見つからない場合はNone）
        """
        if not PDFPLUMBER_AVAILABLE:
            logger.warning("pdfplumberがインストールされていないため、PDF解析をスキップします。")
            return None
        
        if not pdf_path.exists() or not pdf_path.is_file():
            logger.warning(f"PDFファイルが存在しません: {pdf_path}")
            return None
        
        try:
            # PDFからテキストを抽出
            full_text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"
            
            if not full_text:
                logger.warning(f"PDFからテキストを抽出できませんでした: {pdf_path}")
                return None
            
            # セクションを検索
            section_text = self._find_section(full_text, section_name)
            
            if section_text:
                logger.info(f"セクション抽出成功: {section_name} ({len(section_text)}文字)")
                return section_text
            else:
                logger.warning(f"セクションが見つかりませんでした: {section_name}")
                return None
        
        except Exception as e:
            logger.error(f"PDF解析エラー: {pdf_path} - {e}")
            return None
    
    def extract_mda(self, pdf_path: Path) -> Optional[str]:
        """
        経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析（MD&A）を抽出

        Args:
            pdf_path: PDFファイルのパス

        Returns:
            MD&Aテキスト
        """
        return self.extract_section(
            pdf_path,
            "経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析"
        )
    
    def extract_management_policy(self, pdf_path: Path) -> Optional[str]:
        """
        経営方針、経営環境及び対処すべき課題等を抽出

        Args:
            pdf_path: PDFファイルのパス

        Returns:
            経営方針テキスト
        """
        return self.extract_section(
            pdf_path,
            "経営方針、経営環境及び対処すべき課題等"
        )

