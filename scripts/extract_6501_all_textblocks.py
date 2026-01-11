#!/usr/bin/env python3
"""
6501のすべてのTextBlockを抽出して検索するスクリプト
"""

import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import html
import re

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analysis.xbrl_parser import XBRLParser

def extract_all_textblocks(xbrl_dir: Path) -> dict:
    """すべてのTextBlock要素を抽出"""
    all_text_blocks = {}
    namespaces = {}
    
    # XBRLインスタンス文書を検索
    xml_files = []
    for xml_file in xbrl_dir.rglob("*.xml"):
        if any(suffix in xml_file.name for suffix in ['_lab.xml', '_pre.xml', '_cal.xml', '_def.xml']):
            continue
        xml_files.append(xml_file)
    
    xbrl_files = list(xbrl_dir.rglob("*.xbrl"))
    xml_files.extend(xbrl_files)
    
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
                        namespaces[ns_prefix] = ns_prefix
            
            # 全ての要素を走査
            for elem in root.iter():
                tag = elem.tag
                if '}' in tag:
                    local_tag = tag.split('}')[1]
                else:
                    local_tag = tag
                
                # TextBlockで終わる要素を検索
                if local_tag.endswith('TextBlock') or 'TextBlock' in local_tag:
                    # 要素のテキストを取得
                    text = extract_text_from_element(elem)
                    if text and len(text) > 50:
                        all_text_blocks[local_tag] = {
                            'text': text,
                            'file': xml_file.name
                        }
                        
        except Exception as e:
            print(f"エラー: {xml_file.name} - {e}")
            continue
    
    return all_text_blocks

def extract_text_from_element(element: ET.Element) -> str:
    """要素からテキストを抽出"""
    text_parts = []
    
    if element.text:
        text = element.text.strip()
        if text:
            text_parts.append(text)
    
    for child in element:
        child_text = extract_text_from_element(child)
        if child_text:
            text_parts.append(child_text)
        
        if child.tail:
            tail_text = child.tail.strip()
            if tail_text:
                text_parts.append(tail_text)
    
    combined_text = '\n'.join(text_parts)
    combined_text = html.unescape(combined_text)
    combined_text = re.sub(r'<[^>]+>', '', combined_text)
    combined_text = re.sub(r'\s+', ' ', combined_text)
    combined_text = combined_text.strip()
    
    return combined_text

def search_keywords(text_blocks: dict, keywords: list) -> dict:
    """キーワードで検索"""
    results = {}
    for keyword in keywords:
        results[keyword] = []
        for block_name, block_data in text_blocks.items():
            text = block_data['text']
            if keyword in text:
                results[keyword].append({
                    'block_name': block_name,
                    'file': block_data['file'],
                    'preview': text[:200]
                })
    return results

def main():
    """メイン処理"""
    code = "6501"
    
    # レポートディレクトリを検索
    reports_dir = project_root / "reports"
    edinet_dirs = list(reports_dir.glob(f"{code}_edinet/*_xbrl"))
    
    if not edinet_dirs:
        print(f"❌ {code}のXBRLディレクトリが見つかりませんでした。")
        return
    
    xbrl_dir = sorted(edinet_dirs, key=lambda p: p.name, reverse=True)[0]
    print(f"📂 XBRLディレクトリ: {xbrl_dir}\n")
    
    # すべてのTextBlockを抽出
    print("🔍 すべてのTextBlockを抽出中...")
    all_text_blocks = extract_all_textblocks(xbrl_dir)
    print(f"✅ {len(all_text_blocks)}個のTextBlockを発見\n")
    
    # 見つからなかったセクションのキーワードで検索
    search_keywords_list = {
        'B': ['経営方針', '経営環境', '対処すべき課題', 'BusinessPolicy'],
        'F': ['研究開発', 'ResearchAndDevelopment'],
        'G': ['設備投資', '設備投資等の概要', 'CapitalInvestment'],
        'H': ['配当政策', '配当方針', 'ProfitDistribution', 'ReturnOfSurplus']
    }
    
    print("="*80)
    print("見つからなかったセクションの検索結果:")
    print("="*80)
    
    for section_id, keywords in search_keywords_list.items():
        print(f"\n【セクション {section_id}】")
        print("-" * 80)
        found = False
        for keyword in keywords:
            for block_name, block_data in all_text_blocks.items():
                text = block_data['text']
                if keyword in text:
                    print(f"✅ キーワード '{keyword}' を発見:")
                    print(f"   要素名: {block_name}")
                    print(f"   ファイル: {block_data['file']}")
                    print(f"   文字数: {len(text)}文字")
                    print(f"   プレビュー: {text[:300]}...")
                    print()
                    found = True
                    break
            if found:
                break
        if not found:
            print(f"❌ キーワード {keywords} が見つかりませんでした")
    
    # すべてのTextBlock要素名を表示
    print("\n" + "="*80)
    print("すべてのTextBlock要素名:")
    print("="*80)
    for i, block_name in enumerate(sorted(all_text_blocks.keys()), 1):
        block_data = all_text_blocks[block_name]
        print(f"{i:3d}. {block_name} ({len(block_data['text'])}文字) - {block_data['file']}")
    
    # ファイルに保存
    output_file = project_root / f"all_textblocks_{code}.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write("すべてのTextBlock要素\n")
        f.write("="*80 + "\n\n")
        for block_name in sorted(all_text_blocks.keys()):
            block_data = all_text_blocks[block_name]
            f.write(f"【{block_name}】\n")
            f.write(f"ファイル: {block_data['file']}\n")
            f.write(f"文字数: {len(block_data['text'])}文字\n")
            f.write("-" * 80 + "\n")
            f.write(block_data['text'])
            f.write("\n\n" + "="*80 + "\n\n")
    
    print(f"\n💾 すべてのTextBlockを保存しました: {output_file}")

if __name__ == "__main__":
    main()


