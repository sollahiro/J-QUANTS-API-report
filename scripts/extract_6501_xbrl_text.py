#!/usr/bin/env python3
"""
6501のXBRLテキストを抽出するスクリプト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analysis.xbrl_parser import XBRLParser

def main():
    """メイン処理"""
    code = "6501"
    
    # レポートディレクトリを検索
    reports_dir = project_root / "reports"
    edinet_dirs = list(reports_dir.glob(f"{code}_edinet/*_xbrl"))
    
    if not edinet_dirs:
        print(f"❌ {code}のXBRLディレクトリが見つかりませんでした。")
        print(f"   検索パス: {reports_dir / f'{code}_edinet'}")
        return
    
    # 最新のディレクトリを使用（ファイル名でソート）
    xbrl_dir = sorted(edinet_dirs, key=lambda p: p.name, reverse=True)[0]
    print(f"📂 XBRLディレクトリ: {xbrl_dir}")
    
    # XBRLパーサーを初期化
    xbrl_parser = XBRLParser()
    
    # XBRLセクションを抽出（報告書タイプに関係なく共通ロジックで抽出）
    print(f"🔍 XBRLセクションを抽出中...")
    sections = xbrl_parser.extract_sections_by_type(xbrl_dir)
    
    if not sections:
        print(f"❌ XBRLセクションの抽出に失敗しました。")
        return
    
    print(f"✅ XBRLセクション抽出完了: {len(sections)}個のセクション")
    
    # セクションを順序付きで結合
    section_order = sorted(sections.keys())
    xbrl_text_parts = []
    for section_id in section_order:
        text = sections[section_id]
        section_def = xbrl_parser.COMMON_SECTIONS.get(section_id)
        title = section_def['title'] if section_def else f"セクション{section_id}"
        if text:
            print(f"  - {section_id}: {title} ({len(text)}文字)")
            xbrl_text_parts.append(f"【{section_id}: {title}】\n{text}")
        else:
            print(f"  - {section_id}: {title} (見つかりませんでした)")
    
    xbrl_text = '\n\n'.join(xbrl_text_parts)
    
    # ファイルに保存
    doc_id = xbrl_dir.parent.name  # 親ディレクトリ名がdoc_id
    output_file = project_root / f"xbrl_text_{code}_{doc_id}.txt"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xbrl_text)
    
    print(f"\n💾 テキストを保存しました: {output_file}")
    print(f"📊 合計文字数: {len(xbrl_text)}文字")
    
    # 各セクションの最初の500文字を表示
    print("\n" + "="*80)
    print("各セクションの内容（最初の500文字）:")
    print("="*80)
    for section_id in section_order:
        text = sections[section_id]
        if text:
            section_def = xbrl_parser.COMMON_SECTIONS.get(section_id)
            title = section_def['title'] if section_def else f"セクション{section_id}"
            print(f"\n【{section_id}: {title}】")
            print("-" * 80)
            print(text[:500])
            if len(text) > 500:
                print(f"... (残り {len(text) - 500} 文字)")

if __name__ == "__main__":
    main()

