import {
  TalkResponse,
  SessionState,
  OrderProgress,
  ProgressChatResponse,
  ProgressHistoryResponse,
  ProgressSessionHistoryResponse,
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
   * 询问制作进度的 AI
   */
  static async askOrderProgress(orderId: number, question: string, sessionId?: string): Promise<ProgressChatResponse> {
    const derivedSession = sessionId ?? `progress-order-${orderId}`;
    return ApiService.askProgress(derivedSession, question, orderId);
  }

  /**
   * 会话级别的进度问答
   */
  static async askProgress(sessionId: string, question: string, orderId?: number | null): Promise<ProgressChatResponse> {
    const payload: Record<string, unknown> = {
      session_id: sessionId,
      question,
    };
    if (orderId) {
      payload.order_id = orderId;
    }

    const response = await fetch(`${API_BASE_URL}/progress/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error('Failed to ask progress');
    }

    return response.json();
  }

  /**
   * 获取进度助手历史
   */
  static async getProgressHistory(orderId: number): Promise<ProgressHistoryResponse> {
    const response = await fetch(`${API_BASE_URL}/orders/${orderId}/progress-history`);

    if (!response.ok) {
      throw new Error('Failed to get progress history');
    }

    return response.json();
  }

  /**
   * 获取会话的进度助手历史
   */
  static async getProgressSessionHistory(sessionId: string): Promise<ProgressSessionHistoryResponse> {
    const response = await fetch(`${API_BASE_URL}/progress/history/${sessionId}`);

    if (!response.ok) {
      throw new Error('Failed to get progress session history');
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
