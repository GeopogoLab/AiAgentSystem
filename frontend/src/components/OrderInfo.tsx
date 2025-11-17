import { OrderState } from '../types';

interface OrderInfoProps {
  orderState: OrderState;
  orderTotal?: number | null;
}

export function OrderInfo({ orderState, orderTotal }: OrderInfoProps) {
  const hasData =
    orderState.drink_name ||
    orderState.size ||
    orderState.sugar ||
    orderState.ice ||
    orderState.toppings.length > 0 ||
    orderTotal !== undefined;

  if (!hasData) {
    return null;
  }

  return (
    <div className="mt-6 rounded-lg bg-gray-100 p-4">
      <h3 className="mb-3 text-lg font-semibold text-primary-600">当前订单</h3>
      <div className="space-y-2">
        {orderState.drink_name && (
          <OrderItem label="饮品" value={orderState.drink_name} />
        )}
        {orderState.size && <OrderItem label="杯型" value={orderState.size} />}
        {orderState.sugar && (
          <OrderItem label="甜度" value={orderState.sugar} />
        )}
        {orderState.ice && <OrderItem label="冰块" value={orderState.ice} />}
        {orderState.toppings.length > 0 && (
          <OrderItem label="加料" value={orderState.toppings.join('、')} />
        )}
        {orderState.notes && (
          <OrderItem label="备注" value={orderState.notes} />
        )}
        {orderTotal !== undefined && orderTotal !== null && (
          <OrderItem label="金额" value={`¥${orderTotal.toFixed(2)}`} />
        )}
      </div>
    </div>
  );
}

interface OrderItemProps {
  label: string;
  value: string;
}

function OrderItem({ label, value }: OrderItemProps) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-600">{label}：</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  );
}
