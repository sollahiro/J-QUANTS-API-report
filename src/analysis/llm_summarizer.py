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
    
    def __init__(self, model: str = "gemma2:2b", timeout: int = 60):
        """
        初期化

        Args:
            model: 使用するモデル名（デフォルト: "gemma2:2b"）
            timeout: タイムアウト時間（秒、デフォルト: 60）
        """
        self.model = model
        self.timeout = timeout
        
        # キャッシュディレクトリ
        cache_dir = Path(config.cache_dir)
        self.cache_dir = cache_dir / "edinet" / "summaries"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
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
        キャッシュファイルのパスを取得

        Args:
            doc_id: 書類管理番号
            section: セクション名

        Returns:
            キャッシュファイルのパス
        """
        safe_section = section.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{doc_id}_{safe_section}.txt"
    
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
        
        # キャッシュチェック
        if use_cache and doc_id:
            cache_path = self._get_cache_path(doc_id, section_name)
            if cache_path.exists():
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        cached_summary = f.read()
                    logger.debug(f"キャッシュから要約を取得: {doc_id} {section_name}")
                    return cached_summary
                except Exception as e:
                    logger.warning(f"キャッシュ読み込みエラー: {e}")
        
        # Ollamaが利用可能かチェック
        if not self._check_ollama_available():
            logger.warning("Ollamaが起動していないため、要約をスキップします。")
            return "要約生成不可（Ollama未起動）"
        
        # プロンプト作成（セクション名に応じてプロンプトを変更）
        # MD&Aも含めてマークダウン記号を削除するため、すべてのセクションで処理
        if "経営方針" in section_name or "課題" in section_name:
            # 経営方針・課題セクション用のプロンプト
            # プロンプトの最初と最後に日本語指定を強く配置
            # gemma2:2bは日本語出力が弱いため、より強力な指示を追加
            prompt = f"""日本語で要約してください。英語の単語や文章は一切使用しないでください。英語の固有名詞も日本語に翻訳してください。

以下のテキストは有価証券報告書の「{section_name}」セクションです。
事業戦略の具体的な施策、事業環境、リスク要因を中心に、具体的な数値・指標・事実を抽出して日本語で要約してください。

【重要】回答は必ず日本語で記述してください。英語の単語、文章、固有名詞は一切使用しないでください。英語の固有名詞は日本語に翻訳してください。
【重要】マークダウン記法を使用して構造化してください。見出しは##、箇条書きは-、強調は**text**を使用してください。
経営方針や理念などの定性的な記述は除外し、具体的な数値・指標・事実のみを抽出してください。

以下の4項目について、テキスト内に記載されている具体的な情報のみを要約してください：

①事業戦略の具体的な施策
以下のような具体的な数値・指標・事実を必ず抽出してください：
- 数値目標（例: 2030年までに売上高10兆円、2030年までにCO2排出量50％削減、2025年度までにEPS3倍、ROIC目標値15％以上など）
- 財務指標（例: 総還元性向50％以上、WACC低減により3％以下、ネットD/Eレシオ0.5倍以下、EBITDA倍率10倍以上など）
- 事業指標（例: 売上高目標1兆円、営業利益率目標20％、セグメント別売上高（食品5000億円、医薬3000億円など））
- M&A・投資計画（例: 2024年度にM&A予算500億円、新規事業投資300億円など）
- 事業ポートフォリオ戦略（例: 成長事業への投資比率60％、収益事業の売却により200億円の資金回収など）

②事業環境
以下のような具体的な市場・競争・技術動向を抽出してください：
- 市場規模・成長率（例: 国内市場規模1兆円、年率5％成長、海外市場規模10兆円など）
- 競争環境（例: 市場シェア1位（30％）、競合3社との競争激化、新規参入企業5社など）
- 技術動向（例: AI技術の導入により生産効率30％向上、新技術開発により製品ライフサイクル短縮など）
- 規制・法制度の変化（例: 新規制により2025年から適用、法改正により事業機会拡大など）

③リスク要因
以下のような具体的なリスク情報を抽出してください：
- 事業リスク（例: 原材料価格高騰によりコスト増加率10％、為替変動により営業利益への影響±50億円など）
- 財務リスク（例: 金利上昇により利息負担増加20億円、為替リスクにより損失可能性100億円など）
- 経営リスク（例: 人材不足により生産能力低下リスク、サイバー攻撃による情報漏洩リスクなど）
- リスク対策（例: ヘッジ取引により為替リスク50％軽減、保険加入により損失補償など）

④その他の重要な取り組み
以下のような具体的な取り組みを抽出してください：
- 技術開発・研究開発（例: R&D投資額500億円、新製品開発件数10件、特許取得数50件など）
- 組織体制・ガバナンス（例: 新規委員会設置、外部取締役3名選任、内部監査体制強化など）
- サステナビリティ（例: CO2排出量30％削減目標、再生可能エネルギー導入率50％、ESG投資1000億円など）

各項目について、テキスト内に記載されている具体的な数値・指標・事実のみを要約してください。
数値や指標が記載されている場合は必ずその数値を含めてください。
数値や指標が記載されていない項目は含めないでください（「記載なし」や「特に記載なし」と書かないでください）。
経営方針や理念などの定性的な記述は除外してください。

マークダウン記法を使用して構造化してください：
- 見出し: ## 見出し名
- 箇条書き: - 項目
- 強調: **強調テキスト**
- 段落: 空行で区切る

【最重要】回答は必ず日本語で記述してください。英語の単語、文章、固有名詞は一切使用しないでください。英語の固有名詞は日本語に翻訳してください。日本語のみで回答してください。

{text}

上記のテキストを日本語で要約してください。英語の単語、文章、固有名詞は一切使用しないでください。英語の固有名詞は日本語に翻訳してください。"""
        else:
            # その他のセクション用のプロンプト（MD&Aなど）
            prompt = f"""日本語で回答してください。必ず日本語のみを使用してください。英語は一切使用しないでください。

以下は有価証券報告書の「{section_name}」セクションです。
投資判断に重要なポイントを3-5個の箇条書きで簡潔に要約してください。
各項目は50文字以内で記述してください。

【出力言語】必ず日本語で出力してください。英語やその他の言語は一切使用しないでください。
【フォーマット】マークダウン記号（##、**、*など）は一切使用しないでください。平文で記述してください。

【最重要】必ず日本語で出力してください。英語は一切使用しないでください。日本語のみで回答してください。

{text}

上記のテキストを要約してください。必ず日本語で出力してください。"""
        
        try:
            # Ollamaで要約生成
            # 日本語出力を確実にするため、システムプロンプトも追加
            # gemma2:2bは日本語出力が弱いため、より強力な指示を追加
            system_prompt = "あなたは日本語で回答するAIアシスタントです。必ず日本語のみで出力してください。英語の単語や文章は一切使用しないでください。すべての回答は日本語で記述してください。"
            
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                system=system_prompt,  # システムプロンプトで言語を指定（日本語で記述）
                options={
                    "temperature": 0.2,  # 温度をさらに下げて一貫性を向上
                    "num_predict": 500,  # 最大500トークン
                    "top_p": 0.9,  # top_pを設定して出力を安定化
                }
            )
            
            summary = response.get("response", "").strip()
            
            if not summary:
                summary = "要約生成不可（レスポンスが空）"
            else:
                # マークダウン記法を保持しつつ、不要な部分を削除
                import re
                # 見出し行（①、②で始まる行）を削除（マークダウン見出しが既にある場合は不要）
                lines = summary.split('\n')
                filtered_lines = []
                for line in lines:
                    stripped = line.strip()
                    # 見出し行（①、②で始まる行）をスキップ（マークダウン見出しに置き換える）
                    if stripped and stripped[0] in '①②③④⑤':
                        continue
                    filtered_lines.append(line)
                summary = '\n'.join(filtered_lines)
                
                # 「注記：」「備考：」「III.」「要点まとめ」で始まる行以降を削除
                summary = re.sub(r'\n\s*(注記|備考|III\.|要点まとめ).*$', '', summary, flags=re.MULTILINE | re.DOTALL)
                
                # *で始まる箇条書きを-に統一（マークダウン記法の統一）
                summary = re.sub(r'^\*\s+', '- ', summary, flags=re.MULTILINE)
                
                # 余分な空行を整理（3行以上連続する空行を2行に）
                summary = re.sub(r'\n{3,}', '\n\n', summary)
                summary = summary.strip()
            
            # キャッシュに保存
            if use_cache and doc_id and summary != "要約生成不可（レスポンスが空）":
                try:
                    cache_path = self._get_cache_path(doc_id, section_name)
                    with open(cache_path, "w", encoding="utf-8") as f:
                        f.write(summary)
                except Exception as e:
                    logger.warning(f"キャッシュ保存エラー: {e}")
            
            logger.info(f"要約生成完了: {section_name} ({len(summary)}文字)")
            return summary
        
        except Exception as e:
            logger.error(f"LLM要約エラー: {section_name} - {e}")
            return "要約生成不可（エラー発生）"

