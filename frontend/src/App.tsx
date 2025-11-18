import { useEffect, useMemo, useState } from 'react';
import { Activity, Clock4, RotateCcw } from 'lucide-react';
import { ChatContainer } from './components/ChatContainer';
import { OrderInfo } from './components/OrderInfo';
import { ModeSelector } from './components/ModeSelector';
import { TextInput } from './components/TextInput';
import { VoiceInput } from './components/VoiceInput';
import { ProductionBoard } from './components/ProductionBoard';
import { ApiService } from './services/api';
import { generateSessionId } from './services/utils';
import {
  Message,
  OrderState,
  InputMode,
  OrderStatus,
  TalkResponse,
  ProductionQueueSnapshot,
  OrderMetadata,
} from './types';

const createInitialOrderState = (): OrderState => ({
  drink_name: null,
  size: null,
  sugar: null,
  ice: null,
  toppings: [],
  notes: null,
  is_complete: false,
});

const ORDER_STATUS_MESSAGES: Record<OrderStatus, string> = {
  [OrderStatus.COLLECTING]: '正在为您整理订单信息',
  [OrderStatus.CONFIRMING]: '请确认订单内容是否正确',
  [OrderStatus.SAVED]: '订单已保存，稍等片刻即可取餐',
};
const MODEL_BADGE = import.meta.env.VITE_MODEL_BADGE ?? 'OpenRouter · Llama 3.3 70B';

function App() {
  const [sessionId] = useState(() => generateSessionId());
  const [mode, setMode] = useState<InputMode>('text');
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: '您好！欢迎光临，我可以帮您点单。请告诉我您想要什么饮品～',
      mode: 'online',
    },
  ]);
  const [orderState, setOrderState] = useState<OrderState>(createInitialOrderState);
  const [status, setStatus] = useState<string>('');
  const [activeOrderId, setActiveOrderId] = useState<number | null>(null);
  const [orderTotal, setOrderTotal] = useState<number | null>(null);
  const [orderMeta, setOrderMeta] = useState<OrderMetadata | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [queueSnapshot, setQueueSnapshot] = useState<ProductionQueueSnapshot | null>(null);

  const queueMetrics = useMemo(() => {
    const activeCount = queueSnapshot?.active_orders?.length ?? 0;
    const completed = queueSnapshot?.completed_orders?.length ?? 0;
    const nextOrder = queueSnapshot?.active_orders?.[0];
    return {
      active: activeCount,
      completed,
      eta: nextOrder?.eta_seconds
        ? `${Math.max(1, Math.ceil(nextOrder.eta_seconds / 60))} min`
        : nextOrder
          ? '准备中'
          : '—',
      stageLabel: nextOrder?.current_stage_label ?? '等待更新',
    };
  }, [queueSnapshot]);

  const sessionHash = sessionId.slice(-6).toUpperCase();
  const latestMode = messages[messages.length - 1]?.mode ?? 'online';
  const statusMessage = status || '等待您的下一条指令';
  const lastAssistantMessage = [...messages].reverse().find((msg) => msg.role === 'assistant')?.content;

  const heroChips = [
    { label: 'SESSION', value: `#${sessionHash}` },
    { label: 'MODEL', value: MODEL_BADGE },
    { label: 'MODE', value: latestMode === 'offline' ? '离线安全回退' : '在线实时' },
  ];

  const statBlocks = [
    { label: '排队中', value: queueMetrics.active.toString().padStart(2, '0'), hint: 'Active orders' },
    { label: '今日完成', value: queueMetrics.completed.toString().padStart(2, '0'), hint: 'Served drinks' },
    { label: '下一杯', value: queueMetrics.eta, hint: queueMetrics.stageLabel },
  ];

  const getStatusMessage = (response: TalkResponse) => {
    const totalText =
      response.order_total !== undefined && response.order_total !== null
        ? `（合计 ¥${response.order_total.toFixed(2)}）`
        : '';
    if (response.order_status === OrderStatus.SAVED && response.order_id) {
      return `订单已保存！订单号：#${response.order_id}${totalText}`;
    }
    return ORDER_STATUS_MESSAGES[response.order_status] ?? '';
  };

  const applyAgentResponse = (response: TalkResponse) => {
    const replyMode =
      response.reply_mode ?? (response.assistant_reply.startsWith('【离线模式】') ? 'offline' : 'online');

    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: response.assistant_reply, mode: replyMode },
    ]);
    setOrderState(response.order_state);
    setStatus(getStatusMessage(response));
    if (response.order_total !== undefined) {
      setOrderTotal(response.order_total ?? null);
    }
    if (response.order_metadata !== undefined) {
      setOrderMeta(response.order_metadata ?? null);
    }
    if (response.order_id) {
      setActiveOrderId(response.order_id);
    }
  };

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;

    const connect = () => {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const wsBase = apiBase.replace(/^http/i, (match) =>
        match.toLowerCase() === 'https' ? 'wss' : 'ws'
      );
      ws = new WebSocket(`${wsBase.replace(/\/$/, '')}/ws/production/queue`);

      ws.onmessage = (event) => {
        if (closed) return;
        try {
          const data: ProductionQueueSnapshot = JSON.parse(event.data);
          setQueueSnapshot(data);
        } catch (error) {
          console.error('Failed to parse queue snapshot', error);
        }
      };

      ws.onerror = async () => {
        ws?.close();
        try {
          const snapshot = await ApiService.getProductionQueue();
          if (!closed) {
            setQueueSnapshot(snapshot);
          }
        } catch (error) {
          console.error('Failed to load production queue', error);
        }
      };
    };

    connect();

    return () => {
      closed = true;
      ws?.close();
    };
  }, []);

  const appendUserMessage = (text: string) => {
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
  };

  const handleSendText = async (text: string) => {
    if (!text.trim() || isProcessing) return;

    appendUserMessage(text);
    setStatus('正在处理...');
    setIsProcessing(true);

    try {
      const response = await ApiService.sendText(sessionId, text);
      applyAgentResponse(response);
    } catch (error) {
      console.error('Error sending text:', error);
      setStatus('发送失败，请重试');
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '抱歉，发送失败，请重试。', mode: 'offline' },
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRealtimeVoiceUserText = (text: string) => {
    if (!text.trim()) return;
    appendUserMessage(text);
    setStatus('语音识别完成，正在处理...');
    setIsProcessing(true);
  };

  const handleRealtimeVoiceResponse = (response: TalkResponse) => {
    applyAgentResponse(response);
    setIsProcessing(false);
  };

  const handleRealtimeVoiceError = (detail: string) => {
    setStatus(detail || '语音处理失败');
    setIsProcessing(false);
  };

  const handleReset = async () => {
    if (!confirm('确定要重新开始吗？当前订单信息将被清除。')) {
      return;
    }

    try {
      await ApiService.resetSession(sessionId);

      setMessages([
        {
          role: 'assistant',
          content: '您好！欢迎光临，我可以帮您点单。请告诉我您想要什么饮品～',
          mode: 'online',
        },
      ]);
      setOrderState(createInitialOrderState());
      setActiveOrderId(null);
      setOrderTotal(null);
      setOrderMeta(null);
      setStatus('会话已重置');
      setTimeout(() => setStatus(''), 2000);
    } catch (error) {
      console.error('Error resetting session:', error);
      setStatus('重置失败');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-ink-950 via-black to-ink-950 text-ink-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-8 px-4 py-10 lg:flex-row lg:px-8">
        <div className="flex flex-1 flex-col gap-6">
          <section className="relative overflow-hidden rounded-[32px] border border-white/10 bg-gradient-to-br from-ink-900/90 via-black/80 to-ink-900/60 p-8 shadow-card">
            <div className="pointer-events-none absolute inset-0 opacity-40">
              <div className="h-full w-full bg-grid-light bg-[size:60px_60px]" />
            </div>
            <div className="relative space-y-6">
              <div className="flex flex-wrap gap-2 text-[10px] font-medium uppercase tracking-[0.4em] text-ink-400">
                {heroChips.map((chip, idx) => (
                  <span
                    key={chip.label}
                    className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] text-ink-200 transition-all duration-300 hover:bg-white/10 hover:border-white/30 hover:scale-110 animate-slide-up"
                    style={{ animationDelay: `${idx * 0.05}s` }}
                  >
                    {chip.label}: {chip.value}
                  </span>
                ))}
              </div>

              <div className="animate-slide-up">
                <p className="text-xs uppercase tracking-[0.4em] text-ink-400">茶茶智能门店</p>
                <h1 className="mt-2 text-4xl font-semibold text-white transition-all duration-300 hover:tracking-wider">黑白格调 · AI 接待台</h1>
                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink-300">
                  统一的黑白灰界面，结合语音、文本与实时制作看板，保持零色差的极简体验，随时切换在线 / 离线模式。
                </p>
              </div>

              <div className="grid gap-3 text-sm sm:grid-cols-3">
                {statBlocks.map((stat, idx) => (
                  <div
                    key={stat.label}
                    className="group relative overflow-hidden rounded-2xl border border-white/10 bg-black/40 px-4 py-3 shadow-glow transition-all duration-500 hover:-translate-y-2 hover:shadow-2xl hover:scale-105 animate-bounce-in"
                    style={{ animationDelay: `${idx * 0.1}s` }}
                  >
                    <div className="text-[10px] uppercase tracking-[0.5em] text-ink-400">{stat.label}</div>
                    <div className="mt-2 text-3xl font-semibold text-white">{stat.value}</div>
                    <div className="text-xs text-ink-400">{stat.hint}</div>
                    <span className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent opacity-0 transition duration-500 group-hover:opacity-100" />
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-4 text-sm text-ink-400">
                <span className="inline-flex items-center gap-2 text-ink-200 animate-pulse-glow">
                  <Activity className="h-4 w-4 text-white" />
                  实时同步制作队列
                </span>
                <button
                  onClick={handleReset}
                  disabled={isProcessing}
                  className="group inline-flex items-center gap-2 rounded-full border border-white/15 bg-black/40 px-4 py-2 text-xs uppercase tracking-[0.4em] text-ink-200 transition-all duration-300 hover:-translate-y-1 hover:border-white/40 hover:shadow-lg hover:scale-105 disabled:opacity-50"
                >
                  <RotateCcw className="h-4 w-4" />
                  Reset
                  <span className="sr-only">重置</span>
                </button>
              </div>
            </div>
          </section>

          <section className="rounded-[32px] border border-white/10 bg-black/40 p-6 shadow-glow">
            <div className="mb-6 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.4em] text-ink-400">AI Concierge</p>
                <h2 className="mt-1 text-2xl font-semibold text-white">自然对话，快速下单</h2>
                <p className="text-sm text-ink-400">语音 / 文字双输入，自动跟进订单状态。</p>
              </div>
              <div className="text-xs text-ink-500">
                队列刷新：{queueSnapshot ? new Date(queueSnapshot.generated_at).toLocaleTimeString() : '—'}
              </div>
            </div>

            <div className="relative rounded-3xl border border-white/10 bg-black/30 p-5 shadow-inner">
              <div className={mode === 'voice' ? 'pointer-events-none blur-sm opacity-40 transition duration-300' : 'transition duration-300'}>
                <ChatContainer messages={messages} />
              </div>
              {mode === 'voice' && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <VoiceInput
                    sessionId={sessionId}
                    disabled={isProcessing}
                    onRealtimeUserText={handleRealtimeVoiceUserText}
                    onAgentResponse={handleRealtimeVoiceResponse}
                    onRealtimeError={handleRealtimeVoiceError}
                    onFallbackTranscript={(text) => handleSendText(text)}
                    assistantPreview={lastAssistantMessage ?? null}
                  />
                </div>
              )}
            </div>

            <div className="mt-6 space-y-4">
              <ModeSelector mode={mode} onModeChange={setMode} />
              <div className="rounded-2xl border border-white/10 bg-black/40 p-4">
                {mode === 'text' ? (
                  <TextInput onSend={handleSendText} disabled={isProcessing} />
                ) : (
                  <p className="text-center text-sm text-ink-400">语音模式已开启，使用上方浮层中的按钮即可控制开始 / 暂停。</p>
                )}
              </div>
              <div className="rounded-2xl border border-white/10 bg-gradient-to-r from-white/10 to-transparent px-4 py-3 text-sm text-ink-200">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.4em] text-ink-400">
                  <Clock4 className="h-4 w-4" />
                  实时状态
                </div>
                <p className="mt-1 text-base text-white">{statusMessage}</p>
              </div>
            </div>
          </section>

          <section className="rounded-[32px] border border-white/10 bg-black/40 p-6 shadow-glow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.4em] text-ink-400">订单快照</p>
                <h2 className="mt-2 text-2xl font-semibold text-white">当前订单</h2>
              </div>
              {activeOrderId && (
                <div className="text-xs uppercase tracking-[0.4em] text-ink-400">#{activeOrderId}</div>
              )}
            </div>
            <OrderInfo orderState={orderState} orderTotal={orderTotal} orderMeta={orderMeta} />
          </section>
        </div>

        <div className="w-full max-w-md space-y-6 lg:sticky lg:top-8">
          <ProductionBoard snapshot={queueSnapshot} activeOrderId={activeOrderId} />
        </div>
      </div>
    </div>
  );
}

export default App;
