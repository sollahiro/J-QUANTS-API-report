"""
EDINET統合機能のテストスクリプト

1. EDINET API接続テスト
2. 有報取得テスト（銘柄コード: 7203, 年度: 2023）
3. XBRL解析テスト
4. LLM要約テスト（Ollama起動確認含む）
5. 統合テスト（HTML/CSV生成）
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.edinet_client import EdinetAPIClient
from src.analysis.xbrl_parser import XBRLParser
from src.analysis.llm_summarizer import LLMSummarizer
from src.analysis.individual import IndividualAnalyzer
from src.report.html_report import HTMLReportGenerator


def test_edinet_api():
    """EDINET API接続テスト"""
    print("=" * 60)
    print("1. EDINET API接続テスト")
    print("=" * 60)
    
    try:
        client = EdinetAPIClient()
        if not client.api_key:
            print("⚠️  EDINET_API_KEYが設定されていません。")
            print("   .envファイルにEDINET_API_KEYを設定してください。")
            return False
        
        print("✅ EDINET APIクライアントの初期化に成功しました。")
        return True
    
    except Exception as e:
        print(f"❌ EDINET API接続テスト失敗: {e}")
        return False


def test_fetch_reports():
    """有報取得テスト"""
    print("\n" + "=" * 60)
    print("2. 有報取得テスト（銘柄コード: 7203, 年度: 2023）")
    print("=" * 60)
    
    try:
        client = EdinetAPIClient()
        if not client.api_key:
            print("⚠️  EDINET_API_KEYが設定されていないため、スキップします。")
            return False
        
        reports = client.fetch_reports("7203", [2023])
        
        if reports:
            print(f"✅ 有報取得成功: {len(reports)}件")
            for year, info in reports.items():
                print(f"   {year}年度: docID={info.get('docID')}, submitDate={info.get('submitDate')}")
            return True
        else:
            print("⚠️  有報が見つかりませんでした。")
            return False
    
    except Exception as e:
        print(f"❌ 有報取得テスト失敗: {e}")
        return False


def test_xbrl_parser():
    """XBRL解析テスト"""
    print("\n" + "=" * 60)
    print("3. XBRL解析テスト")
    print("=" * 60)
    
    try:
        parser = XBRLParser()
        
        # テスト用のXBRLディレクトリを検索
        cache_dir = project_root / "cache" / "edinet"
        xbrl_dirs = list(cache_dir.glob("*_xbrl"))
        
        if not xbrl_dirs:
            print("⚠️  XBRLディレクトリが見つかりません。")
            print("   先に有報取得テストを実行してください。")
            return False
        
        xbrl_dir = xbrl_dirs[0]
        print(f"   テスト対象: {xbrl_dir}")
        
        # MD&A抽出テスト
        mda_text = parser.extract_mda(xbrl_dir)
        if mda_text:
            print(f"✅ MD&A抽出成功: {len(mda_text)}文字")
            print(f"   プレビュー: {mda_text[:100]}...")
        else:
            print("⚠️  MD&A抽出失敗（セクションが見つかりませんでした）")
        
        # 経営方針抽出テスト
        policy_text = parser.extract_management_policy(xbrl_dir)
        if policy_text:
            print(f"✅ 経営方針抽出成功: {len(policy_text)}文字")
            print(f"   プレビュー: {policy_text[:100]}...")
        else:
            print("⚠️  経営方針抽出失敗（セクションが見つかりませんでした）")
        
        return True
    
    except Exception as e:
        print(f"❌ XBRL解析テスト失敗: {e}")
        return False


def test_llm_summarizer():
    """LLM要約テスト"""
    print("\n" + "=" * 60)
    print("4. LLM要約テスト（Ollama起動確認含む）")
    print("=" * 60)
    
    try:
        summarizer = LLMSummarizer()
        
        # Ollama起動確認
        if not summarizer._check_ollama_available():
            print("⚠️  Ollamaが起動していません。")
            print("   以下のコマンドでOllamaを起動してください:")
            print("   ollama serve")
            print("   ollama pull gemma2:2b")
            return False
        
        print("✅ Ollama起動確認成功")
        
        # テストテキスト
        test_text = """
        当社は、自動車の研究開発、製造、販売を主な事業としています。
        2023年度は、電気自動車の開発に注力し、新たなモデルを投入しました。
        また、サプライチェーンの最適化により、コスト削減を実現しました。
        """
        
        summary = summarizer.summarize_text(
            test_text,
            "経営方針・課題",
            doc_id="test_doc"
        )
        
        if summary and "要約生成不可" not in summary:
            print(f"✅ LLM要約成功: {len(summary)}文字")
            print(f"   要約結果: {summary}")
            return True
        else:
            print(f"⚠️  LLM要約失敗: {summary}")
            return False
    
    except Exception as e:
        print(f"❌ LLM要約テスト失敗: {e}")
        return False


def test_integration():
    """統合テスト（HTML/CSV生成）"""
    print("\n" + "=" * 60)
    print("5. 統合テスト（HTML/CSV生成）")
    print("=" * 60)
    
    try:
        analyzer = IndividualAnalyzer()
        result = analyzer.analyze_stock("7203", save_data=False)
        
        if not result:
            print("❌ 分析結果の取得に失敗しました。")
            return False
        
        print("✅ 分析結果取得成功")
        
        # EDINETデータの確認
        edinet_data = result.get("edinet_data", {})
        if edinet_data:
            print(f"✅ EDINETデータ取得成功: {len(edinet_data)}年度分")
        else:
            print("⚠️  EDINETデータが取得できませんでした。")
        
        # HTMLレポート生成
        report_generator = HTMLReportGenerator()
        output_path = project_root / "reports" / "test_7203_report"
        
        report_generator.generate(result, str(output_path))
        
        html_path = output_path.with_suffix('.html')
        csv_path = output_path.with_suffix('.csv')
        
        if html_path.exists() and csv_path.exists():
            print(f"✅ HTML/CSVレポート生成成功")
            print(f"   HTML: {html_path}")
            print(f"   CSV: {csv_path}")
            return True
        else:
            print("❌ HTML/CSVレポート生成失敗")
            return False
    
    except Exception as e:
        print(f"❌ 統合テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン関数"""
    print("\n" + "=" * 60)
    print("EDINET統合機能テスト")
    print("=" * 60)
    
    results = []
    
    # 1. EDINET API接続テスト
    results.append(("EDINET API接続", test_edinet_api()))
    
    # 2. 有報取得テスト
    results.append(("有報取得", test_fetch_reports()))
    
    # 3. XBRL解析テスト
    results.append(("XBRL解析", test_xbrl_parser()))
    
    # 4. LLM要約テスト
    results.append(("LLM要約", test_llm_summarizer()))
    
    # 5. 統合テスト
    results.append(("統合テスト", test_integration()))
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("テスト結果サマリー")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{test_name}: {status}")
    
    success_count = sum(1 for _, result in results if result)
    total_count = len(results)
    
    print(f"\n合計: {success_count}/{total_count} テスト成功")
    
    if success_count == total_count:
        print("\n🎉 すべてのテストが成功しました！")
        return 0
    else:
        print(f"\n⚠️  {total_count - success_count}個のテストが失敗しました。")
        return 1


if __name__ == "__main__":
    sys.exit(main())

