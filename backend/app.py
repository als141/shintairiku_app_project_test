import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl, Field, validator
import validators
from fastapi.encoders import jsonable_encoder

from models import LineContentRequest, LineContentResponse, ScrapedContent, GeneratedContent
from scraper import BlogScraper
from content_generator import ContentGenerator
from web_search import WebSearchClient

# 環境変数の読み込み
load_dotenv()

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI アプリケーションの初期化
app = FastAPI(
    title="コンテンツ自動生成API",
    description="ブログ記事、Instagram投稿、LINE配信記事を自動生成するAPIサービス",
    version="1.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開発時は全てのオリジンを許可（本番環境では適切に制限する）
    allow_credentials=True,
    allow_methods=["*"],  # 全てのHTTPメソッドを許可
    allow_headers=["*"],  # 全てのヘッダーを許可
    expose_headers=["*"],  # レスポンスヘッダーを公開
    max_age=600,  # プリフライトリクエストのキャッシュ時間（秒）
)

# OpenAI API キーの取得
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    logger.warning("OPENAI_API_KEYが設定されていません")


# ContentGeneratorの依存関係
def get_content_generator():
    return ContentGenerator(api_key=openai_api_key)


# グローバルなエラーハンドリング
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Global error handler caught: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"サーバーエラーが発生しました: {str(exc)}"}
    )


# URLリクエスト用のモデル（より柔軟なバリデーション）
class UrlRequest(BaseModel):
    url: str = Field(..., description="スクレイピング対象のURL")
    
    @validator('url')
    def validate_url(cls, v):
        if not validators.url(v):
            raise ValueError("有効なURLを入力してください")
        return v


# LINE生成リクエスト統合モデル（複数画像対応）
class LineGenerateRequest(BaseModel):
    """
    フロントエンドからのリクエストに合わせた統合モデル
    """
    # LineContentRequestのすべてのフィールド
    company_name: str = Field(..., description="会社の正式名称")
    company_url: str = Field(..., description="企業のサイトトップURL")
    blog_url: str = Field(..., description="LINE記事用に書き直したい元のブログ記事のURL")
    redirect_text: str = Field(
        "詳しく知りたい方は、下のリンクor画像をタップ👇✨", 
        description="元のブログ記事のURLへの誘導文言"
    )
    bracket_type: str = Field("【】", description="イベント名の「かっこ」の種類")
    honorific: str = Field("様", description="敬称（様orさまorさん）")
    child_honorific: str = Field("お子様", description="子どもの敬称")
    fixed_format: Optional[str] = Field(None, description="定型文があればそのフォーマット")
    add_emotional_intro: bool = Field(True, description="感情を誘発させる文章を文頭につけるか")
    writing_style: str = Field("カジュアル", description="文体")
    line_break_style: str = Field("読みやすさ重視", description="文章中の改行位置")
    content_length: str = Field("200文字前後", description="文章量")
    date_format: str = Field("MM月DD日(ddd), HH:MM", description="日時の表記フォーマット")
    bullet_point: str = Field("🟧", description="箇条書きの文頭")
    emoji_types: str = Field("🏡✨👇🎉😊💁‍♂️🎁🌱🌿", description="絵文字の種類")
    emoji_count: str = Field("4~5", description="絵文字の量（1配信あたり）")
    greeting_text: str = Field("{name}さま　こんばんは！", description="かならずつける挨拶文")
    reference_template: Optional[str] = Field(None, description="作成する記事の全体的な文調の参考にするテンプレート等")
    
    # 追加フィールド
    selected_images: List[str] = Field(default_factory=list, description="選択された画像URLのリスト")
    use_web_search: bool = Field(True, description="Web検索を使用するかどうか")
    
    @validator('blog_url')
    def validate_blog_url(cls, v):
        if not validators.url(v):
            raise ValueError("有効なブログURLを入力してください")
        return v
    
    @validator('company_url')
    def validate_company_url(cls, v):
        if not validators.url(v):
            raise ValueError("有効な企業URLを入力してください")
        return v


@app.get("/")
async def root():
    """
    APIサーバーの状態チェック用エンドポイント
    """
    return {"status": "online", "message": "コンテンツ自動生成APIへようこそ"}


@app.options("/{path:path}")
async def options_route(path: str):
    """
    プリフライトリクエスト用のオプションルート
    """
    return {}


@app.post("/api/scrape-blog")
async def scrape_blog(request: UrlRequest):
    """
    ブログ記事URLをスクレイピングし、コンテンツと画像を取得する
    """
    try:
        url = request.url
        logger.info(f"スクレイピング開始: {url}")
        scraper = BlogScraper(url)
        content = scraper.scrape()
        logger.info(f"スクレイピング完了: {url} - タイトル: {content.title[:30]}...")
        return content
    except ValueError as e:
        # URLバリデーションエラー
        logger.error(f"URLバリデーションエラー: {str(e)}")
        raise HTTPException(status_code=422, detail=f"無効なURL: {str(e)}")
    except Exception as e:
        logger.error(f"スクレイピングエラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ブログ記事のスクレイピングに失敗しました: {str(e)}")


@app.post("/api/generate-line-content", response_model=LineContentResponse)
async def generate_line_content(
    # リクエストボディは統合モデルとして受け取る
    request: LineGenerateRequest = Body(...),
    content_generator: ContentGenerator = Depends(get_content_generator)
):
    """
    LINE配信用のコンテンツを生成する（統合モデル版）
    
    フロントエンドから送信される形式に合わせて、単一のリクエストモデルでパラメータを受け取る
    """
    try:
        # 受信したリクエストの内容をログに出力（デバッグ用）
        request_dict = jsonable_encoder(request)
        selected_images = request.selected_images
        use_web_search = request.use_web_search
        
        logger.info(f"LINE記事生成開始: URL={request.blog_url}, WebSearch={use_web_search}, 画像数={len(selected_images)}")
        
        # 元のブログ記事をスクレイピング
        try:
            scraper = BlogScraper(str(request.blog_url))
            scraped_content = scraper.scrape()
        except Exception as e:
            logger.error(f"スクレイピングエラー: {str(e)}")
            raise HTTPException(status_code=500, detail=f"記事のスクレイピングに失敗しました: {str(e)}")
        
        logger.info(f"スクレイピング完了: {len(scraped_content.content)} 文字, {len(scraped_content.images)} 画像")
        
        # LineContentRequestのインスタンスを作成
        line_request = LineContentRequest(
            company_name=request.company_name,
            company_url=request.company_url,
            blog_url=request.blog_url,
            redirect_text=request.redirect_text,
            bracket_type=request.bracket_type,
            honorific=request.honorific,
            child_honorific=request.child_honorific,
            fixed_format=request.fixed_format,
            add_emotional_intro=request.add_emotional_intro,
            writing_style=request.writing_style,
            line_break_style=request.line_break_style,
            content_length=request.content_length,
            date_format=request.date_format,
            bullet_point=request.bullet_point,
            emoji_types=request.emoji_types,
            emoji_count=request.emoji_count,
            greeting_text=request.greeting_text,
            reference_template=request.reference_template
        )
        
        # LINE配信コンテンツの生成（複数画像と Web検索機能を利用）
        generated_options = content_generator.generate_line_content(
            request=line_request,
            scraped_content=scraped_content,
            selected_images=selected_images,
            use_web_search=use_web_search
        )
        
        logger.info(f"生成完了: {len(generated_options)} 個のコンテンツオプション")
        
        return LineContentResponse(
            scraped_content=scraped_content,
            generated_options=generated_options
        )
    
    except ValueError as e:
        # バリデーションエラー
        logger.error(f"バリデーションエラー: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
        
    except Exception as e:
        logger.error(f"コンテンツ生成エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LINE配信コンテンツの生成に失敗しました: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)