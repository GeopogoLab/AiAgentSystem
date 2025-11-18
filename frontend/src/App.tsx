import { useEffect, useState } from 'react';
import { RotateCcw } from 'lucide-react';
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
  const [isProcessing, setIsProcessing] = useState(false);
  const [queueSnapshot, setQueueSnapshot] = useState<ProductionQueueSnapshot | null>(null);

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

  const handleSendText = async (text: string) => {
    if (!text.trim() || isProcessing) return;

    // 添加用户消息
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
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


  const handleReset = async () => {
    if (!confirm('确定要重新开始吗？当前订单信息将被清除。')) {
      return;
    }

    try {
      await ApiService.resetSession(sessionId);

      // 重置状态
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
      setStatus('会话已重置');
      setTimeout(() => setStatus(''), 2000);
    } catch (error) {
      console.error('Error resetting session:', error);
      setStatus('重置失败');
    }
  };

  return (
    <div className="min-h-screen bg-slate-100">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-6 p-6 lg:flex-row">
        {/* Left Column */}
        <div className="flex flex-1 flex-col gap-6">
          <div className="rounded-2xl bg-gradient-to-r from-primary-500 to-secondary-500 p-6 text-white shadow-lg">
            <div className="text-sm uppercase tracking-wide opacity-80">茶茶智能门店</div>
            <h1 className="mt-2 text-3xl font-bold">茶饮 AI 接待台</h1>
            <p className="mt-1 text-sm opacity-80">语音或文字下单，实时了解制作进度</p>
            <div className="mt-3 inline-flex items-center rounded-full border border-white/40 bg-white/10 px-4 py-1 text-xs">
              Powered by {MODEL_BADGE}
            </div>
          </div>

          <div className="grow rounded-2xl bg-white p-6 shadow-lg">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-primary-600">AI 接待员</h2>
                <p className="text-sm text-gray-500">自然对话即可完成点单</p>
              </div>
              <button
                onClick={handleReset}
                disabled={isProcessing}
                className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 shadow-sm transition hover:border-primary-200 hover:text-primary-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RotateCcw className="h-4 w-4" />
                重新开始
              </button>
            </div>
            <div className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
              <ChatContainer messages={messages} />
            </div>
            <div className="mt-4">
              <ModeSelector mode={mode} onModeChange={setMode} />
              <div className="mt-3 min-h-[100px]">
                {mode === 'text' ? (
                  <TextInput onSend={handleSendText} disabled={isProcessing} />
                ) : (
              <VoiceInput
                onTranscript={(text) => handleSendText(text)}
                disabled={isProcessing}
              />
            )}
          </div>
              {status && (
                <div className="mt-2 rounded-lg bg-primary-50 px-3 py-2 text-sm text-primary-700">
                  {status}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-2xl bg-white p-6 shadow-lg">
            <h2 className="mb-4 text-xl font-semibold text-primary-600">当前订单</h2>
            <OrderInfo orderState={orderState} orderTotal={orderTotal} />
          </div>
        </div>

        {/* Right Column */}
        <div className="w-full max-w-md space-y-6 lg:sticky lg:top-6">
          <ProductionBoard snapshot={queueSnapshot} activeOrderId={activeOrderId} />
        </div>
      </div>
    </div>
  );
}

export default App;
