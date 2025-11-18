import { useEffect, useRef } from 'react';
import { Message as MessageType } from '../types';
import { Message } from './Message';

interface ChatContainerProps {
  messages: MessageType[];
}

export function ChatContainer({ messages }: ChatContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 自动滚动到底部
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div
      ref={containerRef}
      role="log"
      aria-live="polite"
      className="h-[420px] space-y-4 overflow-y-auto pr-2 scroll-smooth"
    >
      {messages.map((message, index) => (
        <Message key={index} message={message} />
      ))}
    </div>
  );
}
