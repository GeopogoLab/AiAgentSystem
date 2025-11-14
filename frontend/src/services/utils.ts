/**
 * 生成会话 ID
 */
export function generateSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * 格式化订单信息
 */
export function formatOrderInfo(orderState: any): string {
  const items: string[] = [];

  if (orderState.drink_name) {
    items.push(`饮品：${orderState.drink_name}`);
  }
  if (orderState.size) {
    items.push(`杯型：${orderState.size}`);
  }
  if (orderState.sugar) {
    items.push(`甜度：${orderState.sugar}`);
  }
  if (orderState.ice) {
    items.push(`冰块：${orderState.ice}`);
  }
  if (orderState.toppings && orderState.toppings.length > 0) {
    items.push(`加料：${orderState.toppings.join('、')}`);
  }
  if (orderState.notes) {
    items.push(`备注：${orderState.notes}`);
  }

  return items.join('\n');
}
