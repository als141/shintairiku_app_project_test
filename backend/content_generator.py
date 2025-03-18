import os
import logging
from typing import List, Optional, Dict, Any
import openai
from models import LineContentRequest, ScrapedContent, GeneratedContent
from web_search import WebSearchClient

logger = logging.getLogger(__name__)

class ContentGenerator:
    """OpenAI APIを使用してLINE配信用のコンテンツを生成するクラス"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        ContentGenerator クラスの初期化
        
        Args:
            api_key: OpenAI API キー。None の場合は環境変数から取得
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API キーが設定されていません")
        
        openai.api_key = self.api_key
        
        # Web検索クライアントの初期化
        self.web_search_client = WebSearchClient(api_key=self.api_key)
    
    def generate_line_content(
        self, 
        request: LineContentRequest, 
        scraped_content: ScrapedContent,
        selected_images: List[str] = [],
        use_web_search: bool = True
    ) -> List[GeneratedContent]:
        """
        LINE配信用のコンテンツを生成する
        
        Args:
            request: LINE配信記事のリクエストパラメータ
            scraped_content: スクレイピングされたブログコンテンツ
            selected_images: 選択された画像URLのリスト
            use_web_search: Web検索APIを使用するかどうか
            
        Returns:
            生成されたコンテンツの選択肢のリスト
        """
        # Web検索を使用して追加情報を取得
        web_search_info = {}
        if use_web_search:
            try:
                # 記事のタイトルやキーワードからトピックを抽出
                topic = scraped_content.title
                
                # Web検索を実行して関連情報を取得
                web_search_info = self.web_search_client.enhance_content_with_web_search(
                    request=request,
                    topic=topic
                )
                
                logger.info(f"Web検索結果を取得しました: {web_search_info.get('search_results', {}).get('summary', '')[:100]}...")
                
            except Exception as e:
                logger.warning(f"Web検索中にエラーが発生しましたが、プロセスは続行します: {str(e)}")
                # エラーがあっても処理を続行
        
        # プロンプトを構築
        prompt = self._build_prompt(request, scraped_content, selected_images, web_search_info)
        
        # 3つのバリエーションを生成
        variations = []
        
        try:
            client = openai.OpenAI(api_key=self.api_key)
            
            for i in range(3):
                # OpenAI API を呼び出してコンテンツを生成
                response = client.chat.completions.create(
                    model="gpt-4o",  # 最新のモデルに変更
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"LINE配信記事のバリエーション{i+1}を生成してください。"}
                    ],
                    max_tokens=800,
                    temperature=0.7 + (i * 0.1),  # バリエーションごとに少し変化をつける
                    top_p=0.95,
                    frequency_penalty=0.0,
                    presence_penalty=0.0
                )
                
                content = response.choices[0].message.content
                
                # マークダウン形式の整形（複数画像対応）
                markdown = self._format_as_markdown(content, selected_images, request.blog_url)
                
                variations.append(
                    GeneratedContent(
                        content=content,
                        markdown=markdown
                    )
                )
                
        except Exception as e:
            logger.error(f"コンテンツ生成中にエラーが発生しました: {str(e)}")
            raise Exception(f"OpenAI APIでのコンテンツ生成に失敗しました: {str(e)}")
        
        return variations
    
    def _build_prompt(
        self, 
        request: LineContentRequest, 
        scraped_content: ScrapedContent,
        selected_images: List[str] = [],
        web_search_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        OpenAI APIに送信するプロンプトを構築する
        
        Args:
            request: LINE配信記事のリクエストパラメータ
            scraped_content: スクレイピングされたブログコンテンツ
            selected_images: 選択された画像URLのリスト
            web_search_info: Web検索から取得した追加情報 (任意)
            
        Returns:
            構築されたプロンプト
        """
        # イメージ指示
        image_instruction = ""
        if selected_images:
            if len(selected_images) == 1:
                image_instruction = "記事には1枚の添付画像があります。画像について言及せず、テキストのみを生成してください。"
            else:
                image_instruction = f"記事には{len(selected_images)}枚の添付画像があります。画像について言及せず、テキストのみを生成してください。"
        
        # 参照テンプレートがある場合
        template_instruction = ""
        if request.reference_template:
            template_instruction = f"""
            以下のテンプレートを参考にして、全体的な文調とフォーマットを模倣してください：
            
            {request.reference_template}
            """
        
        # Web検索情報がある場合
        web_search_section = ""
        if web_search_info and 'search_results' in web_search_info and 'summary' in web_search_info['search_results']:
            web_search_section = f"""
            # Web検索で収集した追加情報
            
            {web_search_info['search_results']['summary']}
            
            この情報を適切に利用して、記事の内容を充実させてください。ただし、過度に専門的になりすぎず、LINE配信の読みやすさを保ってください。
            """
            
        # プロンプトを構築
        prompt = f"""
        あなたは企業のLINE配信記事のプロの作成者です。元のブログ記事をLINE配信向けに最適化された記事に書き換える必要があります。
        
        # 企業情報
        - 企業名: {request.company_name}
        - 企業URL: {request.company_url}
        
        # 元のブログ記事
        タイトル: {scraped_content.title}
        
        コンテンツ:
        {scraped_content.content[:1500]}  # 長すぎる場合は制限
        
        {web_search_section}
        
        # LINE配信記事の要件
        - 記事の長さ: {request.content_length}
        - 文体: {request.writing_style}（丁寧/カジュアル）
        - 改行位置: {request.line_break_style}
        - かっこの種類: {request.bracket_type}
        - 敬称: {request.honorific}
        - 子どもの敬称: {request.child_honorific}
        - 感情を誘発させる文頭: {"必要" if request.add_emotional_intro else "不要"}
        - 絵文字の種類: {request.emoji_types}
        - 絵文字の量: {request.emoji_count}個程度/配信
        - 箇条書き記号: {request.bullet_point}
        - 日時フォーマット: {request.date_format}
        - 挨拶文: {request.greeting_text}
        - 元記事への誘導: {request.redirect_text}
        - 画像: {"あり (" + str(len(selected_images)) + "枚)" if selected_images else "なし"}
        
        {image_instruction}
        
        {template_instruction}
        
        # 指示
        1. オリジナルのブログコンテンツの主要なメッセージを保持しながら、LINEのカジュアルな配信向けに最適化してください。
        2. 指定された絵文字を適切な場所に使い、親しみやすさを演出してください。
        3. 記事の最後には必ず元の記事へのリンク誘導文を入れてください。
        4. 顧客目線で、読者の興味を引く内容に仕上げてください。
        5. 文字数は指定された長さにしてください。
        6. 必要に応じて箇条書きを使って見やすくしてください。
        7. Web検索から得た追加情報がある場合は、それも活用して記事の価値を高めてください。ただし、情報源の詳細なURLなどは含めないでください。
        
        最終的な出力は、LINEで配信するテキストのみを含めてください。マークダウン形式は必要ありません。
        """
        
        return prompt
    
    def _format_as_markdown(
        self, 
        content: str, 
        selected_images: List[str] = [],
        blog_url: Optional[str] = None
    ) -> str:
        """
        生成されたコンテンツをマークダウン形式に整形する
        
        Args:
            content: 生成されたテキストコンテンツ
            selected_images: 選択された画像URLのリスト
            blog_url: 元のブログ記事URL (任意)
            
        Returns:
            マークダウン形式のコンテンツ
        """
        markdown = content
        
        # 画像がある場合は追加
        for i, image_url in enumerate(selected_images):
            markdown += f"\n\n![記事画像 {i+1}]({image_url})"
        
        # ブログURLがある場合は追加
        if blog_url:
            markdown += f"\n\n[詳細を見る]({blog_url})"
        
        return markdown