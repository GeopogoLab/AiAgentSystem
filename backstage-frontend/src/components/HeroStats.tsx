import { Activity, Zap } from 'lucide-react';

interface HeroStatsProps {
  active: number;
  completed: number;
  nextEta: string;
  modeLabel: string;
}

export function HeroStats({ active, completed, nextEta, modeLabel }: HeroStatsProps) {
  const chips = [
    { label: 'QUEUE', value: active.toString().padStart(2, '0'), hint: '排队中' },
    { label: 'SERVED', value: completed.toString().padStart(2, '0'), hint: '今日完成' },
    { label: 'NEXT ETA', value: nextEta, hint: '下一杯' },
  ];

  return (
    <section className="relative overflow-hidden rounded-[36px] border border-white/10 bg-gradient-to-br from-black/80 via-black/70 to-black/60 p-8 shadow-glow">
      <div className="pointer-events-none absolute inset-0 opacity-30">
        <div className="h-full w-full bg-grid-light bg-[size:60px_60px]" />
      </div>
      <div className="relative space-y-6">
        <div className="inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs uppercase tracking-[0.4em] text-ink-200">
          <Zap className="h-4 w-4 text-white" />
          Backstage Monitor · {modeLabel}
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-ink-400">茶茶后台</p>
          <h1 className="mt-2 text-4xl font-semibold text-white">制作后场 · 黑白玻璃控台</h1>
          <p className="mt-3 max-w-2xl text-sm text-ink-300">
            实时监听订单创建与制作节点，后台无需盯命令行即可获悉需要制作的饮品列表，保持与前台同款黑白玻璃视觉。
          </p>
        </div>
        <div className="grid gap-3 text-sm sm:grid-cols-3">
          {chips.map((chip, idx) => (
            <div
              key={chip.label}
              className="group rounded-3xl border border-white/10 bg-black/30 px-4 py-4 shadow-lg transition-all duration-500 hover:-translate-y-1 hover:border-white/30 hover:bg-black/40"
              style={{ animationDelay: `${idx * 0.05}s` }}
            >
              <div className="text-[10px] uppercase tracking-[0.4em] text-ink-400">{chip.label}</div>
              <div className="mt-2 text-3xl font-semibold text-white">{chip.value}</div>
              <div className="text-xs text-ink-400">{chip.hint}</div>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm text-ink-400">
          <span className="inline-flex items-center gap-2 text-ink-100">
            <Activity className="h-4 w-4 text-white" /> 实时同步制作队列
          </span>
        </div>
      </div>
    </section>
  );
}
