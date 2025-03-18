import { LineContentRequest, ScrapedContent, LineContentResponse } from '@/types';
import { apiClient } from './apiClient';
import axios, { AxiosError } from 'axios';

/**
 * APIサーバーの状態をチェック
 */
export async function checkApiServer(): Promise<boolean> {
  try {
    await apiClient.checkApiStatus();
    return true;
  } catch (error) {
    console.error('API server check failed:', error);
    return false;
  }
}

/**
 * ブログ記事URLをスクレイピングする
 * @param url スクレイピング対象のURL
 */
export async function scrapeBlogContent(url: string): Promise<ScrapedContent> {
  try {
    // URL検証 - ダミーURL対策
    if (url === 'https://example.com/blog' || url === 'https://example.com') {
      throw new Error('サンプルURLではなく、実際のブログURLを入力してください');
    }
    
    // URLの検証（基本的な形式チェック）
    try {
      new URL(url);
    } catch (e) {
      throw new Error('有効なURLを入力してください');
    }
    
    return await apiClient.post<ScrapedContent>('/api/scrape-blog', { url: url });
  } catch (error: unknown) {
    console.error('Blog scraping failed:', error);
    
    // エラーレスポンスの詳細をログ出力（デバッグ用）
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      if (axiosError.response) {
        console.error('Error response data:', axiosError.response.data);
        console.error('Error response status:', axiosError.response.status);
      }
    }
    
    throw formatError(error, 'ブログ記事のスクレイピングに失敗しました');
  }
}

/**
 * LINE配信記事を生成する
 * @param request LINE配信記事の生成リクエスト
 * @param selectedImages 選択された画像URL配列
 * @param useWebSearch Web検索を使用するかどうか
 */
export async function generateLineContent(
  request: LineContentRequest,
  selectedImages: string[] = [],
  useWebSearch: boolean = true
): Promise<LineContentResponse> {
  try {
    return await apiClient.post<LineContentResponse>('/api/generate-line-content', {
      ...request,
      selected_images: selectedImages,
      use_web_search: useWebSearch
    });
  } catch (error: unknown) {
    console.error('Content generation failed:', error);
    throw formatError(error, 'LINE配信記事の生成に失敗しました');
  }
}

/**
 * エラーメッセージをフォーマット
 */
function formatError(error: unknown, defaultMessage: string): Error {
  let errorMessage = defaultMessage;
  
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<any>;
    if (axiosError.response?.data?.detail) {
      // FastAPIのエラーレスポンス形式
      errorMessage += `: ${axiosError.response.data.detail}`;
    } else if (axiosError.message) {
      // 一般的なエラーメッセージ
      errorMessage += `: ${axiosError.message}`;
    }
  } else if (error instanceof Error) {
    errorMessage += `: ${error.message}`;
  }
  
  return new Error(errorMessage);
}