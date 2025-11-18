import { Mic } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { TalkResponse } from '../types';

interface VoiceInputProps {
  sessionId: string;
  disabled?: boolean;
  useRealtime?: boolean;
  onFallbackTranscript?: (text: string) => void;
  onRealtimeUserText?: (text: string) => void;
  onAgentResponse?: (response: TalkResponse) => void;
  onRealtimeError?: (message: string) => void;
  assistantPreview?: string | null;
}

export function VoiceInput({
  sessionId,
  disabled,
  useRealtime = true,
  onFallbackTranscript,
  onRealtimeUserText,
  onAgentResponse,
  onRealtimeError,
  assistantPreview,
}: VoiceInputProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [partial, setPartial] = useState('');
  const [lastRecognized, setLastRecognized] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  const stopStreaming = () => {
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    audioContextRef.current?.close();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    processorRef.current = null;
    sourceRef.current = null;
    audioContextRef.current = null;
    streamRef.current = null;

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event: 'flush' }));
      wsRef.current.close();
    }
    wsRef.current = null;
    setIsRecording(false);
    setPartial('');
    setLastRecognized('');
  };

  const startStreaming = async () => {
    if (disabled || isRecording) return;
    setError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioContext = new AudioContext({ sampleRate: 16000 });
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);

      const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const wsBase = apiBase.replace(/^http/i, (match) =>
        match.toLowerCase() === 'https' ? 'wss' : 'ws'
      );
      const ws = new WebSocket(
        `${wsBase.replace(/\/$/, '')}/ws/stt?session_id=${encodeURIComponent(sessionId)}`
      );
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.error) {
            setError(data.error);
            stopStreaming();
            return;
          }
          if (data.message_type === 'agent_response_error' && data.detail) {
            onRealtimeError?.(data.detail);
            return;
          }
          if (data.message_type === 'agent_response' && data.payload) {
            onAgentResponse?.(data.payload as TalkResponse);
            return;
          }
          if (data.message_type === 'partial_transcript') {
            setPartial(data.text || '');
          } else if (data.message_type === 'final_transcript' && data.text) {
            setPartial('');
            setLastRecognized(data.text);
            if (useRealtime) {
              onRealtimeUserText?.(data.text);
            } else {
              onFallbackTranscript?.(data.text);
            }
          }
        } catch (err) {
          console.error('Failed to parse STT message', err);
        }
      };

      ws.onerror = () => {
        setError('实时语音连接失败');
        stopStreaming();
      };

      processor.onaudioprocess = (event) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          return;
        }
        const input = event.inputBuffer.getChannelData(0);
        const pcm16 = floatTo16BitPCM(input);
        const base64 = arrayBufferToBase64(pcm16.buffer);
        wsRef.current.send(JSON.stringify({ audio_data: base64 }));
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      sourceRef.current = source;
      processorRef.current = processor;
      audioContextRef.current = audioContext;
      streamRef.current = stream;
      setIsRecording(true);
    } catch (err) {
      console.error('Failed to access microphone', err);
      setError('无法访问麦克风');
      stopStreaming();
    }
  };

  const handleRecordClick = async () => {
    if (isRecording) {
      stopStreaming();
    } else {
      await startStreaming();
    }
  };

  useEffect(() => {
    return () => {
      stopStreaming();
    };
  }, []);

  const waveformBars = Array.from({ length: 14 });
  const userDisplay = partial || lastRecognized || (isRecording ? '正在监听…' : '点击开始讲话');

  return (
    <div className="relative flex h-[420px] w-full flex-col overflow-hidden rounded-3xl border border-white/20 bg-black/60 text-white">
      <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-white/10 opacity-70" />
      <div className="absolute inset-0 backdrop-blur-2xl" />
      <div className="relative z-10 flex h-full flex-col justify-between p-6">
        <div className="flex w-full flex-col gap-3 text-sm text-ink-200 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-[45%]">
            <p className="text-[10px] uppercase tracking-[0.5em] text-ink-500">LLM</p>
            <p className="mt-1 text-base leading-relaxed text-ink-100">
              {assistantPreview || '等待语音提问'}
            </p>
          </div>
          <div className="max-w-[45%] text-right">
            <p className="text-[10px] uppercase tracking-[0.5em] text-ink-500">USER</p>
            <p className="mt-1 text-base leading-relaxed text-white">
              {userDisplay}
            </p>
          </div>
        </div>

        <div className="flex flex-col items-center gap-6">
          <div className="flex h-20 w-full items-end justify-center gap-1">
            {waveformBars.map((_, index) => (
              <span
                key={index}
                className={`w-1 rounded-full bg-white/60 ${isRecording ? 'origin-bottom animate-voiceWave' : 'opacity-30'}`}
                style={{ animationDelay: `${index * 0.08}s` }}
              />
            ))}
          </div>

          <button
            onClick={handleRecordClick}
            disabled={disabled}
            className={`group relative flex h-28 w-28 items-center justify-center rounded-full border border-white/20 text-white shadow-2xl transition duration-300 ${
              isRecording ? 'bg-white text-black' : 'bg-white/10 hover:-translate-y-1'
            } disabled:cursor-not-allowed disabled:opacity-30`}
          >
            <Mic className={`h-10 w-10 ${isRecording ? 'text-black' : 'text-white'}`} />
            <span className="absolute -bottom-8 text-xs uppercase tracking-[0.5em] text-ink-400">
              {isRecording ? 'PAUSE' : 'START'}
            </span>
            {isRecording && <span className="absolute inset-0 rounded-full border border-white/40 animate-pulseRing" />}
          </button>

          <div className="text-center text-sm text-ink-400">
            {error
              ? error
              : isRecording
                ? '实时识别中 · 再次点击可暂停'
                : '点击上方按钮开始实时语音'}
          </div>
        </div>
      </div>
    </div>
  );
}

function floatTo16BitPCM(float32Array: Float32Array) {
  const buffer = new ArrayBuffer(float32Array.length * 2);
  const view = new DataView(buffer);
  let offset = 0;
  for (let i = 0; i < float32Array.length; i++, offset += 2) {
    let s = Math.max(-1, Math.min(1, float32Array[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Int16Array(buffer);
}

function arrayBufferToBase64(buffer: ArrayBuffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
