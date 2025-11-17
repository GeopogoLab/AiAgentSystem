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
  mode?: 'online' | 'offline';
}

// API 响应
export interface TalkResponse {
  assistant_reply: string;
  order_state: OrderState;
  order_status: OrderStatus;
  order_id?: number;
  reply_mode?: 'online' | 'offline';
  order_total?: number | null;
}

export type ProductionStage = 'queued' | 'brewing' | 'sealing' | 'ready';

export interface ProductionTimelineItem {
  stage: ProductionStage;
  label: string;
  started_at: string;
  finished_at?: string | null;
  duration_seconds?: number | null;
}

export interface OrderProgress {
  order_id: number;
  current_stage: ProductionStage;
  current_stage_label: string;
  eta_seconds?: number | null;
  total_duration_seconds: number;
  is_completed: boolean;
  timeline: ProductionTimelineItem[];
  queue_position?: number | null;
  total_orders?: number | null;
}

export interface ProgressChatResponse {
  answer: string;
  progress?: OrderProgress | null;
  mode?: 'online' | 'offline';
  order_id?: number | null;
}

export interface ProgressHistoryResponse {
  order_id: number;
  history: Message[];
}

export interface ProgressSessionHistoryResponse {
  session_id: string;
  history: Message[];
}

export interface ProductionQueueSnapshot {
  generated_at: string;
  active_orders: OrderProgress[];
  completed_orders: OrderProgress[];
}

export interface TTSApiResponse {
  audio_url?: string;
  audio_base64?: string;
  voice: string;
  format: string;
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
