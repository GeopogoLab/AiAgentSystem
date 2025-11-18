import {
  TalkResponse,
  SessionState,
  OrderProgress,
  ProductionQueueSnapshot,
  TTSApiResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export class ApiService {
  /**
   * 发送文本消息
   */
  static async sendText(sessionId: string, text: string): Promise<TalkResponse> {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('text', text);

    const response = await fetch(`${API_BASE_URL}/text`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Failed to send text');
    }

    return response.json();
  }

  /**
   * 重置会话
   */
  static async resetSession(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/reset/${sessionId}`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error('Failed to reset session');
    }
  }

  /**
   * 获取会话状态
   */
  static async getSession(sessionId: string): Promise<SessionState> {
    const response = await fetch(`${API_BASE_URL}/session/${sessionId}`);

    if (!response.ok) {
      throw new Error('Failed to get session');
    }

    return response.json();
  }

  /**
   * 获取所有订单
   */
  static async getAllOrders(limit: number = 100): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/orders?limit=${limit}`);

    if (!response.ok) {
      throw new Error('Failed to get orders');
    }

    return response.json();
  }

  /**
   * 获取单个订单
   */
  static async getOrder(orderId: number): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/orders/${orderId}`);

    if (!response.ok) {
      throw new Error('Failed to get order');
    }

    return response.json();
  }

  /**
   * 获取订单制作进度
   */
  static async getOrderStatus(orderId: number): Promise<OrderProgress> {
    const response = await fetch(`${API_BASE_URL}/orders/${orderId}/status`);

    if (!response.ok) {
      throw new Error('Failed to get order status');
    }

    return response.json();
  }

  /**
   * 获取当前排队面板
   */
  static async getProductionQueue(): Promise<ProductionQueueSnapshot> {
    const response = await fetch(`${API_BASE_URL}/production/queue`);

    if (!response.ok) {
      throw new Error('Failed to load production queue');
    }

    return response.json();
  }

  /**
   * 请求 TTS 音频
   */
  static async requestTTS(text: string): Promise<TTSApiResponse> {
    const response = await fetch(`${API_BASE_URL}/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      throw new Error('Failed to request TTS');
    }

    return response.json();
  }
}
