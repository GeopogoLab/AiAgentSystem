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
  placed_at: string;
  current_stage: ProductionStage;
  current_stage_label: string;
  eta_seconds?: number | null;
  total_duration_seconds: number;
  is_completed: boolean;
  timeline: ProductionTimelineItem[];
  queue_position?: number | null;
  total_orders?: number | null;
  drink_name?: string | null;
  size?: string | null;
  sugar?: string | null;
  ice?: string | null;
  toppings?: string[];
}

export interface ProductionQueueSnapshot {
  generated_at: string;
  active_orders: OrderProgress[];
  completed_orders: OrderProgress[];
}

export interface ApiError {
  message: string;
}
