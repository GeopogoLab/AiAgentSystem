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
   * 请求 TTS 音频（旧版 HTTP，已弃用）
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

  /**
   * 流式 TTS（WebSocket）
   *
   * @param text 要合成的文本
   * @param onChunk 接收到音频块的回调（audioData: Base64字符串, isLast: 是否最后一块）
   * @param onError 错误回调
   * @returns 取消函数（可调用以中断连接）
   */
  static streamTTS(
    text: string,
    onChunk: (audioData: string, isLast: boolean) => void,
    onError?: (error: string) => void
  ): () => void {
    const apiBase = API_BASE_URL;
    const wsBase = apiBase.replace(/^http/i, (match) =>
      match.toLowerCase() === 'https' ? 'wss' : 'ws'
    );
    const wsUrl = `${wsBase.replace(/\/$/, '')}/ws/tts`;

    const ws = new WebSocket(wsUrl);
    let cancelled = false;

    ws.onopen = () => {
      if (cancelled) {
        ws.close();
        return;
      }
      // 发送 TTS 请求
      ws.send(JSON.stringify({ text, format: 'mp3' }));
    };

    ws.onmessage = (event) => {
      if (cancelled) return;

      try {
        const data = JSON.parse(event.data);

        if (data.message_type === 'error') {
          onError?.(data.error);
          ws.close();
          return;
        }

        if (data.message_type === 'audio_chunk') {
          const isLast = data.is_final === true;
          onChunk(data.audio_data, isLast);

          if (isLast) {
            ws.close();
          }
        }
      } catch (error) {
        console.error('Failed to parse TTS message:', error);
        onError?.('Failed to parse TTS response');
        ws.close();
      }
    };

    ws.onerror = (event) => {
      if (cancelled) return;
      console.error('TTS WebSocket error:', event);
      onError?.('WebSocket connection failed');
      ws.close();
    };

    ws.onclose = () => {
      // Connection closed
    };

    // 返回取消函数
    return () => {
      cancelled = true;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }
}
