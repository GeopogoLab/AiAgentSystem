# 茶茶后台前端（Backstage Monitor）

实时监听订单制作队列的黑白玻璃风后台界面，用于后厨在新订单产生时弹出所需制作清单。

## 开发

```bash
cd backstage-frontend
npm install
npm run dev
```

通过 `VITE_API_URL` 指定后端地址，默认 `http://localhost:8000`。

## 功能

- WebSocket + 轮询双路监听 `/production/queue`
- 新订单自动高亮并弹出需要制作的详情
- 黑白玻璃拟态视觉，与前台保持一致
- 状态卡片展示实时连接状态与队列指标
