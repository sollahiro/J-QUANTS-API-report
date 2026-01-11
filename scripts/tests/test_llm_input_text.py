"""
LLMに渡すテキストを確認するテストスクリプト

銘柄コード9432の有価証券報告書から抽出されたテキストを出力します。
要約の直前で停止します。
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.analysis.individual import IndividualAnalyzer
from src.api.client import JQuantsAPIClient

def main():
    """メイン処理"""
    code = "4689"
    
    print(f"============================================================")
    print(f"LLM入力テキスト確認テスト - 銘柄コード: {code}")
    print(f"============================================================\n")
    
    try:
        # アナライザーを初期化
        print("1. アナライザーを初期化中...")
        api_client = JQuantsAPIClient()
        analyzer = IndividualAnalyzer(api_client=api_client, use_cache=True)
        
        if not analyzer.edinet_client:
            print("❌ EDINETクライアントが初期化されていません。")
            print("   EDINET_API_KEYが設定されているか確認してください。")
            return
        
        if not analyzer.xbrl_parser:
            print("❌ XBRLパーサーが初期化されていません。")
            return
        
        print("   ✅ アナライザーの初期化に成功しました\n")
        
        # 最新年度の有価証券報告書を取得
        print("2. XBRLファイルを検索中...")
        
        # reportsディレクトリからXBRLディレクトリを検索
        reports_dir = project_root / "reports" / f"{code}_edinet"
        
        if not reports_dir.exists():
            print(f"❌ レポートディレクトリが見つかりません: {reports_dir}")
            print("\n代替方法: EDINET APIから取得を試みます...\n")
            
            # EDINET APIから取得を試みる
            from datetime import datetime
            current_year = datetime.now().year
            years_to_fetch = [current_year - i for i in range(5)]  # 過去5年分を検索
            
            print(f"   取得年度: {years_to_fetch}\n")
            
            # J-QUANTSから年度データは取得しない（メソッドが存在しないため）
            annual_data = None
            
            # llm_summarizerを一時的に無効化して要約をスキップ
            original_llm_summarizer = analyzer.llm_summarizer
            analyzer.llm_summarizer = None
            
            results = analyzer.fetch_edinet_reports(
                code=code,
                years=years_to_fetch,
                jquants_annual_data=annual_data,
                progress_callback=lambda msg: print(f"   - {msg}")
            )
            
            # llm_summarizerを復元
            analyzer.llm_summarizer = original_llm_summarizer
            
            if not results:
                print("❌ EDINETレポートが取得できませんでした。")
                print("   EDINET_API_KEYが設定されているか、または該当する有価証券報告書が存在するか確認してください。")
                return
            
            # 最新年度のレポートからテキストを抽出
            latest_year = max(results.keys())
            result = results[latest_year]
            xbrl_path_str = result.get('xbrl_path')
            doc_id = result.get('docID', '不明')
            
            # xbrl_pathをPathオブジェクトに変換
            if xbrl_path_str:
                xbrl_dir = Path(xbrl_path_str)
            else:
                print("❌ XBRLパスが取得できませんでした。")
                return
            
            print(f"   ✅ レポートを取得しました: {doc_id} (年度: {latest_year})\n")
        else:
            # 既存のXBRLディレクトリを使用
            xbrl_dirs = [d for d in reports_dir.iterdir() if d.is_dir() and d.name.endswith('_xbrl')]
            if not xbrl_dirs:
                print(f"❌ XBRLディレクトリが見つかりません: {reports_dir}")
                return
            
            # 最新のXBRLディレクトリを使用
            xbrl_dir = max(xbrl_dirs, key=lambda p: p.stat().st_mtime)
            doc_id = xbrl_dir.stem.replace('_xbrl', '')
            print(f"   見つかったXBRLディレクトリ: {xbrl_dir.name}\n")
        
        print(f"   書類ID: {doc_id}")
        print(f"   XBRLディレクトリ: {xbrl_dir}\n")
        
        print("3. XBRLから経営方針テキストを抽出中...\n")
        
        # XBRLから経営方針テキストを抽出（LLMに渡すテキスト）
        sections = analyzer.xbrl_parser.extract_sections_by_type(xbrl_dir)
        
        # セクションを順序付きで結合（A→B→C...の順）
        section_order = sorted(sections.keys())
        policy_text_parts = []
        for section_id in section_order:
            text = sections[section_id]
            if text:
                policy_text_parts.append(text)
        
        policy_text = '\n\n'.join(policy_text_parts)
        
        if not policy_text:
            print("❌ 経営方針テキストが抽出できませんでした。")
            return
        
        print("=" * 60)
        print("LLMに渡すテキスト（要約直前）")
        print("=" * 60)
        print(f"\nテキスト長: {len(policy_text)} 文字\n")
        
        # テキストをファイルに保存
        output_file = project_root / f"llm_input_text_{code}_{doc_id}.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(policy_text)
        print(f"✅ テキストをファイルに保存しました: {output_file}\n")
        
        print("-" * 60)
        print("テキストの最初の2000文字:")
        print("-" * 60)
        print(policy_text[:2000])
        print("\n... (中略) ...\n")
        print("-" * 60)
        print("テキストの最後の2000文字:")
        print("-" * 60)
        print(policy_text[-2000:])
        print("-" * 60)
        
        # プロンプトも表示（オプション）
        if analyzer.llm_summarizer:
            print("\n" + "=" * 60)
            print("使用されるプロンプト（最初の500文字）")
            print("=" * 60)
            # プロンプトの最初の部分を表示するために、summarize_textの内部を確認
            # 実際にはプロンプト全体は長いので、最初の部分だけ表示
            section_name = "経営方針・課題"
            prompt_start = f"""以下のテキストは有価証券報告書の「{section_name}」セクションです。
テキスト内に実際に記載されている具体的な数値・指標・事実のみを抽出して、以下の4項目のみについて日本語で要約してください。

【絶対に守るルール】
- 4項目（①事業の概要・リスク、②経営成績・財政状態に関する自社の分析、③キャッシュフロー状況、④配当政策についての言及）のみを記述してください
..."""
            print(prompt_start)
            print("\n... (プロンプトは長いため省略) ...\n")
        
        print("\n" + "=" * 60)
        print("テスト完了")
        print("=" * 60)
        print("\n上記のテキストがLLMに渡されます。")
        print("要約は実行されていません。")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

