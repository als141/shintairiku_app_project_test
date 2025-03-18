import os
import logging
from typing import List, Optional, Dict, Any
import openai
from models import LineContentRequest

logger = logging.getLogger(__name__)

class WebSearchClient:
    """OpenAIのWebSearch APIを使用してウェブ検索を行うクラス"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        WebSearchClient クラスの初期化
        
        Args:
            api_key: OpenAI API キー。None の場合は環境変数から取得
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API キーが設定されていません")
        
        openai.api_key = self.api_key
    
    def search_related_info(self, query: str, country: str = "JP") -> Dict[str, Any]:
        """
        指定したクエリに関連する情報をWebSearch APIで検索する
        
        Args:
            query: 検索クエリ
            country: 検索を行う国のコード (デフォルト: "JP")
            
        Returns:
            検索結果の情報
        """
        try:
            client = openai.OpenAI(api_key=self.api_key)
            
            # Responses APIを使用してWeb検索を実行
            response = client.responses.create(
                model="gpt-4o",
                tools=[{
                    "type": "web_search_preview",
                    "user_location": {
                        "type": "approximate",
                        "country": country
                    },
                    "search_context_size": "medium"
                }],
                input=f"以下のトピックに関する最新情報を詳しく調査してください。情報は日本語で要約し、情報源も含めてください。検索対象: {query}",
                temperature=0.7,
                top_p=0.95
            )
            
            # レスポンスから必要な情報を抽出
            result = {
                "search_results": []
            }
            
            # テキスト出力を取得
            for item in response.output:
                if item.type == "message":
                    for content in item.content:
                        if content.type == "output_text":
                            result["summary"] = content.text
                            
                            # 引用URLを抽出
                            if hasattr(content, 'annotations'):
                                citations = []
                                for annotation in content.annotations:
                                    if annotation.type == "url_citation":
                                        citations.append({
                                            "url": annotation.url,
                                            "title": annotation.title if hasattr(annotation, 'title') else ""
                                        })
                                result["citations"] = citations
            
            return result
            
        except Exception as e:
            logger.error(f"Web検索中にエラーが発生しました: {str(e)}")
            return {"error": str(e), "summary": "", "citations": []}
    
    def enhance_content_with_web_search(
        self, 
        request: LineContentRequest, 
        topic: str
    ) -> Dict[str, Any]:
        """
        指定したトピックに関連する情報を検索し、コンテンツを強化する
        
        Args:
            request: LINE配信記事のリクエストパラメータ
            topic: 検索するトピック
            
        Returns:
            検索結果を含めた強化情報
        """
        # コンテンツ関連の検索クエリを構築
        search_query = f"{request.company_name} {topic}"
        
        # Web検索を実行
        search_results = self.search_related_info(search_query)
        
        return {
            "topic": topic,
            "search_results": search_results
        }