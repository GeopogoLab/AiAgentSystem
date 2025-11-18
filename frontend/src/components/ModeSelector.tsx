import { InputMode } from '../types';
import { MessageSquare, Mic } from 'lucide-react';

interface ModeSelectorProps {
  mode: InputMode;
  onModeChange: (mode: InputMode) => void;
}

export function ModeSelector({ mode, onModeChange }: ModeSelectorProps) {
  return (
    <div className="flex gap-2 rounded-full border border-white/15 bg-black/40 p-1">
      <button
        type="button"
        aria-pressed={mode === 'text'}
        onClick={() => onModeChange('text')}
        className={`flex flex-1 items-center justify-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition duration-300 ${
          mode === 'text'
            ? 'bg-white text-ink-900 shadow-lg'
            : 'text-ink-300 hover:text-white'
        }`}
      >
        <MessageSquare className="h-4 w-4" />
        文字
      </button>
      <button
        type="button"
        aria-pressed={mode === 'voice'}
        onClick={() => onModeChange('voice')}
        className={`flex flex-1 items-center justify-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition duration-300 ${
          mode === 'voice'
            ? 'bg-white text-ink-900 shadow-lg'
            : 'text-ink-300 hover:text-white'
        }`}
      >
        <Mic className="h-4 w-4" />
        语音
      </button>
    </div>
  );
}
