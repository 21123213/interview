// 用户相关类型
export interface User {
  id: number;
  username: string;
  phone: string;
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  phone: string;
  code: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_info: User;
}

// 文件相关类型
export interface FileMetadata {
  id: number;
  user_id: number;
  filename: string;
  original_filename: string;
  file_path: string;
  file_size: number;
  file_type: string | null;
  mime_type: string | null;
  status: string;
  chunks_count: number;
  error_message: string | null;
  upload_time: string;
  processed_time: string | null;
}

export interface FileListResponse {
  total: number;
  items: FileMetadata[];
}

// 对话相关类型
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: ChatSource[];
}

export interface ChatSource {
  content: string;
  score: number;
  metadata?: any;
}

export interface ChatQueryRequest {
  query: string;
  session_id?: string;
  file_ids?: number[];
  /** 向量（语义）融合权重 0~1；与 bm25_weight 会归一化 */
  vector_weight?: number;
  /** BM25（关键词）融合权重 0~1 */
  bm25_weight?: number;
}

export interface ChatQueryResponse {
  answer: string;
  sources: ChatSource[];
  session_id: string;
}

export interface ChatSession {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message: string | null;
}

// 通用响应类型
export interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data?: T;
}

// File Processing Types
export interface ProcessingStatus {
  file_id: string;
  filename: string;
  status: 'pending' | 'processing' | 'processed' | 'completed' | 'failed';
  current_stage?: string;
  progress?: number;
  error?: string;
  partitioning?: PartitioningResult;
  chunking?: ChunkingResult;
  summarization?: SummarizationProgress;
}

export interface PartitioningResult {
  total_elements: number;
  element_types: {
    text_sections: number;
    tables: number;
    images: number;
    titles: number;
    list_items: number;
  };
}

export interface ChunkingResult {
  total_elements: number;
  total_chunks: number;
  avg_chunk_size: number;
}

export interface SummarizationProgress {
  total_chunks: number;
  processed_chunks: number;
  progress_percentage: number;
}

export interface Chunk {
  id: string;
  content: string;
  element_ids: string[];
  element_count?: number;
  character_count: number;
  page_number?: number;
  chunk_type: string;
  content_types?: string[];
  metadata: {
    filename: string;
    page_number?: number;
    element_types: string[];
    content_types?: string[];
  };
}

export interface Element {
  id: string;
  type: string;
  text: string;
  page_number?: number;
}
