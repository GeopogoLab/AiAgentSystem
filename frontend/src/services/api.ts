import { TalkResponse, SessionState } from '../types';

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
   * 发送语音文件
   */
  static async sendAudio(sessionId: string, audioBlob: Blob): Promise<TalkResponse> {
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('audio', audioBlob, 'audio.webm');

    const response = await fetch(`${API_BASE_URL}/talk`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Failed to send audio');
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
}
