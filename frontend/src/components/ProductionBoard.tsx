import { ProductionQueueSnapshot } from '../types';
import { formatRelativeTime } from '../services/utils';

interface ProductionBoardProps {
  snapshot?: ProductionQueueSnapshot | null;
  activeOrderId?: number | null;
}

const metaPill = 'rounded-full border border-white/10 px-3 py-1 text-[10px] uppercase tracking-[0.4em] text-ink-200';

export function ProductionBoard({ snapshot, activeOrderId }: ProductionBoardProps) {
  const renderActiveOrders = () => {
    if (!snapshot || snapshot.active_orders.length === 0) {
      return (
        <div className="rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-ink-400">
          暂无排队，等待新的订单进入制作。
        </div>
      );
    }

    return snapshot.active_orders.map((order) => {
      const etaText = order.eta_seconds ? `约 ${Math.max(1, Math.ceil(order.eta_seconds / 60))} 分钟` : '准备中';
      const queueInfo = order.queue_position ? `第 ${order.queue_position} 位` : '排队更新中';
      const isCurrent = order.order_id === activeOrderId;

      const placedAtDate = order.placed_at ? new Date(order.placed_at) : null;
      const placedAtFormatted = placedAtDate ? placedAtDate.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      }) : '未知时间';

      return (
        <article
          key={order.order_id}
          className={`group relative overflow-hidden rounded-3xl border border-white/15 bg-white/5 p-4 text-sm transition-all duration-500 hover:-translate-y-2 hover:border-white/40 hover:bg-white/10 hover:shadow-2xl hover:scale-[1.02] ${
            isCurrent ? 'border-white/50 bg-white/15 shadow-glow' : ''
          }`}
        >
          {/* 主要内容 */}
          <div className="flex items-center justify-between text-xs uppercase tracking-[0.4em] text-ink-300">
            <span>#{order.order_id}</span>
            <span>{queueInfo}</span>
          </div>
          <div className="mt-3 flex items-end justify-between">
            <div>
              <p className="text-lg font-semibold text-white">{order.drink_name ?? order.current_stage_label}</p>
              <p className="text-xs text-ink-400">{etaText}</p>
              <p className="text-[11px] text-ink-500">下单 {formatRelativeTime(order.placed_at)}</p>
            </div>
            <div className={metaPill}>{order.current_stage.toUpperCase()}</div>
          </div>

          {/* 悬浮时显示的详细信息 */}
          <div className="mt-3 opacity-0 max-h-0 overflow-hidden transition-all duration-500 group-hover:opacity-100 group-hover:max-h-40">
            <div className="rounded-2xl border border-white/20 bg-black/60 p-3 backdrop-blur-sm animate-slide-up">
              <div className="text-[10px] uppercase tracking-[0.4em] text-ink-400 mb-2">订单详情</div>

              {/* 下单时间 */}
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="text-ink-400">下单时间</span>
                <span className="text-white font-mono">{placedAtFormatted}</span>
              </div>

              {/* 订单配置 */}
              <div className="flex flex-wrap gap-2 text-[10px] mb-2">
                {order.size && <span className="rounded-full border border-white/20 bg-white/10 px-2 py-0.5 text-ink-200">{order.size}</span>}
                {order.sugar && <span className="rounded-full border border-white/20 bg-white/10 px-2 py-0.5 text-ink-200">{order.sugar}</span>}
                {order.ice && <span className="rounded-full border border-white/20 bg-white/10 px-2 py-0.5 text-ink-200">{order.ice}</span>}
              </div>

              {/* 加料 */}
              {order.toppings?.length ? (
                <div className="text-[11px] text-ink-300">
                  <span className="text-ink-400">加料：</span>{order.toppings.join('、')}
                </div>
              ) : null}
            </div>
          </div>

          {/* 底部光效 */}
          <span className="pointer-events-none absolute inset-0 opacity-0 transition-all duration-500 group-hover:opacity-100">
            <span className="absolute inset-x-4 bottom-0 h-px bg-gradient-to-r from-transparent via-white/50 to-transparent" />
          </span>
        </article>
      );
    });
  };

  const renderCompletedOrders = () => {
    if (!snapshot || snapshot.completed_orders.length === 0) {
      return (
        <div className="rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-ink-400">
          暂无完成记录。
        </div>
      );
    }

    return snapshot.completed_orders.map((order) => {
      const placedAtDate = order.placed_at ? new Date(order.placed_at) : null;
      const placedAtFormatted = placedAtDate ? placedAtDate.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      }) : '未知时间';

      return (
        <article
          key={order.order_id}
          className="group relative overflow-hidden rounded-3xl border border-white/10 bg-black/30 p-4 text-sm text-ink-200 transition-all duration-300 hover:border-white/30 hover:bg-black/40 hover:-translate-y-1 hover:scale-[1.01]"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-white">#{order.order_id}</p>
              <p className="text-xs text-ink-400">{order.drink_name ?? order.current_stage_label}</p>
              <p className="text-[11px] text-ink-500">{formatRelativeTime(order.placed_at)}</p>
            </div>
            <div className="rounded-full border border-emerald-300/40 bg-emerald-500/10 px-3 py-1 text-xs uppercase tracking-[0.4em] text-emerald-200">
              完成
            </div>
          </div>

          {/* 悬浮时显示的详细信息 */}
          <div className="mt-2 opacity-0 max-h-0 overflow-hidden transition-all duration-300 group-hover:opacity-100 group-hover:max-h-32">
            <div className="rounded-xl border border-white/15 bg-black/50 p-2 mt-2 backdrop-blur-sm">
              <div className="text-[10px] uppercase tracking-[0.4em] text-ink-500 mb-1.5">订单详情</div>

              {/* 下单时间 */}
              <div className="mb-1.5 flex items-center justify-between text-[11px]">
                <span className="text-ink-400">下单时间</span>
                <span className="text-ink-200 font-mono">{placedAtFormatted}</span>
              </div>

              {/* 订单配置 */}
              <div className="flex flex-wrap gap-1.5 text-[10px]">
                {order.size && <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-ink-300">{order.size}</span>}
                {order.sugar && <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-ink-300">{order.sugar}</span>}
                {order.ice && <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-ink-300">{order.ice}</span>}
              </div>

              {/* 加料 */}
              {order.toppings?.length ? (
                <div className="text-[10px] text-ink-400 mt-1.5">
                  加料：{order.toppings.join('、')}
                </div>
              ) : null}
            </div>
          </div>

          {/* 底部光效 */}
          <span className="pointer-events-none absolute inset-0 opacity-0 transition-all duration-300 group-hover:opacity-100">
            <span className="absolute inset-x-3 bottom-0 h-px bg-gradient-to-r from-transparent via-emerald-400/30 to-transparent" />
          </span>
        </article>
      );
    });
  };

  return (
    <div className="relative overflow-hidden rounded-[32px] border border-white/10 bg-gradient-to-b from-black/85 via-black/70 to-black/80 p-6 shadow-glow">
      <div className="pointer-events-none absolute inset-0 opacity-20">
        <div className="h-full w-full bg-grid-light bg-[size:40px_40px]" />
      </div>
      <div className="relative flex flex-col gap-2">
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-ink-400">Production Board</p>
          <h3 className="mt-1 text-2xl font-semibold text-white">实时取号面板</h3>
        </div>
        <div className="text-xs text-ink-500">更新：{snapshot ? new Date(snapshot.generated_at).toLocaleTimeString() : '—'}</div>
      </div>

      <div className="relative mt-6 space-y-6">
        <section>
          <div className="mb-3 text-xs uppercase tracking-[0.4em] text-ink-400">制作中</div>
          <div className="space-y-3">{renderActiveOrders()}</div>
        </section>

        <section>
          <div className="mb-3 text-xs uppercase tracking-[0.4em] text-ink-400">最近完成</div>
          <div className="space-y-3">{renderCompletedOrders()}</div>
        </section>
      </div>
    </div>
  );
}
