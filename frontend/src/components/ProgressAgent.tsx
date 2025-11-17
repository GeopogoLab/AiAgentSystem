import { useEffect, useMemo, useRef, useState } from 'react';
import { ApiService } from '../services/api';
import { OrderProgress, Message, ProductionQueueSnapshot } from '../types';
import { Message as MessageItem } from './Message';
import { TextInput } from './TextInput';

const STAGE_LABELS: Record<string, string> = {
  queued: '排队中',
  brewing: '制作中',
  sealing: '封杯打包',
  ready: '可取餐',
};

const DEFAULT_GREETING: Message = {
  role: 'assistant',
  content: '制作进度助手就绪，我会同步全店排队面板。想查询某个订单，请告诉我编号；也可以直接询问现在排了几单。',
  mode: 'online',
};

interface ProgressAgentProps {
  sessionId: string;
  activeOrderId?: number | null;
  queueSnapshot?: ProductionQueueSnapshot | null;
}

export function ProgressAgent({ sessionId, activeOrderId, queueSnapshot }: ProgressAgentProps) {
  const [messages, setMessages] = useState<Message[]>([DEFAULT_GREETING]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [agentProgress, setAgentProgress] = useState<OrderProgress | null>(null);
  const [liveProgress, setLiveProgress] = useState<OrderProgress | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const queueProgress = useMemo(() => {
    if (!activeOrderId || !queueSnapshot) return null;
    return [...queueSnapshot.active_orders, ...queueSnapshot.completed_orders].find(
      (order) => order.order_id === activeOrderId,
    ) ?? null;
  }, [activeOrderId, queueSnapshot]);

  useEffect(() => {
    let cancelled = false;
    const loadHistory = async () => {
      try {
        const data = await ApiService.getProgressSessionHistory(sessionId);
        if (cancelled) return;
        if (data.history && data.history.length > 0) {
          setMessages(data.history);
        } else {
          setMessages([DEFAULT_GREETING]);
        }
      } catch (error) {
        console.error('Failed to load progress history', error);
        if (!cancelled) {
          setMessages([
            {
              role: 'assistant',
              content: '暂时无法加载历史，稍后再试。',
              mode: 'offline',
            },
          ]);
        }
      }
    };
    loadHistory();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (!activeOrderId) {
      setLiveProgress(null);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const wsBase = apiBase.replace(/^http/i, (match) =>
      match.toLowerCase() === 'https' ? 'wss' : 'ws',
    );
    const ws = new WebSocket(`${wsBase.replace(/\/$/, '')}/ws/orders/${activeOrderId}/status`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.error) {
          return;
        }
        setLiveProgress(data);
      } catch (err) {
        console.error('Failed to parse progress websocket payload', err);
      }
    };

    ws.onerror = (event) => {
      console.error('Progress websocket error', event);
    };

    ws.onclose = () => {
      wsRef.current = null;
    };

    return () => {
      ws.close();
    };
  }, [activeOrderId]);

  useEffect(() => {
    if (queueProgress) {
      setAgentProgress((current) =>
        current && current.order_id !== queueProgress.order_id ? current : queueProgress,
      );
    }
  }, [queueProgress]);

  const displayProgress = liveProgress ?? agentProgress ?? queueProgress ?? null;

  const handleQuestion = async (text: string) => {
    if (!text.trim()) {
      return;
    }

    setMessages((prev) => [...prev, { role: 'user', content: text, mode: 'online' }]);
    setIsProcessing(true);

    try {
      const response = await ApiService.askProgress(sessionId, text, activeOrderId ?? undefined);
      const answerMode = response.mode === 'offline' ? 'offline' : 'online';
      pushAssistantMessage(response.answer, answerMode);
      setAgentProgress(response.progress ?? null);
    } catch (error) {
      console.error('Failed to ask progress', error);
      pushAssistantMessage('无法获取制作进度，请稍后再试。', 'offline');
    } finally {
      setIsProcessing(false);
    }
  };

  const pushAssistantMessage = (content: string, mode: 'online' | 'offline' = 'online') => {
    setMessages((prev) => [...prev, { role: 'assistant', content, mode }]);
  };

  return (
    <div className="mt-6 rounded-2xl bg-white p-6 shadow-xl">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-xl font-semibold text-primary-600">制作进度助手</h3>
          <p className="text-sm text-gray-500">
            实时参考排队面板，回答“现在排到哪”和“我的订单还要多久”
          </p>
        </div>
        <div className="text-sm text-gray-500">{renderQueueSummary(queueSnapshot)}</div>
      </div>

      <div
        ref={containerRef}
        className="h-72 overflow-y-auto rounded-xl border border-gray-200 bg-gray-50 p-4"
      >
        {displayProgress && (
          <div className="mb-4 rounded-xl bg-white p-3 shadow-sm">
            <div className="text-sm font-semibold text-primary-600">实时进度</div>
            <div className="text-sm text-gray-700">{renderProgressHint(displayProgress)}</div>
          </div>
        )}
        {messages.map((message, index) => (
          <MessageItem key={index} message={message} />
        ))}
      </div>

      <div className="mt-4">
        <TextInput
          onSend={handleQuestion}
          disabled={isProcessing}
          placeholder="例如：“订单 #12 还要多久？” 或 “现在排了几单？”"
        />
      </div>
    </div>
  );
}

function renderProgressHint(progress: OrderProgress | null) {
  if (!progress) return '';
  if (progress.is_completed) {
    return `订单 #${progress.order_id} 已完成，可以取餐。`;
  }
  const stageLabel = STAGE_LABELS[progress.current_stage] || progress.current_stage_label;
  const details: string[] = [];
  if (progress.queue_position && progress.total_orders) {
    details.push(`排在第 ${progress.queue_position}/${progress.total_orders} 位`);
  }
  if (progress.eta_seconds) {
    details.push(`预计约 ${Math.max(1, Math.ceil(progress.eta_seconds / 60))} 分钟`);
  }
  const extra = details.length ? `（${details.join('，')}）` : '';
  return `订单 #${progress.order_id} 正在 ${stageLabel}${extra}`.trim();
}

function renderQueueSummary(snapshot?: ProductionQueueSnapshot | null) {
  if (!snapshot) {
    return '等待排队数据';
  }
  const active = snapshot.active_orders.length;
  const completed = snapshot.completed_orders.length;
  if (active === 0) {
    return `暂无排队 · 最近完成 ${completed} 单`;
  }
  return `排队中 ${active} 单 · 最近完成 ${completed} 单`;
}
