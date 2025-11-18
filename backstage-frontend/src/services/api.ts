import { ProductionQueueSnapshot } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export class ApiService {
  static async getQueueSnapshot(limit = 50): Promise<ProductionQueueSnapshot> {
    const response = await fetch(`${API_BASE_URL}/production/queue?limit=${limit}`);
    if (!response.ok) {
      throw new Error('无法获取制作队列');
    }
    return response.json();
  }
}
