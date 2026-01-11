"""
LLM要約モジュール

Ollamaを使用してテキストを要約します。
"""

import logging
from typing import Optional
from pathlib import Path

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.warning("ollamaパッケージがインストールされていません。LLM要約機能は使用できません。")

from ..config import config

logger = logging.getLogger(__name__)


class LLMSummarizer:
    """LLM要約クラス"""
    
    def __init__(self, model: Optional[str] = None, timeout: int = 60):
        """
        初期化

        Args:
            model: 使用するモデル名（Noneの場合は環境変数LLM_MODELから取得、デフォルト: "gemma3:1b"）
            timeout: タイムアウト時間（秒、デフォルト: 60）
        """
        self.model = model or config.llm_model
        self.timeout = timeout
        
        # キャッシュディレクトリ（使用しない - pklに統合済み）
        # cache_dir = Path(config.cache_dir)
        # self.cache_dir = cache_dir / "edinet" / "summaries"
        # self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = None  # ファイルキャッシュは使用しない（pklに統合）
        
        if not OLLAMA_AVAILABLE:
            logger.warning("ollamaパッケージがインストールされていません。")
    
    def _check_ollama_available(self) -> bool:
        """
        Ollamaが利用可能かチェック

        Returns:
            利用可能な場合True
        """
        if not OLLAMA_AVAILABLE:
            return False
        
        try:
            # Ollamaのヘルスチェック（モデルリスト取得で確認）
            ollama.list()
            return True
        except Exception as e:
            logger.warning(f"Ollamaが起動していません: {e}")
            return False
    
    def _get_cache_path(self, doc_id: str, section: str) -> Path:
        """
        キャッシュファイルのパスを取得（使用しない - pklに統合済み）

        Args:
            doc_id: 書類管理番号
            section: セクション名

        Returns:
            キャッシュファイルのパス（使用しない）
        """
        # ファイルキャッシュは使用しない（pklに統合済み）
        # このメソッドは後方互換性のために残しているが、実際には使用されない
        safe_section = section.replace("/", "_").replace("\\", "_")
        # ダミーパスを返す（実際には使用されない）
        return Path("/dev/null")
    
    def _post_process_summary(self, summary: str) -> str:
        """
        要約テキストの後処理
        
        - 監査報告書の内容を削除
        - 禁止されている注記を削除
        - グラフのセクションタイトルや計算式を削除
        - 文字数制限の適用
        
        Args:
            summary: 要約テキスト
            
        Returns:
            後処理後の要約テキスト
        """
        import re
        
        # 1. 監査報告書の内容を積極的に削除
        audit_patterns = [
            r'本報告書は.*?',
            r'監査法人.*?',
            r'監査の目的と範囲.*?',
            r'監査の実施状況.*?',
            r'監査の結論.*?',
            r'重要な発見事項.*?',
            r'監査法人は.*?',
            r'監査人は.*?',
            r'期中レビュー.*?',
            r'要約中間連結財務諸表.*?',
            r'国際会計基準.*?',
            r'継続企業の前提.*?',
            r'財務諸表の作成.*?',
            r'適正に表示.*?',
            r'監査等委員会.*?',
            r'独立性.*?',
            r'職業倫理.*?',
            r'限定付結論.*?',
            r'否定的結論.*?',
            r'証拠に基づき.*?',
            r'2025年9月30日現在.*?',
            r'2025年4月1日から.*?',
            r'中間連結会計年度.*?',
            r'中間連結会計期間.*?',
        ]
        
        for pattern in audit_patterns:
            summary = re.sub(pattern, '', summary, flags=re.DOTALL | re.IGNORECASE)
        
        # 2. 禁止されている注記を削除
        notice_patterns = [
            r'注:.*?本要約は.*?自動生成.*?',
            r'注:.*?AIによる.*?',
            r'正確な情報については.*?原本.*?',
            r'有価証券報告書の原本.*?',
        ]
        
        for pattern in notice_patterns:
            summary = re.sub(pattern, '', summary, flags=re.DOTALL | re.IGNORECASE)
        
        # 3. グラフのセクションタイトルや計算式を削除
        graph_patterns = [
            r'📈\s*[^\n]+',
            r'簡易ROIC.*?',
            r'CF変換率.*?',
            r'営業利益/純資産.*?',
            r'営業CF/営業利益.*?',
        ]
        
        for pattern in graph_patterns:
            summary = re.sub(pattern, '', summary, flags=re.MULTILINE)
        
        # 4. 監査関連の単語が含まれる行を削除
        lines = summary.split('\n')
        filtered_lines = []
        for line in lines:
            # 監査関連のキーワードが含まれている行をスキップ
            if any(keyword in line for keyword in ['監査', '監査法人', '監査人', '財務諸表の作成', '報告書の発表', '会計基準', '会計方針']):
                continue
            filtered_lines.append(line)
        summary = '\n'.join(filtered_lines)
        
        # 5. 余分な空白を整理
        summary = re.sub(r'\n{3,}', '\n\n', summary)
        summary = summary.strip()
        
        # 6. 文字数制限の適用（1,000文字を超える場合は切り詰め）
        if len(summary) > 1000:
            # 1,000文字以内になるように、文単位で切り詰め
            sentences = re.split(r'[。\n]', summary)
            truncated = []
            current_length = 0
            for sentence in sentences:
                if current_length + len(sentence) + 1 <= 1000:
                    truncated.append(sentence)
                    current_length += len(sentence) + 1
                else:
                    break
            summary = '。'.join(truncated)
            if summary and not summary.endswith('。'):
                summary += '。'
        
        return summary
    
    def summarize_text(
        self,
        text: str,
        section_name: str,
        doc_id: Optional[str] = None,
        use_cache: bool = True
    ) -> str:
        """
        テキストを要約

        Args:
            text: 要約するテキスト
            section_name: セクション名（プロンプトに使用）
            doc_id: 書類管理番号（キャッシュ用、省略可）
            use_cache: キャッシュを使用するか

        Returns:
            要約テキスト（エラー時は"要約生成不可"）
        """
        if not text or not text.strip():
            return "要約対象のテキストがありません。"
        
        # キャッシュチェック（ファイルキャッシュは使用しない - pklに統合済み）
        # キャッシュはindividual.pyのedinet_dataのmanagement_policyに保存されているため、
        # ここではファイルキャッシュをチェックしない
        # if use_cache and doc_id:
        #     cache_path = self._get_cache_path(doc_id, section_name)
        #     if cache_path.exists():
        #         try:
        #             with open(cache_path, "r", encoding="utf-8") as f:
        #                 cached_summary = f.read()
        #             logger.debug(f"キャッシュから要約を取得: {doc_id} {section_name}")
        #             return cached_summary
        #         except Exception as e:
        #             logger.warning(f"キャッシュ読み込みエラー: {e}")
        
        # Ollamaが利用可能かチェック
        if not self._check_ollama_available():
            logger.warning("Ollamaが起動していないため、要約をスキップします。")
            return "要約生成不可（Ollama未起動）"
        
        # プロンプト作成（セクション名に応じてプロンプトを変更）
        # MD&Aも含めてマークダウン記号を削除するため、すべてのセクションで処理
        if "経営方針" in section_name or "課題" in section_name:
            # 経営方針・課題セクション用のプロンプト
            prompt = f"""以下のテキストは有価証券報告書の「{section_name}」セクションです。以下の4項目について、具体的な数値を含めて要約してください。

【文字数制限】レポート全体は800文字以上1,000文字以内で記述してください。

①事業の概要・リスク
事業概要、リスク要因、数値目標、財務指標、事業指標、M&A・投資計画について、具体的な数値（金額、比率、数量、年度など）を含めて記述してください。

②経営成績・財政状態
売上高、営業利益、純利益などの経営成績、および資産、負債、純資産などの財政状態に関する分析について、具体的な数値（金額、比率、数量など）を含めて記述してください。

③キャッシュフロー状況
営業キャッシュフロー、投資キャッシュフロー、フリーキャッシュフローの状況について、具体的な数値（金額、比率、数量など）を含めて記述してください。

④配当政策
配当政策、配当額・配当率、株主還元方針、自社株買い、配当の継続性・安定性について、具体的な数値（金額、比率、数量など）を含めて記述してください。

【重要ルール】
- 各項目には必ず具体的な数値を含めてください。数値が含まれていない項目は省略してください
- 「高い」「良好」「安定」などの抽象的な表現のみの記述は禁止です
- 会社を指す単語は「同社」を使用してください

【テキスト】
{text}

上記のテキストを要約してください。"""
        else:
            # その他のセクション用のプロンプト（MD&Aなど）
            prompt = f"""以下は有価証券報告書の「{section_name}」セクションです。投資判断に重要なポイントを3-5個の箇条書きで簡潔に要約してください。

【出力要件】
- 必ず日本語で出力してください
- 各項目は50文字以内で記述してください
- マークダウン記号（##、**、*など）は使用しないでください。平文で記述してください

【テキスト】
{text}

上記のテキストを要約してください。"""
        
        try:
            # Ollamaで要約生成
            # 日本語出力を確実にするため、システムプロンプトも追加
            if "経営方針" in section_name or "課題" in section_name:
                system_prompt = "日本語のみで回答してください。文字数は800文字以上1,000文字以内で記述してください。"
            else:
                system_prompt = "日本語のみで回答してください。"
            
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                system=system_prompt,  # システムプロンプトで言語を指定（日本語で記述）
                options={
                    "temperature": 0.3,  # 温度を少し上げて創造性を向上
                    "num_predict": 3000,  # 最大3000トークン（800〜1,000文字のレポート生成に必要、余裕を持たせる）
                    "top_p": 0.9,  # top_pを設定して出力を安定化
                }
            )
            
            summary = response.get("response", "").strip()
            
            if not summary:
                summary = "要約生成不可（レスポンスが空）"
            else:
                # 後処理：不要な内容を削除
                summary = self._post_process_summary(summary)
                
                # マークダウン記法を保持しつつ、不要な部分を削除
                import re
                # 最初の見出し行（タイトル行）を削除
                lines = summary.split('\n')
                filtered_lines = []
                skip_first_heading = True
                for line in lines:
                    stripped = line.strip()
                    # 最初の##見出しをスキップ（タイトル行を削除）
                    if skip_first_heading and stripped.startswith('##'):
                        skip_first_heading = False
                        continue
                    # 見出し行（①、②で始まる行）をスキップ（マークダウン見出しに置き換える）
                    if stripped and stripped[0] in '①②③④⑤':
                        continue
                    # <br>タグを改行に変換
                    line = line.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
                    filtered_lines.append(line)
                summary = '\n'.join(filtered_lines)
                
                # 「注記：」「備考：」「III.」「要点まとめ」で始まる行以降を削除
                summary = re.sub(r'\n\s*(注記|備考|III\.|要点まとめ).*$', '', summary, flags=re.MULTILINE | re.DOTALL)
                
                # *で始まる箇条書きを-に統一（マークダウン記法の統一）
                summary = re.sub(r'^\*\s+', '- ', summary, flags=re.MULTILINE)
                
                # 余分な空行を整理（3行以上連続する空行を2行に）
                summary = re.sub(r'\n{3,}', '\n\n', summary)
                summary = summary.strip()
            
            # キャッシュに保存（ファイルキャッシュは使用しない - pklに統合済み）
            # キャッシュはindividual.pyのedinet_dataのmanagement_policyに保存されるため、
            # ここではファイルキャッシュに保存しない
            # if use_cache and doc_id and summary != "要約生成不可（レスポンスが空）":
            #     try:
            #         cache_path = self._get_cache_path(doc_id, section_name)
            #         with open(cache_path, "w", encoding="utf-8") as f:
            #             f.write(summary)
            #     except Exception as e:
            #         logger.warning(f"キャッシュ保存エラー: {e}")
            
            logger.info(f"要約生成完了: {section_name} ({len(summary)}文字)")
            return summary
        
        except Exception as e:
            logger.error(f"LLM要約エラー: {section_name} - {e}")
            return "要約生成不可（エラー発生）"

