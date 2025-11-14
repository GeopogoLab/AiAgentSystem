// 订单状态
export interface OrderState {
  drink_name: string | null;
  size: string | null;
  sugar: string | null;
  ice: string | null;
  toppings: string[];
  notes: string | null;
  is_complete: boolean;
}

// 订单状态枚举
export enum OrderStatus {
  COLLECTING = 'collecting',
  CONFIRMING = 'confirming',
  SAVED = 'saved',
}

// 对话消息
export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

// API 响应
export interface TalkResponse {
  assistant_reply: string;
  order_state: OrderState;
  order_status: OrderStatus;
  order_id?: number;
}

// 会话状态
export interface SessionState {
  session_id: string;
  history: Message[];
  order_state: OrderState;
  status: OrderStatus;
}

// 模式类型
export type InputMode = 'text' | 'voice';
