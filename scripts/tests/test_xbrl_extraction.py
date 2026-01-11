"""
XBRLからテキストを抽出するテストスクリプト

EDINETからXBRLを取得し、テキストを抽出して表形式データを除外します。
"""

import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Set

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.api.edinet_client import EdinetAPIClient
from src.api.client import JQuantsAPIClient
from src.config import config


class XBRLParser:
    """XBRLからテキストを抽出するパーサー"""
    
    # 表タグのパターン（除外対象）
    TABLE_TAGS = {
        'table', 'table:table', 'table:tableGroup', 'table:tableModel',
        'table:tableHeader', 'table:tableBody', 'table:tableFooter',
        'table:tableRow', 'table:tableCell', 'table:tableContent',
        'ix:table', 'ix:tableGroup', 'ix:tableHeader', 'ix:tableBody',
        'ix:tableRow', 'ix:tableCell'
    }
    
    # テキストを含む可能性のあるタグ
    TEXT_TAGS = {
        'p', 'paragraph', 'text', 'content', 'description',
        'note', 'footnote', 'narrative', 'textBlock',
        'ix:nonNumeric', 'ix:nonFraction', 'ix:text',
        'jpcrp_cor:BusinessPolicyTextBlock',
        'jpcrp_cor:BusinessRisksTextBlock',
        'jpcrp_cor:BusinessResultsOfOperationsTextBlock',
        'jpcrp_cor:ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock',
        'jpcrp_cor:BasicPolicyRegardingProfitDistributionAndReturnOfSurplusTextBlock',
    }
    
    def __init__(self):
        """初期化"""
        self.namespaces = {}
    
    def _register_namespaces(self, root: ET.Element):
        """XML名前空間を登録"""
        for prefix, uri in root.attrib.items():
            if prefix.startswith('xmlns'):
                if prefix == 'xmlns':
                    self.namespaces[''] = uri
                else:
                    ns_prefix = prefix.replace('xmlns:', '')
                    self.namespaces[ns_prefix] = uri
    
    def _extract_text_from_html(self, element: ET.Element) -> str:
        """HTMLタグを含む要素からテキストを抽出（表を除外）"""
        import html
        
        # 要素のテキストを取得
        text_parts = []
        
        # 要素の直接のテキスト
        if element.text:
            text = element.text.strip()
            if text:
                text_parts.append(text)
        
        # 子要素からテキストを再帰的に抽出
        for child in element:
            # 表要素の場合はスキップ
            if self._is_table_element(child):
                continue
            
            child_text = self._extract_text_from_html(child)
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
    
    def _is_table_element(self, element: ET.Element) -> bool:
        """要素が表要素かどうかを判定"""
        tag = element.tag
        # 名前空間を除去したタグ名を取得
        if '}' in tag:
            tag = tag.split('}')[1]
        
        # 表タグかどうかチェック
        if tag in self.TABLE_TAGS:
            return True
        
        # 属性で判定
        if element.get('class') and 'table' in element.get('class', '').lower():
            return True
        
        return False
    
    def _is_text_block(self, element: ET.Element) -> bool:
        """要素がテキストブロックかどうかを判定"""
        tag = element.tag
        # 名前空間を除去したタグ名を取得
        if '}' in tag:
            tag = tag.split('}')[1]
        
        # TextBlockで終わるタグはテキストブロック
        if tag.endswith('TextBlock') or 'TextBlock' in tag:
            return True
        
        # 特定のテキストブロックタグをチェック
        text_block_patterns = [
            'BusinessPolicyTextBlock',
            'BusinessRisksTextBlock',
            'BusinessResultsOfOperationsTextBlock',
            'ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock',
            'BasicPolicyRegardingProfitDistributionAndReturnOfSurplusTextBlock',
            'DescriptionOfBusinessTextBlock',
            'OverviewOfBusinessResultsTextBlock',
            'AnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock',
        ]
        
        for pattern in text_block_patterns:
            if pattern in tag:
                return True
        
        return False
    
    def _extract_text_from_element(self, element: ET.Element, exclude_tables: bool = True, in_text_block: bool = False) -> str:
        """要素からテキストを抽出（表を除外）"""
        # 表要素の場合は空文字列を返す
        if exclude_tables and self._is_table_element(element):
            return ""
        
        # テキストブロックの開始を検出
        is_text_block = self._is_text_block(element)
        if is_text_block:
            in_text_block = True
        
        texts = []
        
        # テキストブロック内の場合、またはテキストブロック要素自体の場合
        if in_text_block or is_text_block:
            # 要素の直接のテキスト
            if element.text:
                text = element.text.strip()
                if text and len(text) > 10:  # 短すぎるテキストは除外
                    texts.append(text)
        
        # 子要素からテキストを再帰的に抽出
        for child in element:
            child_text = self._extract_text_from_element(child, exclude_tables, in_text_block)
            if child_text:
                texts.append(child_text)
            
            # 子要素の後のテキスト（tail）
            if child.tail and (in_text_block or is_text_block):
                tail_text = child.tail.strip()
                if tail_text and len(tail_text) > 10:
                    texts.append(tail_text)
        
        return '\n'.join(texts)
    
    def extract_text_from_xbrl(self, xbrl_dir: Path, exclude_tables: bool = True) -> str:
        """
        XBRLディレクトリからテキストを抽出
        
        Args:
            xbrl_dir: XBRLが展開されたディレクトリ
            exclude_tables: 表を除外するかどうか
            
        Returns:
            抽出されたテキスト
        """
        all_texts = []
        
        # XBRLインスタンス文書を検索（.xbrlファイル、またはlab/pre/cal/def以外のXMLファイル）
        xml_files = []
        for xml_file in xbrl_dir.rglob("*.xml"):
            # ラベル、プレゼンテーション、計算、定義ファイルは除外
            if any(suffix in xml_file.name for suffix in ['_lab.xml', '_pre.xml', '_cal.xml', '_def.xml']):
                continue
            xml_files.append(xml_file)
        
        # .xbrlファイルも検索
        xbrl_files = list(xbrl_dir.rglob("*.xbrl"))
        xml_files.extend(xbrl_files)
        
        if not xml_files:
            print(f"⚠️ XBRLインスタンス文書が見つかりません: {xbrl_dir}")
            return ""
        
        print(f"📄 {len(xml_files)}個のXBRLインスタンス文書を処理中...")
        
        for xml_file in xml_files:
            try:
                # XMLファイルをパース
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # 名前空間を登録
                self._register_namespaces(root)
                
                # テキストブロック要素を検索（TextBlockで終わる要素）
                text_blocks = []
                
                # 全ての要素を走査してテキストブロックを検索
                for elem in root.iter():
                    tag = elem.tag
                    # 名前空間を除去
                    if '}' in tag:
                        tag = tag.split('}')[1]
                    
                    # TextBlockで終わる要素を検索
                    if tag.endswith('TextBlock') or 'TextBlock' in tag:
                        # 要素のテキストを取得（HTMLタグを除去）
                        text = self._extract_text_from_html(elem)
                        if text and len(text) > 50:  # 50文字以上のテキストブロックのみ
                            text_blocks.append(text)
                
                if text_blocks:
                    combined_text = '\n\n'.join(text_blocks)
                    all_texts.append(combined_text)
                    print(f"  ✅ {xml_file.name}: {len(combined_text)}文字 ({len(text_blocks)}個のテキストブロック)")
                else:
                    print(f"  ⚠️ {xml_file.name}: テキストブロックが見つかりませんでした")
            
            except ET.ParseError as e:
                print(f"  ⚠️ XMLパースエラー: {xml_file.name} - {e}")
                continue
            except Exception as e:
                print(f"  ⚠️ エラー: {xml_file.name} - {e}")
                continue
        
        combined_text = '\n\n'.join(all_texts)
        
        # 表形式データを除外（正規表現ベース）
        if exclude_tables:
            combined_text = self._filter_table_data(combined_text)
        
        return combined_text
    
    def _filter_table_data(self, text: str) -> str:
        """
        表形式のデータを除外（正規表現ベース）
        
        Args:
            text: 元のテキスト
            
        Returns:
            表形式データを除外したテキスト
        """
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 1. 短すぎる行を除外（ただし見出しは残す）
            if len(line) <= 3 and not any(keyword in line for keyword in ["【", "】", "①", "②", "③", "④", "第"]):
                continue
            
            # 2. 数値のみ、または数値が過度に多い行を除外
            numbers = re.findall(r'[\d,，]+', line)
            number_chars = sum(len(num) for num in numbers)
            actual_chars = len(re.sub(r'[\s,，\s]', '', line))
            if actual_chars > 0:
                number_ratio = number_chars / actual_chars
                if number_ratio > 0.4:
                    continue
            
            # 3. 数値の羅列パターンを除外
            number_sequences = re.findall(r'[\d,，]+(?:\s+[\d,，]+){2,}', line)
            if number_sequences:
                non_number_chars = len(re.sub(r'[\d,，\s]', '', line))
                if non_number_chars < 20:
                    continue
            
            # 4. 単位のみの行を除外
            if re.match(r'^[（(]?単位[：:：]?[）)]?', line):
                continue
            
            # 5. 日付のみの行を除外
            if re.match(r'^\d{4}年\d{1,2}月\d{1,2}日', line):
                continue
            
            filtered_lines.append(line)
        
        # 重複する行を除去
        seen = set()
        unique_lines = []
        for line in filtered_lines:
            normalized = re.sub(r'\s+', ' ', line.strip())
            if normalized and normalized not in seen and len(normalized) > 3:
                seen.add(normalized)
                unique_lines.append(line)
        
        return '\n'.join(unique_lines)


def main():
    """メイン処理"""
    code = "4689"  # テスト対象の銘柄コード
    
    print(f"=" * 60)
    print(f"XBRLテキスト抽出テスト - 銘柄コード: {code}")
    print(f"=" * 60)
    print()
    
    # 1. EDINETクライアントを初期化
    print("1. EDINETクライアントを初期化中...")
    edinet_client = EdinetAPIClient()
    
    if not edinet_client.api_key:
        print("❌ EDINET_API_KEYが設定されていません。")
        return
    
    print("   ✅ EDINETクライアントの初期化に成功しました\n")
    
    # 2. 書類を検索
    print("2. EDINETから書類を検索中...")
    from datetime import datetime
    current_year = datetime.now().year
    years_to_search = [current_year - i for i in range(5)]
    
    # search_documentsメソッドを使用
    documents = edinet_client.search_documents(
        code=code,
        years=years_to_search,
        doc_type_code="030",  # 有価証券報告書
        form_code=None  # 全様式
    )
    
    if not documents:
        print("❌ 書類が見つかりませんでした。")
        return
    
    # 最新の書類を取得
    doc_info = documents[0]
    doc_id = doc_info.get("docID")
    
    print(f"   ✅ 書類が見つかりました: {doc_id}")
    print(f"   書類ID: {doc_id}")
    print(f"   提出日: {doc_info.get('submitDateTime', '不明')}")
    print(f"   書類種別: {doc_info.get('docTypeCode', '不明')}")
    print()
    
    # 3. XBRLをダウンロード
    print("3. XBRLをダウンロード中...")
    save_dir = project_root / "reports" / f"{code}_xbrl"
    save_dir.mkdir(parents=True, exist_ok=True)
    
    xbrl_dir = edinet_client.download_document(
        doc_id=doc_id,
        doc_type=1,  # XBRL
        save_dir=save_dir
    )
    
    if not xbrl_dir or not xbrl_dir.exists():
        print("❌ XBRLのダウンロードに失敗しました。")
        return
    
    print(f"   ✅ XBRLダウンロード完了: {xbrl_dir}\n")
    
    # 4. XBRLからテキストを抽出
    print("4. XBRLからテキストを抽出中...")
    xbrl_parser = XBRLParser()
    extracted_text = xbrl_parser.extract_text_from_xbrl(
        xbrl_dir=xbrl_dir,
        exclude_tables=True
    )
    
    if not extracted_text:
        print("❌ テキストが抽出できませんでした。")
        return
    
    print(f"   ✅ テキスト抽出完了: {len(extracted_text)}文字\n")
    
    # 5. 結果を保存
    output_file = project_root / f"xbrl_text_{code}_{doc_id}.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(extracted_text)
    
    print("=" * 60)
    print("抽出結果")
    print("=" * 60)
    print(f"テキスト長: {len(extracted_text)} 文字")
    print(f"保存先: {output_file}")
    print()
    print("-" * 60)
    print("テキストの最初の2000文字:")
    print("-" * 60)
    print(extracted_text[:2000])
    print()
    print("-" * 60)
    print("テキストの最後の2000文字:")
    print("-" * 60)
    print(extracted_text[-2000:])


if __name__ == "__main__":
    main()

