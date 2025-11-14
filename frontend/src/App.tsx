import { useState, useEffect } from 'react';
import { RotateCcw } from 'lucide-react';
import { ChatContainer } from './components/ChatContainer';
import { OrderInfo } from './components/OrderInfo';
import { ModeSelector } from './components/ModeSelector';
import { TextInput } from './components/TextInput';
import { VoiceInput } from './components/VoiceInput';
import { ApiService } from './services/api';
import { generateSessionId } from './services/utils';
import { Message, OrderState, InputMode } from './types';

const initialOrderState: OrderState = {
  drink_name: null,
  size: null,
  sugar: null,
  ice: null,
  toppings: [],
  notes: null,
  is_complete: false,
};

function App() {
  const [sessionId] = useState(() => generateSessionId());
  const [mode, setMode] = useState<InputMode>('text');
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: '您好！欢迎光临，我可以帮您点单。请告诉我您想要什么饮品～',
    },
  ]);
  const [orderState, setOrderState] = useState<OrderState>(initialOrderState);
  const [status, setStatus] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState(false);

  const handleSendText = async (text: string) => {
    if (!text.trim() || isProcessing) return;

    // 添加用户消息
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setStatus('正在处理...');
    setIsProcessing(true);

    try {
      const response = await ApiService.sendText(sessionId, text);

      // 添加 AI 回复
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: response.assistant_reply },
      ]);

      // 更新订单状态
      setOrderState(response.order_state);

      // 更新状态文本
      if (response.order_id) {
        setStatus(`订单已保存！订单号：#${response.order_id}`);
      } else {
        setStatus('');
      }
    } catch (error) {
      console.error('Error sending text:', error);
      setStatus('发送失败，请重试');
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '抱歉，发送失败，请重试。' },
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSendAudio = async (audioBlob: Blob) => {
    if (isProcessing) return;

    setStatus('正在识别语音...');
    setIsProcessing(true);

    try {
      const response = await ApiService.sendAudio(sessionId, audioBlob);

      // 添加 AI 回复
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: response.assistant_reply },
      ]);

      // 更新订单状态
      setOrderState(response.order_state);

      // 更新状态文本
      if (response.order_id) {
        setStatus(`订单已保存！订单号：#${response.order_id}`);
      } else {
        setStatus('');
      }
    } catch (error) {
      console.error('Error sending audio:', error);
      setStatus('语音识别失败，请重试');
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '抱歉，语音识别失败，请重试。' },
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = async () => {
    if (!confirm('确定要重新开始吗？当前订单信息将被清除。')) {
      return;
    }

    try {
      await ApiService.resetSession(sessionId);

      // 重置状态
      setMessages([
        {
          role: 'assistant',
          content: '您好！欢迎光临，我可以帮您点单。请告诉我您想要什么饮品～',
        },
      ]);
      setOrderState(initialOrderState);
      setStatus('会话已重置');
      setTimeout(() => setStatus(''), 2000);
    } catch (error) {
      console.error('Error resetting session:', error);
      setStatus('重置失败');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-500 to-secondary-500 p-5 flex items-center justify-center">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-8 shadow-2xl">
        {/* Header */}
        <div className="mb-6 text-center">
          <h1 className="mb-2 text-3xl font-bold text-primary-600">
            🧋 奶茶点单 AI
          </h1>
          <p className="text-sm text-gray-600">语音或文字，轻松点单！</p>
        </div>

        {/* Chat Container */}
        <ChatContainer messages={messages} />

        {/* Controls */}
        <div className="mt-6 space-y-4">
          {/* Mode Selector */}
          <ModeSelector mode={mode} onModeChange={setMode} />

          {/* Input Area */}
          <div className="min-h-[100px]">
            {mode === 'text' ? (
              <TextInput onSend={handleSendText} disabled={isProcessing} />
            ) : (
              <VoiceInput onAudioReady={handleSendAudio} disabled={isProcessing} />
            )}
          </div>

          {/* Status */}
          {status && (
            <div className="text-center text-sm text-gray-600">{status}</div>
          )}

          {/* Reset Button */}
          <button
            onClick={handleReset}
            disabled={isProcessing}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-gray-500 py-3 font-medium text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:bg-gray-300"
          >
            <RotateCcw className="h-4 w-4" />
            重新开始
          </button>
        </div>

        {/* Order Info */}
        <OrderInfo orderState={orderState} />
      </div>
    </div>
  );
}

export default App;
