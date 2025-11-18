import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Loader2, WifiOff } from 'lucide-react';
import { ApiService } from './services/api';
import { ProductionQueueSnapshot } from './types';
import { QueueBoard } from './components/QueueBoard';
import { NewOrdersPanel } from './components/NewOrdersPanel';
import { HeroStats } from './components/HeroStats';

const MODEL_BADGE = import.meta.env.VITE_MODEL_BADGE ?? 'OpenRouter · Llama 3.3 70B';

export default function App() {
  const [snapshot, setSnapshot] = useState<ProductionQueueSnapshot | null>(null);
  const [connectionState, setConnectionState] = useState<'connecting' | 'live' | 'fallback'>('connecting');
  const [error, setError] = useState<string | null>(null);
  const [highlightedIds, setHighlightedIds] = useState<number[]>([]);
  const [panelOpen, setPanelOpen] = useState(false);
  const seenOrders = useRef<Set<number>>(new Set());

  const stats = useMemo(() => {
    const active = snapshot?.active_orders.length ?? 0;
    const completed = snapshot?.completed_orders.length ?? 0;
    const nextOrder = snapshot?.active_orders[0];
    const nextEta = nextOrder?.eta_seconds
      ? `${Math.max(1, Math.ceil(nextOrder.eta_seconds / 60))} min`
      : nextOrder
        ? '准备中'
        : '—';
    return { active, completed, nextEta };
  }, [snapshot]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;

    const connect = () => {
      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const wsBase = apiBase.replace(/^http/i, (match) => (match.toLowerCase() === 'https' ? 'wss' : 'ws'));
      ws = new WebSocket(`${wsBase.replace(/\/$/, '')}/ws/production/queue`);

      ws.onopen = () => {
        setConnectionState('live');
        setError(null);
      };

      ws.onmessage = (event) => {
        if (closed) return;
        try {
          const data: ProductionQueueSnapshot = JSON.parse(event.data);
          setSnapshot(data);
        } catch (err) {
          console.error('队列消息解析失败', err);
          setError('队列数据解析失败');
        }
      };

      ws.onerror = () => {
        ws?.close();
        setConnectionState('fallback');
      };

      ws.onclose = () => {
        if (!closed) {
          setConnectionState('fallback');
        }
      };
    };

    connect();

    const fallbackInterval = setInterval(async () => {
      if (connectionState === 'live') return;
      try {
        const data = await ApiService.getQueueSnapshot();
        setSnapshot(data);
        setError(null);
      } catch (err) {
        console.error('拉取制作队列失败', err);
        setError('无法连接实时队列');
      }
    }, 5000);

    return () => {
      closed = true;
      ws?.close();
      clearInterval(fallbackInterval);
    };
  }, [connectionState]);

  useEffect(() => {
    if (!snapshot) return;
    const activeOrders = snapshot.active_orders ?? [];
    if (activeOrders.length === 0) {
      setHighlightedIds([]);
      setPanelOpen(false);
      return;
    }
    const newly = activeOrders.filter((order) => !seenOrders.current.has(order.order_id));
    if (newly.length > 0) {
      newly.forEach((order) => seenOrders.current.add(order.order_id));
      setHighlightedIds((prev) => Array.from(new Set([...prev, ...newly.map((order) => order.order_id)])));
      setPanelOpen(true);
    } else {
      setHighlightedIds((prev) => prev.filter((id) => activeOrders.some((order) => order.order_id === id)));
    }
  }, [snapshot]);

  const handleAcknowledge = (orderId: number) => {
    setHighlightedIds((prev) => {
      const next = prev.filter((id) => id !== orderId);
      if (next.length === 0) {
        setPanelOpen(false);
      }
      return next;
    });
  };

  const connectionHint = {
    connecting: '正在连接实时队列',
    live: '连接正常 · WebSocket',
    fallback: '实时通道异常，自动切换轮询模式',
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-ink-950 via-black to-ink-950 text-ink-50">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-8 px-4 py-10 lg:px-8">
        <HeroStats active={stats.active} completed={stats.completed} nextEta={stats.nextEta} modeLabel={connectionHint[connectionState]} />

        {error && (
          <div className="flex items-center gap-3 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            <AlertTriangle className="h-5 w-5" />
            {error}
          </div>
        )}

        <div className="grid gap-8 lg:grid-cols-[2fr_1fr]">
          <QueueBoard snapshot={snapshot ?? undefined} highlightedIds={highlightedIds} />

          <div className="space-y-4 rounded-[32px] border border-white/10 bg-black/40 p-6 shadow-glow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.4em] text-ink-400">Backstage State</p>
                <p className="mt-1 text-2xl font-semibold text-white">连接状态</p>
              </div>
              <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.4em] text-ink-200">
                {MODEL_BADGE}
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-ink-200">
              <div className="flex items-center gap-3">
                {connectionState === 'live' ? (
                  <Loader2 className="h-4 w-4 animate-spin text-emerald-300" />
                ) : (
                  <WifiOff className="h-4 w-4 text-yellow-300" />
                )}
                {connectionHint[connectionState]}
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-ink-300">
              新订单会自动高亮并拉起上方弹窗，无需人工刷新。点击“已确认”即可关闭弹窗并开始制作。
            </div>
          </div>
        </div>
      </div>

      <NewOrdersPanel
        open={panelOpen}
        snapshot={snapshot ?? undefined}
        highlightedIds={highlightedIds}
        onClose={() => setPanelOpen(false)}
        onAcknowledge={handleAcknowledge}
      />
    </div>
  );
}
