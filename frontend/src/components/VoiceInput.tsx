import { Mic, Upload } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

interface VoiceInputProps {
  onAudioReady: (audioBlob: Blob) => void;
  onTranscript?: (text: string) => void;
  disabled?: boolean;
}

export function VoiceInput({ onAudioReady, onTranscript, disabled }: VoiceInputProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [partial, setPartial] = useState('');
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
      const ws = new WebSocket(`${wsBase.replace(/\/$/, '')}/ws/stt`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.error) {
            setError(data.error);
            stopStreaming();
            return;
          }
          if (data.message_type === 'partial_transcript') {
            setPartial(data.text || '');
          } else if (data.message_type === 'final_transcript' && data.text) {
            setPartial('');
            onTranscript?.(data.text);
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

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onAudioReady(file);
      e.target.value = ''; // 重置文件输入
    }
  };

  useEffect(() => {
    return () => {
      stopStreaming();
    };
  }, []);

  return (
    <div className="flex flex-col items-center gap-4">
      <button
        onClick={handleRecordClick}
        disabled={disabled}
        className={`flex h-20 w-20 items-center justify-center rounded-full text-white transition-all ${
          isRecording
            ? 'animate-pulse bg-red-600 hover:bg-red-700'
            : 'bg-red-500 hover:scale-110 hover:bg-red-600'
        } disabled:cursor-not-allowed disabled:bg-gray-300 disabled:hover:scale-100`}
      >
        <Mic className="h-8 w-8" />
      </button>

      <div className="text-center text-sm text-gray-600">
        {isRecording ? '实时识别中，点击停止' : '点击按钮开始实时语音'}
      </div>

      {partial && (
        <div className="rounded-xl bg-gray-50 px-4 py-2 text-sm text-gray-700">
          {partial}
        </div>
      )}

      {error && (
        <div className="text-sm text-red-600">{error}</div>
      )}

      <div className="relative">
        <input
          type="file"
          accept="audio/*"
          onChange={handleFileUpload}
          disabled={disabled}
          className="hidden"
          id="audio-upload"
        />
        <label
          htmlFor="audio-upload"
          className={`flex cursor-pointer items-center gap-2 rounded-lg bg-gray-500 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-600 ${
            disabled ? 'cursor-not-allowed opacity-50' : ''
          }`}
        >
          <Upload className="h-4 w-4" />
          或上传音频文件
        </label>
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
