#!/usr/bin/env python3
"""
6501のXBRL解析をテストするスクリプト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.analysis.xbrl_parser import XBRLParser
from src.utils.xbrl_compressor import compress_text
from src.analysis.llm_summarizer import LLMSummarizer

def main():
    code = "6501"
    doc_id = "S100X0LM"
    
    print(f"============================================================")
    print(f"6501 XBRL解析テスト - docID: {doc_id}")
    print(f"============================================================\n")
    
    # XBRLディレクトリのパス
    xbrl_dir = project_root / "reports" / f"{code}_edinet" / f"{doc_id}_xbrl"
    
    if not xbrl_dir.exists():
        print(f"❌ XBRLディレクトリが見つかりません: {xbrl_dir}")
        return
    
    print(f"✅ XBRLディレクトリ: {xbrl_dir}\n")
    
    # 1. XBRLパーサーでテキスト抽出
    print("1. XBRLからテキストを抽出中...")
    xbrl_parser = XBRLParser()
    xbrl_text = xbrl_parser.extract_text_from_xbrl(xbrl_dir, exclude_tables=True)
    
    if not xbrl_text:
        print("❌ XBRLテキストが抽出できませんでした")
        return
    
    print(f"✅ XBRLテキスト抽出成功: {len(xbrl_text)} 文字\n")
    print(f"最初の1000文字:\n{xbrl_text[:1000]}\n")
    print(f"最後の1000文字:\n{xbrl_text[-1000:]}\n")
    
    # 2. テキスト圧縮
    print("2. テキストを圧縮中...")
    compressed_text = compress_text(xbrl_text)
    
    if not compressed_text:
        print("❌ テキストの圧縮に失敗しました")
        return
    
    print(f"✅ テキスト圧縮成功: {len(compressed_text)} 文字\n")
    print(f"圧縮後のテキスト（最初の2000文字）:\n{compressed_text[:2000]}\n")
    
    # 3. LLM要約
    print("3. LLMで要約を生成中...")
    llm_summarizer = LLMSummarizer()
    
    # Ollama接続確認（summarize_text内でチェックされる）
    print(f"✅ LLM要約クラス初期化完了: モデル={llm_summarizer.model}\n")
    
    try:
        summary = llm_summarizer.summarize_text(
            compressed_text,
            "経営方針・課題",
            doc_id=doc_id,
            use_cache=False  # キャッシュを使わずにテスト
        )
        
        if summary:
            print(f"✅ 要約生成成功: {len(summary)} 文字\n")
            print("=" * 60)
            print("生成された要約:")
            print("=" * 60)
            print(summary)
        else:
            print("❌ 要約が生成されませんでした（空文字列）")
    except Exception as e:
        print(f"❌ 要約生成中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

