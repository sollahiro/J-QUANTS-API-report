"""
XBRL解析モジュール

インラインXBRL（HTML形式）からセクションを抽出します。
XBRLインスタンス文書（XML形式）からテキストブロックを抽出します。
"""

import logging
import re
import html
from typing import Optional, Dict, List
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logging.warning("beautifulsoup4がインストールされていません。XBRL解析機能は使用できません。")

try:
    import xml.etree.ElementTree as ET
    ET_AVAILABLE = True
except ImportError:
    ET_AVAILABLE = False
    logging.warning("xml.etree.ElementTreeが利用できません。XBRL解析機能は使用できません。")

logger = logging.getLogger(__name__)


class XBRLParser:
    """XBRL解析クラス"""
    
    # 共通セクション定義（有価証券報告書・中間報告書共通）
    COMMON_SECTIONS = {
        'A': {
            'title': '事業の内容',
            'keywords': ['事業の内容', 'DescriptionOfBusiness'],
            'xbrl_elements': ['DescriptionOfBusinessTextBlock']
        },
        'B': {
            'title': '経営方針、経営環境及び対処すべき課題等',
            'keywords': ['経営方針', '経営環境', '対処すべき課題', 'BusinessPolicy'],
            'xbrl_elements': ['BusinessPolicyTextBlock']
        },
        'C': {
            'title': '事業等のリスク',
            'keywords': ['事業等のリスク', 'BusinessRisks'],
            'xbrl_elements': ['BusinessRisksTextBlock']
        },
        'D': {
            'title': '経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析',
            'keywords': ['経営者による', '財政状態', '経営成績', 'キャッシュ・フロー', 'ManagementAnalysis'],
            'xbrl_elements': ['ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock']
        },
        'E': {
            'title': '重要な契約等',
            'keywords': ['重要な契約', 'ImportantContracts'],
            'xbrl_elements': ['ImportantContractsTextBlock']
        },
        'F': {
            'title': '設備投資等の概要',
            'keywords': ['設備投資', '設備投資等の概要', 'CapitalInvestment'],
            'xbrl_elements': ['OverviewOfCapitalInvestmentTextBlock']
        }
    }
    
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
                    # 次の見出しが見つかったら終了
                    # currentがTagオブジェクトの場合のみname属性にアクセス
                    try:
                        # BeautifulSoupのTagオブジェクトの場合
                        if hasattr(current, 'name') and hasattr(current, 'get_text'):
                            if getattr(current, 'name', None) in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                                break
                            text = current.get_text(strip=True)
                            if text:
                                content.append(text)
                        elif isinstance(current, str):
                            text = current.strip()
                            if text:
                                content.append(text)
                    except (AttributeError, TypeError):
                        # 属性アクセスエラーの場合はスキップ
                        pass
                    
                    # next_siblingが存在する場合のみ取得（NavigableStringやTagオブジェクトの場合）
                    try:
                        if hasattr(current, 'next_sibling'):
                            current = current.next_sibling  # type: ignore
                        else:
                            break
                    except (AttributeError, TypeError):
                        break
                
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
    
    def _detect_report_type(self, xbrl_dir: Path) -> str:
        """
        報告書タイプを判定
        
        Args:
            xbrl_dir: XBRL展開ディレクトリのパス
            
        Returns:
            'annual' (有価証券報告書) または 'interim' (半期報告書)
        """
        # XBRLインスタンス文書を検索
        xml_files = []
        for xml_file in xbrl_dir.rglob("*.xml"):
            if any(suffix in xml_file.name for suffix in ['_lab.xml', '_pre.xml', '_cal.xml', '_def.xml']):
                continue
            xml_files.append(xml_file)
        
        xbrl_files = list(xbrl_dir.rglob("*.xbrl"))
        xml_files.extend(xbrl_files)
        
        # ファイル名から判定
        for xml_file in xml_files:
            filename = xml_file.name.lower()
            # 有価証券報告書: jpcrp040300
            if 'jpcrp040300' in filename or '040300' in filename:
                return 'annual'
            # 半期報告書: jpcrp030300
            if 'jpcrp030300' in filename or '030300' in filename:
                return 'interim'
        
        # XMLファイルの内容から判定
        for xml_file in xml_files[:5]:  # 最初の5ファイルをチェック
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # DocumentType要素を検索
                for elem in root.iter():
                    tag = elem.tag
                    if '}' in tag:
                        tag = tag.split('}')[1]
                    
                    if 'DocumentType' in tag or 'documentType' in tag:
                        text = elem.text
                        if text:
                            text_lower = text.lower()
                            if '有価証券報告書' in text or 'annual' in text_lower or '040300' in text:
                                return 'annual'
                            if '半期報告書' in text or 'interim' in text_lower or 'quarterly' in text_lower or '030300' in text:
                                return 'interim'
            except Exception:
                continue
        
        # デフォルトは有価証券報告書
        logger.warning(f"報告書タイプを判定できませんでした。デフォルトで有価証券報告書として処理します: {xbrl_dir}")
        return 'annual'
    
    def extract_sections_by_type(
        self, 
        xbrl_dir: Path, 
        report_type: Optional[str] = None
    ) -> Dict[str, str]:
        """
        共通ロジックでセクションを抽出（報告書タイプに関係なく）
        
        Args:
            xbrl_dir: XBRL展開ディレクトリのパス
            report_type: 未使用（互換性のため残す）
            
        Returns:
            {セクションID: テキスト} の辞書（見つからない場合は空文字列）
        """
        if not ET_AVAILABLE:
            logger.warning("xml.etree.ElementTreeが利用できないため、XBRLテキスト抽出をスキップします。")
            return {}
        
        if not xbrl_dir.exists() or not xbrl_dir.is_dir():
            logger.warning(f"XBRLディレクトリが存在しません: {xbrl_dir}")
            return {}
        
        # 共通セクション定義を使用
        sections = self.COMMON_SECTIONS
        logger.info(f"抽出対象セクション数: {len(sections)}")
        
        # XBRLインスタンス文書を検索
        xml_files = []
        for xml_file in xbrl_dir.rglob("*.xml"):
            if any(suffix in xml_file.name for suffix in ['_lab.xml', '_pre.xml', '_cal.xml', '_def.xml']):
                continue
            xml_files.append(xml_file)
        
        xbrl_files = list(xbrl_dir.rglob("*.xbrl"))
        xml_files.extend(xbrl_files)
        
        if not xml_files:
            logger.warning(f"XBRLインスタンス文書が見つかりません: {xbrl_dir}")
            return {}
        
        # 全てのテキストブロック要素を抽出（要素名ベース）
        all_text_blocks = {}
        namespaces = {}
        
        for xml_file in xml_files:
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # 名前空間を登録
                for prefix, uri in root.attrib.items():
                    if prefix.startswith('xmlns'):
                        if prefix == 'xmlns':
                            namespaces[''] = uri
                        else:
                            ns_prefix = prefix.replace('xmlns:', '')
                            namespaces[ns_prefix] = uri
                
                # 全ての要素を走査してテキストブロックを検索
                for elem in root.iter():
                    tag = elem.tag
                    # 名前空間を除去
                    if '}' in tag:
                        local_tag = tag.split('}')[1]
                    else:
                        local_tag = tag
                    
                    # TextBlockで終わる要素を検索
                    if local_tag.endswith('TextBlock') or 'TextBlock' in local_tag:
                        # 要素のテキストを取得
                        text = self._extract_text_from_html_element_simple(elem)
                        if text and len(text) > 50:
                            # 要素名をキーとして保存
                            all_text_blocks[local_tag] = text
                            
            except ET.ParseError as e:
                logger.warning(f"XMLパースエラー: {xml_file.name} - {e}")
                continue
            except Exception as e:
                logger.error(f"XBRLテキスト抽出エラー: {xml_file.name} - {e}", exc_info=True)
                continue
        
        # セクション定義に基づいて抽出
        result = {}
        for section_id, section_def in sections.items():
            section_text = None
            
            # 方法1: 要素名で検索（完全一致または部分一致）
            target_elements = section_def.get('xbrl_elements', [])
            for xbrl_element in target_elements:
                for block_name, block_text in all_text_blocks.items():
                    if xbrl_element in block_name or block_name.endswith(xbrl_element):
                        section_text = block_text
                        logger.debug(f"セクション {section_id} ({section_def['title']}) を要素名で発見: {block_name}")
                        break
                if section_text:
                    break
            
            # 方法2: 大きなTextBlockからサブセクションを抽出
            if not section_text:
                # ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlockから抽出
                mda_block = all_text_blocks.get('ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock')
                if mda_block:
                    # セクションIDに応じた抽出パターン
                    if section_id == 'B':  # 経営方針、経営環境及び対処すべき課題等
                        # まず、項目名のフレーズを探す
                        normalized_mda = self._normalize_text(mda_block)
                        title_patterns = [
                            '経営方針、経営環境及び対処すべき課題等',
                            '【経営方針、経営環境及び対処すべき課題等】',
                            '経営方針、経営環境及び対処すべき課題等】'
                        ]
                        
                        title_start_idx = None
                        for pattern in title_patterns:
                            idx = normalized_mda.find(pattern)
                            if idx != -1:
                                title_start_idx = idx
                                break
                        
                        # （３）経営方針 から （５）研究開発 までを抽出（（４）対処すべき課題も含む）
                        extracted = self._extract_subsection_from_text(
                            mda_block,
                            start_patterns=['（３）経営方針', '（3）経営方針', '（３） 経営方針', '（3） 経営方針'],
                            end_patterns=['（５）研究開発', '（5）研究開発', '（５） 研究開発', '（5） 研究開発']
                        )
                        if extracted:
                            # 項目名のフレーズが見つかった場合は、その位置から抽出
                            if title_start_idx is not None:
                                # 項目名のフレーズから（３）経営方針までの部分も含める
                                lines = normalized_mda.split('\n')
                                title_line_idx = None
                                for i, line in enumerate(lines):
                                    if any(pattern in line for pattern in title_patterns):
                                        title_line_idx = i
                                        break
                                
                                if title_line_idx is not None:
                                    # （３）経営方針の行を探す
                                    policy_line_idx = None
                                    for i, line in enumerate(lines):
                                        if '（３）経営方針' in line or '（3）経営方針' in line:
                                            policy_line_idx = i
                                            break
                                    
                                    if policy_line_idx is not None and policy_line_idx > title_line_idx:
                                        # 項目名のフレーズから（３）経営方針までの部分を取得
                                        title_section = '\n'.join(lines[title_line_idx:policy_line_idx]).strip()
                                        # 抽出したテキストと結合
                                        section_text = title_section + ' ' + extracted
                                    else:
                                        section_text = section_def['title'] + ' ' + extracted
                                else:
                                    section_text = section_def['title'] + ' ' + extracted
                            else:
                                # 項目名のフレーズが見つからない場合は、項目名を先頭に追加
                                section_text = section_def['title'] + ' ' + extracted
                            logger.debug(f"セクション {section_id} ({section_def['title']}) をManagementAnalysisから抽出: {len(section_text)}文字")
                    
                    elif section_id == 'F':  # 設備投資等の概要
                        extracted = self._extract_subsection_from_text(
                            mda_block,
                            start_patterns=['（６）設備', '（6）設備', '（６） 設備', '（6） 設備', '（７）設備', '（7）設備', '（７） 設備', '（7） 設備'],
                            end_patterns=['（８）将来予想', '（8）将来予想', '（８） 将来予想', '（8） 将来予想']
                        )
                        if extracted:
                            section_text = extracted
                            logger.debug(f"セクション {section_id} ({section_def['title']}) をManagementAnalysisから抽出: {len(section_text)}文字")
            
            # 方法4: キーワードで検索（フォールバック）
            # 完全な項目名のフレーズで検索（簡略化されたキーワードは使用しない）
            if not section_text:
                section_title = section_def.get('title', '')
                
                for block_name, block_text in all_text_blocks.items():
                    # XBRL要素名をチェック（英語の要素名）
                    xbrl_elements = section_def.get('xbrl_elements', [])
                    element_found = False
                    for element in xbrl_elements:
                        if element in block_name or block_name.endswith(element):
                            element_found = True
                            break
                    
                    # 完全な項目名のフレーズで検索（様々なパターン）
                    title_patterns = [
                        section_title,  # 完全一致
                        f'【{section_title}】',  # 【項目名】
                        f'{section_title}】',  # 項目名】
                        f'【{section_title}',  # 【項目名
                    ]
                    
                    # 完全な項目名のフレーズまたはXBRL要素名が見つかった場合
                    if element_found or any(pattern in block_text[:500] for pattern in title_patterns):
                        section_text = block_text
                        logger.debug(f"セクション {section_id} ({section_def['title']}) を完全な項目名で発見")
                        break
            
            if section_text:
                # 項目名のフレーズで始まるように調整
                section_text = self._ensure_starts_with_section_title(section_text, section_def['title'])
                result[section_id] = section_text
                logger.info(f"セクション {section_id} ({section_def['title']}) 抽出成功: {len(section_text)}文字")
            else:
                logger.debug(f"セクション {section_id} ({section_def['title']}) が見つかりませんでした（空文字列を返します）")
                result[section_id] = ""
        
        return result
    
    def _ensure_starts_with_section_title(self, text: str, section_title: str) -> str:
        """
        抽出したテキストが項目名のフレーズで始まるように調整
        
        Args:
            text: 抽出されたテキスト
            section_title: セクションのタイトル（項目名）
            
        Returns:
            項目名のフレーズで始まるように調整されたテキスト
        """
        # 既に項目名で始まっている場合はそのまま返す
        if text.strip().startswith(section_title):
            return text.strip()
        
        # 項目名のフレーズを探す（様々なパターン）
        patterns = [
            f'【{section_title}】',  # 【項目名】
            f'{section_title}】',  # 項目名】
            f'【{section_title}',  # 【項目名
            section_title,  # 完全一致
        ]
        
        # テキスト内で項目名のフレーズを探す
        best_match = None
        best_idx = len(text)
        
        for pattern in patterns:
            idx = text.find(pattern)
            if idx != -1 and idx < best_idx:
                best_match = pattern
                best_idx = idx
        
        if best_match is not None:
            # 項目名のフレーズが見つかった位置から開始
            adjusted_text = text[best_idx:]
            
            # 項目名のフレーズの前にある数字や記号を除去
            # 例：「２【事業の内容】」→「事業の内容」で始まるように
            # 例：「事業の内容】」→「事業の内容」で始まるように
            if adjusted_text.startswith('【'):
                # 【項目名】の場合
                if adjusted_text.startswith(f'【{section_title}】'):
                    adjusted_text = adjusted_text[len(f'【{section_title}】'):].lstrip()
                    adjusted_text = section_title + (' ' if adjusted_text else '') + adjusted_text
                elif adjusted_text.startswith(f'【{section_title}'):
                    # 【項目名 の場合
                    end_idx = adjusted_text.find('】')
                    if end_idx != -1:
                        adjusted_text = adjusted_text[end_idx + 1:].lstrip()
                        adjusted_text = section_title + (' ' if adjusted_text else '') + adjusted_text
            elif adjusted_text.startswith(f'{section_title}】'):
                # 項目名】の場合
                adjusted_text = adjusted_text[len(f'{section_title}】'):].lstrip()
                adjusted_text = section_title + (' ' if adjusted_text else '') + adjusted_text
            elif not adjusted_text.startswith(section_title):
                # 項目名で始まっていない場合、項目名を探してその位置から開始
                title_idx = adjusted_text.find(section_title)
                if title_idx != -1:
                    # 項目名の前の部分を除去
                    adjusted_text = adjusted_text[title_idx:]
                    # 項目名の後に】がある場合は除去
                    if adjusted_text.startswith(section_title + '】'):
                        adjusted_text = adjusted_text[len(section_title + '】'):].lstrip()
                        adjusted_text = section_title + (' ' if adjusted_text else '') + adjusted_text
                    elif adjusted_text.startswith(section_title):
                        # 項目名の直後にスペースがない場合は追加
                        if len(adjusted_text) > len(section_title) and adjusted_text[len(section_title)] not in [' ', '　', '】', '】']:
                            adjusted_text = section_title + ' ' + adjusted_text[len(section_title):].lstrip()
            
            return adjusted_text.strip()
        
        # 項目名のフレーズが見つからない場合は、項目名を先頭に追加
        return section_title + ' ' + text.strip()
    
    def _normalize_text(self, text: str) -> str:
        """
        テキストを整形して見出しを識別しやすくする
        
        Args:
            text: 整形前のテキスト
            
        Returns:
            整形後のテキスト
        """
        # 見出しパターンの前に改行を挿入
        # パターン1: （数字）見出し
        text = re.sub(r'（([０-９0-9]+)）([^）\n]+)', r'\n（\1）\2', text)
        # パターン2: 数字【見出し】
        text = re.sub(r'([０-９0-9]+)【([^】]+)】', r'\n\1【\2】', text)
        # パターン3: 【見出し】
        text = re.sub(r'【([^】]+)】', r'\n【\1】', text)
        # パターン4: 注数字．見出し
        text = re.sub(r'注([０-９0-9]+)\.', r'\n注\1.', text)
        
        # 余分な改行を整理（3行以上連続する改行を2行に）
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def _extract_subsection_from_text(self, text: str, start_patterns: List[str], end_patterns: List[str]) -> Optional[str]:
        """
        テキストからサブセクションを抽出
        
        Args:
            text: 抽出元のテキスト
            start_patterns: 開始パターンのリスト
            end_patterns: 終了パターンのリスト
            
        Returns:
            抽出されたサブセクションのテキスト
        """
        # テキストを整形
        normalized_text = self._normalize_text(text)
        
        # 改行で分割
        lines = normalized_text.split('\n')
        
        start_idx = None
        end_idx = None
        
        # 開始パターンを検索
        for i, line in enumerate(lines):
            for pattern in start_patterns:
                if pattern in line:
                    start_idx = i
                    break
            if start_idx is not None:
                break
        
        if start_idx is None:
            return None
        
        # 終了パターンを検索（開始位置以降）
        for i in range(start_idx + 1, len(lines)):
            for pattern in end_patterns:
                if pattern in lines[i]:
                    end_idx = i
                    break
            if end_idx is not None:
                break
        
        # 終了パターンが見つからない場合は、次の主要な見出しまで（最大1000行）
        if end_idx is None:
            end_idx = min(start_idx + 1000, len(lines))
        
        # セクションを抽出
        extracted_lines = lines[start_idx:end_idx]
        extracted_text = '\n'.join(extracted_lines).strip()
        
        return extracted_text if extracted_text else None
    
    def _extract_text_from_html_element_simple(self, element: ET.Element) -> str:
        """HTMLタグを含む要素からテキストを抽出（テーブル判定なし）"""
        # 要素のテキストを取得
        text_parts = []
        
        # 要素の直接のテキスト
        if element.text:
            text = element.text.strip()
            if text:
                text_parts.append(text)
        
        # 子要素からテキストを再帰的に抽出
        for child in element:
            child_text = self._extract_text_from_html_element_simple(child)
            if child_text:
                text_parts.append(child_text)
            
            # 子要素の後のテキスト（tail）
            if child.tail:
                tail_text = child.tail.strip()
                if tail_text:
                    text_parts.append(tail_text)
        
        combined_text = '\n'.join(text_parts)
        
        # HTMLエンティティをデコード
        combined_text = html.unescape(combined_text)
        
        # HTMLタグを除去（正規表現で）
        combined_text = re.sub(r'<[^>]+>', '', combined_text)
        
        # 余分な空白を整理
        combined_text = re.sub(r'\s+', ' ', combined_text)
        combined_text = combined_text.strip()
        
        return combined_text
    
    def extract_text_from_xbrl(self, xbrl_dir: Path, exclude_tables: bool = False) -> str:
        """
        XBRLディレクトリからテキストブロックを抽出（後方互換性のためのメソッド）
        
        注意: このメソッドは後方互換性のために残されています。
        新しいコードでは extract_sections_by_type を使用してください。
        
        Args:
            xbrl_dir: XBRLが展開されたディレクトリ
            exclude_tables: 表を除外するかどうか（現在は無視されます）
            
        Returns:
            抽出されたテキスト（全セクションを結合）
        """
        # 新しいメソッドを使用してセクションを抽出
        sections = self.extract_sections_by_type(xbrl_dir)
        
        # セクションを順序付きで結合（A→B→C...の順）
        section_order = sorted(sections.keys())
        combined_texts = []
        for section_id in section_order:
            text = sections[section_id]
            if text:
                combined_texts.append(text)
        
        return '\n\n'.join(combined_texts)
    

