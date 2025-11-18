import { useState, KeyboardEvent } from 'react';
import { Send } from 'lucide-react';

interface TextInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function TextInput({ onSend, disabled, placeholder }: TextInputProps) {
  const [text, setText] = useState('');

  const handleSend = () => {
    if (text.trim() && !disabled) {
      onSend(text.trim());
      setText('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = Boolean(text.trim()) && !disabled;

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder ?? '输入您的需求...'}
          disabled={disabled}
          className="w-full rounded-2xl border border-white/15 bg-transparent px-5 py-3 text-base text-white placeholder:text-ink-500 focus:border-white/40 focus:outline-none disabled:cursor-not-allowed disabled:text-ink-500"
        />
        <p className="mt-1 text-xs uppercase tracking-[0.4em] text-ink-500">按 Enter 立即发送</p>
      </div>
      <button
        type="button"
        aria-label="发送"
        onClick={handleSend}
        disabled={!canSend}
        className="relative inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-white/15 bg-white/10 text-white transition duration-300 hover:border-white/40 hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Send className="h-5 w-5" />
        {canSend && <span className="absolute inset-0 rounded-2xl border border-white/10 animate-pulseRing" />}
      </button>
    </div>
  );
}
