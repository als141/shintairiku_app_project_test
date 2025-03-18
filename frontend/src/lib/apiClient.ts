import axios, { AxiosInstance, AxiosError, AxiosRequestConfig, AxiosResponse } from 'axios';

// APIのベースURL - 環境変数またはポート8000（エラーログにあるポート8001ではなく8000に修正）
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001';

// URLを表示（デバッグ用）
console.log(`API_BASE_URL: ${API_BASE_URL}`);

// リトライ設定
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // ms

/**
 * カスタムエラーハンドリング付きAxiosインスタンスを作成
 */
class ApiClient {
  // clientインスタンスを公開（デバッグ用）
  public client: AxiosInstance;
  
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      // タイムアウト設定
      timeout: 30000, // 30秒
    });
    
    // リクエストインターセプター
    this.client.interceptors.request.use(
      (config) => {
        // リクエスト前の処理
        console.log(`🚀 API Request: ${config.method?.toUpperCase()} ${config.url} to ${config.baseURL}`);
        return config;
      },
      (error) => {
        // リクエストエラー
        console.error('❌ Request Error:', error);
        return Promise.reject(error);
      }
    );
    
    // レスポンスインターセプター
    this.client.interceptors.response.use(
      (response) => {
        // レスポンス受信時の処理
        console.log(`✅ API Response: ${response.config.method?.toUpperCase()} ${response.config.url} - Status: ${response.status}`);
        return response;
      },
      async (error: AxiosError) => {
        // レスポンスエラー処理
        const originalRequest = error.config as AxiosRequestConfig & { _retry?: number };
        
        if (!originalRequest) {
          console.error('❌ Response Error (no config):', error.message);
          return Promise.reject(error);
        }
        
        // エラー詳細をログ出力
        console.error(`❌ Response Error: ${originalRequest.method?.toUpperCase()} ${originalRequest.url} - ${error.message}`);
        
        // リトライカウンターの初期化
        if (originalRequest._retry === undefined) {
          originalRequest._retry = 0;
        }
        
        // 特定のエラーでリトライ
        const shouldRetry = (
          // ネットワークエラー
          error.message === 'Network Error' ||
          // タイムアウト
          error.code === 'ECONNABORTED' ||
          // サーバーエラー（500系）
          (error.response && error.response.status >= 500 && error.response.status < 600)
        );
        
        if (shouldRetry && originalRequest._retry < MAX_RETRIES) {
          originalRequest._retry++;
          const delay = RETRY_DELAY * originalRequest._retry;
          
          console.log(`🔄 Retrying request (${originalRequest._retry}/${MAX_RETRIES}) after ${delay}ms...`);
          
          // 指定の遅延後にリトライ
          return new Promise(resolve => {
            setTimeout(() => {
              resolve(this.client(originalRequest));
            }, delay);
          });
        }
        
        // エラーレスポンスの詳細を出力
        if (error.response) {
          console.error('Response data:', error.response.data);
          console.error('Response status:', error.response.status);
          console.error('Response headers:', error.response.headers);
        } else if (error.request) {
          console.error('No response received. Request:', error.request);
        }
        
        return Promise.reject(error);
      }
    );
  }
  
  /**
   * GETリクエスト
   */
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    try {
      const response = await this.client.get<T>(url, config);
      return response.data;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }
  
  /**
   * POSTリクエスト
   */
  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    try {
      const response = await this.client.post<T>(url, data, {
        ...config,
        // POSTリクエストはタイムアウトを長めに設定
        timeout: config?.timeout || 120000, // 2分
      });
      return response.data;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }
  
  /**
   * PUTリクエスト
   */
  async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    try {
      const response = await this.client.put<T>(url, data, config);
      return response.data;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }
  
  /**
   * DELETEリクエスト
   */
  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    try {
      const response = await this.client.delete<T>(url, config);
      return response.data;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }
  
  /**
   * エラーハンドリング
   */
  private handleError(error: any): void {
    if (axios.isAxiosError(error)) {
      // AxiosError固有の処理
      const axiosError = error as AxiosError;
      
      if (axiosError.code === 'ECONNABORTED') {
        console.error('リクエストがタイムアウトしました。サーバーが応答していないか、ネットワーク接続を確認してください。');
      } else if (!axiosError.response) {
        console.error('サーバーに接続できませんでした。バックエンドが起動しているか確認してください。');
      }
    } else {
      // その他のエラー
      console.error('API呼び出し中の予期しないエラー:', error);
    }
  }
  
  /**
   * APIサーバーの状態チェック
   */
  async checkApiStatus(): Promise<{ status: string }> {
    try {
      return await this.get<{ status: string }>('/');
    } catch (error) {
      console.error('APIサーバーに接続できません:', error);
      throw new Error('APIサーバーに接続できません。バックエンドサーバーが起動しているか確認してください。');
    }
  }
}

// シングルトンインスタンスをエクスポート
export const apiClient = new ApiClient();