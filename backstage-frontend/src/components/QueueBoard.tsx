import { Flame, ListCheck } from 'lucide-react';
import { ProductionQueueSnapshot } from '../types';
import { formatRelativeTime } from '../utils/time';

interface QueueBoardProps {
  snapshot?: ProductionQueueSnapshot | null;
  highlightedIds?: number[];
}

const chipCls = 'rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[10px] uppercase tracking-[0.4em] text-ink-200';

export function QueueBoard({ snapshot, highlightedIds = [] }: QueueBoardProps) {
  const isHighlighted = (orderId: number) => highlightedIds.includes(orderId);

  const renderActive = () => {
    if (!snapshot || snapshot.active_orders.length === 0) {
      return (
        <div className="rounded-3xl border border-white/10 bg-black/30 p-5 text-sm text-ink-400">
          暂无排队，等待新订单进入制作。
        </div>
      );
    }

    return snapshot.active_orders.map((order) => (
      <article
        key={order.order_id}
        className={`group relative overflow-hidden rounded-3xl border border-white/15 bg-white/5 p-5 transition-all duration-500 hover:-translate-y-1 hover:border-white/40 hover:bg-white/15 hover:shadow-2xl ${
          isHighlighted(order.order_id) ? 'border-white/60 bg-white/20 shadow-glow' : ''
        }`}
      >
        <div className="flex items-center justify-between text-xs uppercase tracking-[0.4em] text-ink-300">
          <span>#{order.order_id}</span>
          <span>{order.queue_position ? `队列第 ${order.queue_position}` : '排队更新中'}</span>
        </div>
        <div className="mt-3 flex items-end justify-between">
          <div>
            <p className="text-xl font-semibold text-white">{order.drink_name ?? order.current_stage_label}</p>
            <p className="text-sm text-ink-400">
              {order.eta_seconds ? `约 ${Math.max(1, Math.ceil(order.eta_seconds / 60))} 分钟` : '准备中'} ·
              下单 {formatRelativeTime(order.placed_at)}
            </p>
          </div>
          <div className={chipCls}>{order.current_stage.toUpperCase()}</div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.4em] text-ink-400">
          {order.size && <span className={chipCls}>Size {order.size}</span>}
          {order.sugar && <span className={chipCls}>Sugar {order.sugar}</span>}
          {order.ice && <span className={chipCls}>Ice {order.ice}</span>}
          {order.toppings?.length ? (
            <span className={chipCls.replace('px-3', 'px-4')}>Toppings {order.toppings.length}</span>
          ) : null}
        </div>
        <span className="pointer-events-none absolute inset-0 opacity-0 transition group-hover:opacity-100">
          <span className="absolute inset-x-5 bottom-0 h-px bg-gradient-to-r from-transparent via-white/60 to-transparent" />
        </span>
      </article>
    ));
  };

  const renderCompleted = () => {
    if (!snapshot || snapshot.completed_orders.length === 0) {
      return (
        <div className="rounded-3xl border border-white/10 bg-black/30 p-5 text-sm text-ink-400">
          暂无完成记录。
        </div>
      );
    }

    return snapshot.completed_orders.map((order) => (
      <article
        key={order.order_id}
        className="flex items-center justify-between rounded-3xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-ink-200 transition-all duration-300 hover:border-white/30 hover:bg-black/40"
      >
        <div>
          <p className="text-sm font-semibold text-white">#{order.order_id}</p>
          <p className="text-xs text-ink-400">{order.current_stage_label}</p>
          <p className="text-[11px] text-ink-500">{formatRelativeTime(order.placed_at)}</p>
        </div>
        <div className="rounded-full border border-emerald-300/40 bg-emerald-600/15 px-3 py-1 text-[10px] uppercase tracking-[0.4em] text-emerald-100">
          完成
        </div>
      </article>
    ));
  };

  return (
    <div className="rounded-[36px] border border-white/10 bg-gradient-to-b from-black/80 via-black/70 to-black/75 p-6 shadow-glow">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-3 text-xs uppercase tracking-[0.4em] text-ink-400">
          <Flame className="h-4 w-4 text-white" />
          Live Queue
        </div>
        <h3 className="text-2xl font-semibold text-white">制作队列</h3>
        <p className="text-xs text-ink-500">
          更新：{snapshot ? new Date(snapshot.generated_at).toLocaleTimeString() : '—'}
        </p>
      </div>
      <div className="mt-6 space-y-6">
        <section>
          <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-[0.4em] text-ink-400">
            <ListCheck className="h-4 w-4" />
            制作中
          </div>
          <div className="space-y-3">{renderActive()}</div>
        </section>
        <section>
          <div className="mb-3 text-xs uppercase tracking-[0.4em] text-ink-400">最近完成</div>
          <div className="space-y-3">{renderCompleted()}</div>
        </section>
      </div>
    </div>
  );
}
