import { InputMode } from '../types';
import { MessageSquare, Mic } from 'lucide-react';

interface ModeSelectorProps {
  mode: InputMode;
  onModeChange: (mode: InputMode) => void;
}

export function ModeSelector({ mode, onModeChange }: ModeSelectorProps) {
  return (
    <div className="flex gap-3">
      <button
        onClick={() => onModeChange('text')}
        className={`flex flex-1 items-center justify-center gap-2 rounded-lg border-2 py-3 font-medium transition-all ${
          mode === 'text'
            ? 'border-primary-500 bg-primary-500 text-white'
            : 'border-primary-500 bg-white text-primary-500 hover:bg-primary-50'
        }`}
      >
        <MessageSquare className="h-5 w-5" />
        文字模式
      </button>
      <button
        onClick={() => onModeChange('voice')}
        className={`flex flex-1 items-center justify-center gap-2 rounded-lg border-2 py-3 font-medium transition-all ${
          mode === 'voice'
            ? 'border-primary-500 bg-primary-500 text-white'
            : 'border-primary-500 bg-white text-primary-500 hover:bg-primary-50'
        }`}
      >
        <Mic className="h-5 w-5" />
        语音模式
      </button>
    </div>
  );
}
