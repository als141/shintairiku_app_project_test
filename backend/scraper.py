import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin
from models import ScrapedContent
from typing import List, Optional

logger = logging.getLogger(__name__)

class BlogScraper:
    """ブログ記事のスクレイピングを行うクラス"""
    
    def __init__(self, url: str):
        self.url = url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def scrape(self) -> ScrapedContent:
        """記事内容と画像URLを取得する"""
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # タイトルの取得
            title = self._extract_title(soup)
            
            # メインコンテンツの取得
            content = self._extract_content(soup)
            
            # 画像URLの取得
            images = self._extract_images(soup)
            
            return ScrapedContent(
                title=title,
                content=content,
                images=images
            )
            
        except requests.RequestException as e:
            logger.error(f"記事の取得に失敗しました: {str(e)}")
            raise Exception(f"記事のスクレイピングに失敗しました: {str(e)}")
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """ページタイトルを抽出する"""
        # h1タグを探す
        h1 = soup.find('h1')
        if h1 and h1.text.strip():
            return h1.text.strip()
        
        # article-titleクラスを持つ要素を探す
        article_title = soup.find(class_=['article-title', 'entry-title', 'post-title'])
        if article_title and article_title.text.strip():
            return article_title.text.strip()
        
        # titleタグから取得
        title_tag = soup.find('title')
        if title_tag and title_tag.text.strip():
            return title_tag.text.strip()
        
        return "タイトル不明"
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """記事本文を抽出する"""
        # 代表的な記事コンテンツを含む要素を探す
        content_selectors = [
            'article', '.article-content', '.entry-content', '.post-content',
            '#content', '.content', 'main', '.main'
        ]
        
        content_element = None
        for selector in content_selectors:
            if selector.startswith('.'):
                content_element = soup.find(class_=selector[1:])
            elif selector.startswith('#'):
                content_element = soup.find(id=selector[1:])
            else:
                content_element = soup.find(selector)
                
            if content_element:
                break
        
        if not content_element:
            content_element = soup
        
        # 不要なタグを削除
        for tag in content_element.find_all(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
        
        # pタグとh2, h3タグからテキストを抽出
        paragraphs = content_element.find_all(['p', 'h2', 'h3'])
        
        if not paragraphs:
            # pタグがない場合はdivやspanなどからテキストを取得
            paragraphs = content_element.find_all(['div', 'span', 'section'])
        
        content = "\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
        
        # コンテンツが空の場合は全テキストを取得
        if not content:
            content = content_element.get_text().strip()
        
        return content
    
    def _extract_images(self, soup: BeautifulSoup) -> List[str]:
        """記事内の画像URLを抽出する"""
        images = []
        
        # 記事コンテンツ内の画像を探す
        content_selectors = [
            'article', '.article-content', '.entry-content', '.post-content',
            '#content', '.content', 'main', '.main'
        ]
        
        content_element = None
        for selector in content_selectors:
            if selector.startswith('.'):
                content_element = soup.find(class_=selector[1:])
            elif selector.startswith('#'):
                content_element = soup.find(id=selector[1:])
            else:
                content_element = soup.find(selector)
                
            if content_element:
                break
        
        if not content_element:
            content_element = soup
        
        # img タグを探す
        for img in content_element.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src:
                # 相対URLを絶対URLに変換
                full_url = urljoin(self.url, src)
                images.append(full_url)
        
        # 画像が見つからない場合はページ全体から探す
        if not images:
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src:
                    full_url = urljoin(self.url, src)
                    images.append(full_url)
        
        # 重複を排除して返す
        return list(dict.fromkeys(images))