import { OrderMetadata, OrderState } from '../types';

interface OrderInfoProps {
  orderState: OrderState;
  orderTotal?: number | null;
  orderMeta?: OrderMetadata | null;
}

function formatTimestamp(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function OrderInfo({ orderState, orderTotal, orderMeta }: OrderInfoProps) {
  const entries = [
    orderState.drink_name && { label: '饮品', value: orderState.drink_name },
    orderState.size && { label: '杯型', value: orderState.size },
    orderState.sugar && { label: '甜度', value: orderState.sugar },
    orderState.ice && { label: '冰块', value: orderState.ice },
    orderState.toppings.length > 0 && { label: '加料', value: orderState.toppings.join('、') },
    orderState.notes && { label: '备注', value: orderState.notes },
    orderTotal !== undefined && orderTotal !== null && { label: '金额', value: `¥${orderTotal.toFixed(2)}` },
  ].filter(Boolean) as { label: string; value: string }[];

  const metaEntries = [
    orderMeta?.placed_at && { label: '下单时间', value: formatTimestamp(orderMeta.placed_at) },
    orderMeta?.session_id && {
      label: '会话',
      value: `#${orderMeta.session_id.slice(-6).toUpperCase()}`,
    },
  ].filter(Boolean) as { label: string; value: string }[];

  if (entries.length === 0 && metaEntries.length === 0) {
    return (
      <div className="mt-6 rounded-3xl border border-white/10 bg-black/30 p-6 text-sm text-ink-400">
        待收集更多订单信息，开始对话即可更新。
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-4">
      {metaEntries.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {metaEntries.map((item, idx) => (
            <div
              key={`${item.label}-${item.value}`}
              className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-ink-200 transition-all duration-300 hover:bg-white/10 hover:border-white/30 hover:scale-105 animate-bounce-in"
              style={{ animationDelay: `${idx * 0.1}s` }}
            >
              <div className="text-[10px] uppercase tracking-[0.4em] text-ink-400">{item.label}</div>
              <div className="mt-1 text-sm text-white">{item.value}</div>
            </div>
          ))}
        </div>
      )}
      {entries.map((item, index) => (
        <div
          key={`${item.label}-${index}`}
          className="group relative flex items-center gap-3 rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-ink-200 transition-all duration-300 hover:bg-black/40 hover:border-white/30 hover:scale-[1.02] animate-slide-up"
          style={{ animationDelay: `${(metaEntries.length + index) * 0.1}s` }}
        >
          <span className="relative flex h-8 w-8 items-center justify-center rounded-2xl border border-white/10 text-xs font-semibold text-white">
            {item.label}
            <span className="absolute inset-0 rounded-2xl border border-white/5 opacity-0 transition group-hover:opacity-100" />
          </span>
          <div className="text-base text-white">{item.value}</div>
        </div>
      ))}
      {orderState.is_complete && (
        <div className="rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-center text-xs uppercase tracking-[0.4em] text-white animate-bounce-in animate-pulse-glow">
          订单已确认
        </div>
      )}
    </div>
  );
}
