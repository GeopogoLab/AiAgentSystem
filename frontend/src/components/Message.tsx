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
    ? '您'
    : message.mode === 'offline'
      ? 'AI 接待员 · 离线'
      : message.mode === 'online'
        ? 'AI 接待员 · LLM'
        : 'AI 接待员';
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
    <div
      className={`mb-4 flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-primary-500 text-white'
            : 'bg-white border border-gray-200 text-gray-800'
        }`}
      >
        <div className="mb-1 flex items-center justify-between text-xs opacity-70">
          <span>{label}</span>
          {!isUser && (
            <button
              type="button"
              onClick={handlePlay}
              disabled={isPlaying}
              className="inline-flex items-center gap-1 rounded-full border border-gray-200 px-2 py-0.5 text-[10px] font-medium text-gray-600 transition hover:border-primary-200 hover:text-primary-600 disabled:opacity-50"
            >
              <Volume2 className="h-3 w-3" />
              {isPlaying ? '播报中...' : '语音播报'}
            </button>
          )}
        </div>
        <div className="text-sm whitespace-pre-wrap">{message.content}</div>
        {ttsError && !isUser && (
          <div className="mt-1 text-[10px] text-red-500">{ttsError}</div>
        )}
      </div>
    </div>
  );
}
