import { useEffect, useState } from 'react';
import { Volume2 } from 'lucide-react';
import { Message as MessageType } from '../types';
import { ApiService } from '../services/api';

interface MessageProps {
  message: MessageType;
}

export function Message({ message }: MessageProps) {
  const isUser = message.role === 'user';
  const label = isUser
    ? '访客'
    : message.mode === 'offline'
      ? 'AI · 离线'
      : message.mode === 'online'
        ? 'AI · 在线'
        : 'AI 助手';
  const [isPlaying, setIsPlaying] = useState(false);
  const [audio, setAudio] = useState<HTMLAudioElement | null>(null);
  const [ttsError, setTtsError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      audio?.pause();
    };
  }, [audio]);

  const handlePlay = async () => {
    if (isUser || !message.content.trim() || isPlaying) return;
    setTtsError(null);
    try {
      setIsPlaying(true);
      const data = await ApiService.requestTTS(message.content);
      const src =
        data.audio_url ??
        (data.audio_base64 ? `data:audio/${data.format ?? 'mp3'};base64,${data.audio_base64}` : null);
      if (!src) {
        throw new Error('No audio generated');
      }
      const audioElement = new Audio(src);
      setAudio(audioElement);
      audioElement.onended = () => setIsPlaying(false);
      audioElement.onerror = () => {
        setIsPlaying(false);
        setTtsError('无法播放语音');
      };
      await audioElement.play();
    } catch (error) {
      console.error('Failed to play TTS', error);
      setIsPlaying(false);
      setTtsError('无法合成语音');
    }
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-slide-up`}>
      <div
        className={`group relative max-w-[80%] rounded-3xl px-5 py-4 text-sm leading-relaxed transition-all duration-500 ${
          isUser
            ? 'bg-white text-ink-900 shadow-xl hover:shadow-2xl hover:scale-[1.02]'
            : 'border border-white/15 bg-white/5 text-ink-100 backdrop-blur-sm hover:border-white/30 hover:bg-white/10'
        }`}
      >
        <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-[0.4em] text-ink-400">
          <span>{label}</span>
          {!isUser && (
            <button
              type="button"
              onClick={handlePlay}
              disabled={isPlaying}
              className="inline-flex items-center gap-1 rounded-full border border-white/15 px-2 py-1 text-[10px] font-medium uppercase tracking-[0.4em] text-ink-300 transition hover:border-white/40 hover:text-white disabled:opacity-60"
            >
              <Volume2 className="h-3 w-3" />
              {isPlaying ? '播报中' : '语音'}
            </button>
          )}
        </div>
        <div className="whitespace-pre-wrap text-base text-current">{message.content}</div>
        {ttsError && !isUser && (
          <div className="mt-2 text-[11px] text-red-400">{ttsError}</div>
        )}
        {!isUser && (
          <span className="pointer-events-none absolute inset-0 -z-10 rounded-[32px] opacity-0 transition duration-300 group-hover:opacity-100">
            <span className="absolute inset-0 animate-ripple rounded-[32px] border border-white/5" />
          </span>
        )}
      </div>
    </div>
  );
}
