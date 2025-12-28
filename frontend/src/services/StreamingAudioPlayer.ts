/**
 * Streaming Audio Player - 流式音频播放器
 *
 * 使用 Web Audio API 实现边接收边播放的流式音频播放器。
 *
 * 特点：
 * - 无缝衔接多个音频块
 * - 低延迟（边接收边播放）
 * - 自动计算播放时间避免间隙
 */

export class StreamingAudioPlayer {
  private audioContext: AudioContext | null = null;
  private sourceNodes: AudioBufferSourceNode[] = [];
  private nextStartTime = 0;
  private isPlaying = false;

  constructor() {
    // 创建 AudioContext（兼容性处理）
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) {
      throw new Error('Web Audio API not supported in this browser');
    }
    this.audioContext = new AudioContextClass();
  }

  /**
   * 添加音频块到播放队列
   *
   * @param base64Data Base64 编码的音频数据
   * @param format 音频格式（mp3, wav, etc.）
   */
  async enqueueChunk(base64Data: string, format: string = 'mp3'): Promise<void> {
    if (!this.audioContext) {
      throw new Error('AudioContext not initialized');
    }

    // Resume context if suspended (浏览器自动暂停策略)
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }

    try {
      // Base64 → ArrayBuffer
      const arrayBuffer = this.base64ToArrayBuffer(base64Data);

      // 解码音频数据
      const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);

      // 创建播放节点
      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.audioContext.destination);

      // 计算播放时间（无缝衔接）
      const currentTime = this.audioContext.currentTime;
      const startTime = Math.max(currentTime, this.nextStartTime);

      // 开始播放
      source.start(startTime);
      this.nextStartTime = startTime + audioBuffer.duration;

      this.sourceNodes.push(source);
      this.isPlaying = true;

      // 清理已播放的节点
      source.onended = () => {
        const index = this.sourceNodes.indexOf(source);
        if (index > -1) {
          this.sourceNodes.splice(index, 1);
        }
        if (this.sourceNodes.length === 0) {
          this.isPlaying = false;
        }
      };
    } catch (error) {
      console.error('Failed to enqueue audio chunk:', error);
      throw new Error(`Audio decoding failed: ${error}`);
    }
  }

  /**
   * Base64 转 ArrayBuffer
   */
  private base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binaryString = atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  }

  /**
   * 停止所有播放
   */
  stop(): void {
    this.sourceNodes.forEach((node) => {
      try {
        node.stop();
      } catch (e) {
        // 节点可能已停止，忽略错误
      }
    });
    this.sourceNodes = [];
    this.nextStartTime = 0;
    this.isPlaying = false;
  }

  /**
   * 销毁播放器（释放资源）
   */
  destroy(): void {
    this.stop();
    this.audioContext?.close();
    this.audioContext = null;
  }

  /**
   * 获取播放状态
   */
  get playing(): boolean {
    return this.isPlaying;
  }

  /**
   * 检查 Web Audio API 支持
   */
  static isSupported(): boolean {
    return !!(window.AudioContext || (window as any).webkitAudioContext);
  }
}
