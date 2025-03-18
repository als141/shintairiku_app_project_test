from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Literal


class LineContentRequest(BaseModel):
    """LINE配信記事生成のリクエストモデル"""
    company_name: str = Field(..., description="会社の正式名称")
    company_url: HttpUrl = Field(..., description="企業のサイトトップURL")
    blog_url: HttpUrl = Field(..., description="LINE記事用に書き直したい元のブログ記事のURL")
    redirect_text: str = Field(
        "詳しく知りたい方は、下のリンクor画像をタップ👇✨", 
        description="元のブログ記事のURLへの誘導文言"
    )
    bracket_type: str = Field("【】", description="イベント名の「かっこ」の種類")
    honorific: str = Field("様", description="敬称（様orさまorさん）")
    child_honorific: str = Field("お子様", description="子どもの敬称")
    fixed_format: Optional[str] = Field(None, description="定型文があればそのフォーマット")
    add_emotional_intro: bool = Field(True, description="感情を誘発させる文章を文頭につけるか")
    writing_style: Literal["丁寧", "カジュアル"] = Field("カジュアル", description="文体")
    line_break_style: Literal["読みやすさ重視", "短め", "長め"] = Field("読みやすさ重視", description="文章中の改行位置")
    content_length: str = Field("200文字前後", description="文章量")
    date_format: str = Field("MM月DD日(ddd), HH:MM", description="日時の表記フォーマット")
    bullet_point: str = Field("🟧", description="箇条書きの文頭")
    emoji_types: str = Field("🏡✨👇🎉😊💁‍♂️🎁🌱🌿", description="絵文字の種類")
    emoji_count: str = Field("4~5", description="絵文字の量（1配信あたり）")
    greeting_text: str = Field("{name}さま　こんばんは！", description="かならずつける挨拶文")
    reference_template: Optional[str] = Field(None, description="作成する記事の全体的な文調の参考にするテンプレート等")


class ScrapedContent(BaseModel):
    """スクレイピングされたコンテンツ"""
    title: str
    content: str
    images: List[str]


class GeneratedContent(BaseModel):
    """生成されたLINE配信コンテンツ"""
    content: str
    markdown: str


class LineContentResponse(BaseModel):
    """LINE配信記事生成のレスポンスモデル"""
    scraped_content: ScrapedContent
    generated_options: List[GeneratedContent]