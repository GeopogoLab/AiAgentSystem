import { Mic, Upload } from 'lucide-react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';

interface VoiceInputProps {
  onAudioReady: (audioBlob: Blob) => void;
  disabled?: boolean;
}

export function VoiceInput({ onAudioReady, disabled }: VoiceInputProps) {
  const { isRecording, error, toggleRecording } = useAudioRecorder();

  const handleRecordClick = async () => {
    if (disabled) return;

    const audioBlob = await toggleRecording();
    if (audioBlob) {
      onAudioReady(audioBlob);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onAudioReady(file);
      e.target.value = ''; // 重置文件输入
    }
  };

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
        {isRecording ? '录音中，点击停止' : '点击按钮开始录音'}
      </div>

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
