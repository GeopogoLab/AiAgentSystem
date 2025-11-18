import { CheckCircle2, X } from 'lucide-react';
import { ProductionQueueSnapshot, OrderProgress } from '../types';
import { formatRelativeTime } from '../utils/time';

interface NewOrdersPanelProps {
  open: boolean;
  snapshot?: ProductionQueueSnapshot | null;
  highlightedIds: number[];
  onClose: () => void;
  onAcknowledge: (orderId: number) => void;
}

export function NewOrdersPanel({ open, snapshot, highlightedIds, onClose, onAcknowledge }: NewOrdersPanelProps) {
  if (!snapshot || highlightedIds.length === 0) {
    return null;
  }

  const orders: OrderProgress[] = snapshot.active_orders.filter((order) => highlightedIds.includes(order.order_id));
  if (orders.length === 0) {
    return null;
  }

  return (
    <div className={`fixed inset-0 z-50 flex items-start justify-center bg-black/70 backdrop-blur-2xl transition-opacity duration-500 ${open ? 'opacity-100 pointer-events-auto' : 'pointer-events-none opacity-0'}`}>
      <div className="relative mt-12 w-full max-w-5xl rounded-[40px] border border-white/15 bg-gradient-to-br from-black/90 via-black/80 to-black/85 p-8 shadow-glow">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-6 top-6 rounded-full border border-white/10 bg-black/40 p-2 text-ink-200 transition hover:border-white/40 hover:bg-black/60"
          aria-label="关闭新订单面板"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex flex-wrap items-center gap-4">
          <div className="rounded-full border border-white/15 bg-white/10 px-4 py-2 text-sm uppercase tracking-[0.4em] text-ink-100">
            新订单提醒
          </div>
          <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.4em] text-white">
            {orders.length.toString().padStart(2, '0')} PENDING
          </div>
        </div>
        <p className="mt-4 text-sm text-ink-300">
          下方列出的订单刚刚生成，确认配方后即可开始制作。每条记录都同步自实时制作队列，不需要额外刷新。
        </p>

        <div className="mt-6 space-y-4">
          {orders.map((order) => (
            <article
              key={order.order_id}
              className="rounded-3xl border border-white/15 bg-white/5 p-5 text-sm text-ink-200"
            >
              <div className="flex flex-wrap items-center justify-between gap-3 text-xs uppercase tracking-[0.4em] text-ink-300">
                <span>#{order.order_id}</span>
                <span>{order.queue_position ? `队列第 ${order.queue_position}` : '排队更新中'}</span>
                <span>下单 {formatRelativeTime(order.placed_at)}</span>
              </div>
              <div className="mt-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-2xl font-semibold text-white">{order.drink_name ?? '未知饮品'}</p>
                  <p className="text-sm text-ink-400">{order.current_stage_label}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.4em] text-ink-300">
                  {order.size && <span className="rounded-full border border-white/15 bg-black/40 px-3 py-1">Size {order.size}</span>}
                  {order.sugar && <span className="rounded-full border border-white/15 bg-black/40 px-3 py-1">Sugar {order.sugar}</span>}
                  {order.ice && <span className="rounded-full border border-white/15 bg-black/40 px-3 py-1">Ice {order.ice}</span>}
                </div>
              </div>
              {order.toppings?.length ? (
                <p className="mt-3 text-sm text-ink-300">加料：{order.toppings.join('、')}</p>
              ) : (
                <p className="mt-3 text-sm text-ink-500">无额外加料</p>
              )}
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] uppercase tracking-[0.4em] text-ink-200">
                  ETA {order.eta_seconds ? `${Math.max(1, Math.ceil(order.eta_seconds / 60))} min` : '待估'}
                </div>
                <button
                  type="button"
                  onClick={() => onAcknowledge(order.order_id)}
                  className="inline-flex items-center gap-2 rounded-full border border-emerald-400/60 bg-emerald-500/10 px-4 py-2 text-xs uppercase tracking-[0.4em] text-emerald-100 transition hover:bg-emerald-500/20"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  已确认
                </button>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
