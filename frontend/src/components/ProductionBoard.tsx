import { ProductionQueueSnapshot } from '../types';

interface ProductionBoardProps {
  snapshot?: ProductionQueueSnapshot | null;
  activeOrderId?: number | null;
}

const stageBadges: Record<string, string> = {
  queued: 'bg-yellow-100 text-yellow-700',
  brewing: 'bg-blue-100 text-blue-700',
  sealing: 'bg-purple-100 text-purple-700',
  ready: 'bg-emerald-100 text-emerald-700',
};

export function ProductionBoard({ snapshot, activeOrderId }: ProductionBoardProps) {
  return (
    <div className="mt-6 flex max-h-[75vh] flex-col rounded-2xl border border-primary-100 bg-white p-5 shadow-md">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-xl font-semibold text-primary-600">实时取号面板</h3>
          <p className="text-sm text-gray-500">所有订单的排队、制作、封杯状态</p>
        </div>
        <div className="text-sm text-gray-500">
          刷新时间：{snapshot ? new Date(snapshot.generated_at).toLocaleTimeString() : '—'}
        </div>
      </div>

      <div className="grid flex-1 gap-4 md:grid-cols-2">
        <section className="flex min-h-0 flex-col">
          <div className="mb-2 text-sm font-semibold text-gray-600">制作中</div>
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
            {snapshot && snapshot.active_orders.length > 0 ? (
              snapshot.active_orders.map((order) => (
                <div
                  key={order.order_id}
                  className={`flex items-center justify-between rounded-xl border px-3 py-2 text-sm shadow-sm transition ${
                    order.order_id === activeOrderId
                      ? 'border-primary-400 bg-primary-50'
                      : 'border-gray-100 bg-gray-50'
                  }`}
                >
                  <div>
                    <div className="font-semibold text-gray-900">#{order.order_id}</div>
                    <div className="text-xs text-gray-500">
                      第 {order.queue_position ?? '-'} 位 · {order.current_stage_label}
                    </div>
                  </div>
                  <div
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      stageBadges[order.current_stage] ?? 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {order.current_stage_label}
                  </div>
                  <div className="text-xs text-gray-500">
                    {order.eta_seconds ? `约 ${Math.max(1, Math.ceil(order.eta_seconds / 60))} 分钟` : '准备中'}
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-xl bg-gray-50 p-4 text-sm text-gray-500">
                暂无排队，欢迎下单。
              </div>
            )}
          </div>
        </section>

        <section className="flex min-h-0 flex-col">
          <div className="mb-2 text-sm font-semibold text-gray-600">最近完成</div>
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
            {snapshot && snapshot.completed_orders.length > 0 ? (
              snapshot.completed_orders.map((order) => (
                <div
                  key={order.order_id}
                  className="flex items-center justify-between rounded-xl border border-gray-100 bg-white px-3 py-2 text-sm shadow-sm"
                >
                  <div>
                    <div className="font-semibold text-gray-900">#{order.order_id}</div>
                    <div className="text-xs text-gray-500">{order.current_stage_label}</div>
                  </div>
                  <div className="text-xs text-emerald-600">已完成</div>
                </div>
              ))
            ) : (
              <div className="rounded-xl bg-gray-50 p-4 text-sm text-gray-500">
                暂无完成记录。
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
