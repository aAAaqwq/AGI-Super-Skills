'use client';

import { useState, useEffect, useRef, DragEvent } from 'react';
import { Sparkles, Image, Video, MessageSquare, Zap, Loader2, ArrowLeft, Copy, Check, Trash2, Settings2, X, FolderOpen, Upload, FileImage, Globe } from 'lucide-react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { LLM_MODELS, T2I_MODELS, I2I_MODELS, VIDEO_MODELS, VLM_MODELS } from '@/config/models';

// 辅助函数：将相对路径转换为完整 URL
const toMediaUrl = (path: string) => {
  if (!path) return '';
  // 如果已经是完整 URL，直接返回
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  // 相对路径添加 /code/ 前缀（result/xxx 格式）
  if (path.startsWith('result/')) {
    return `/code/${path}`;
  } else if (!path.startsWith('/code/')) {
    return `/code/result/${path}`;
  }
  return path;
};

// 工具类型
type ToolType = 'llm' | 'vlm' | 't2i' | 'i2i' | 'video';

interface Tool {
  id: ToolType;
  name: string;
  description: string;
  icon: React.ReactNode;
}

const tools: Tool[] = [
  { id: 'llm', name: 'LLM 对话', description: '文字生成', icon: <MessageSquare className="w-5 h-5" /> },
  { id: 'vlm', name: '图片理解', description: '分析图片内容', icon: <Image className="w-5 h-5" /> },
  { id: 't2i', name: '文生图', description: '文字生成图片', icon: <Sparkles className="w-5 h-5" /> },
  { id: 'i2i', name: '图生图', description: '图片风格转换', icon: <Zap className="w-5 h-5" /> },
  { id: 'video', name: '视频生成', description: '图生视频/文生视频', icon: <Video className="w-5 h-5" /> },
];

// 历史记录类型
interface HistoryRecord {
  id: string;
  tool: string;
  model: string;
  input: {
    prompt?: string;
    images?: string[];
    reference_image?: string;
  };
  output?: {
    response?: string;
    images?: string[];
    video?: string;
    video_path?: string;
  };
  created_at: string;
}

// 图片上传组件
function ImageUploader({
  value,
  onChange,
  required,
  label,
}: {
  value: string;
  onChange: (url: string) => void;
  required?: boolean;
  label: string;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [inputMode, setInputMode] = useState<'url' | 'file'>('file');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      await uploadFile(files[0]);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      await uploadFile(files[0]);
    }
  };

  const uploadFile = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      alert('请选择图片文件');
      return;
    }

    setUploading(true);
    try {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result as string;
        onChange(base64);
        setUploading(false);
      };
      reader.onerror = () => {
        alert('文件读取失败');
        setUploading(false);
      };
      reader.readAsDataURL(file);
    } catch (e) {
      alert('上传失败');
      setUploading(false);
    }
  };

  // 判断是否为 URL
  const isUrl = value.startsWith('http://') || value.startsWith('https://');

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        {label} {required && <span className="text-red-500">*</span>}
      </label>

      {/* 切换 URL / 文件上传 */}
      <div className="flex gap-2 mb-2">
        <button
          type="button"
          onClick={() => setInputMode('url')}
          className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
            inputMode === 'url' ? 'bg-indigo-100 text-indigo-700' : 'text-gray-500 hover:bg-gray-100'
          }`}
        >
          URL 地址
        </button>
        <button
          type="button"
          onClick={() => setInputMode('file')}
          className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
            inputMode === 'file' ? 'bg-indigo-100 text-indigo-700' : 'text-gray-500 hover:bg-gray-100'
          }`}
        >
          本地上传
        </button>
      </div>

      {/* URL 输入模式 */}
      {inputMode === 'url' && (
        <div className="space-y-2">
          <input
            type="text"
            value={isUrl ? value : ''}
            onChange={e => onChange(e.target.value)}
            placeholder="https://example.com/image.jpg"
            className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none"
          />
          {value && isUrl && (
            <div className="relative group">
              <img src={value} alt="预览" className="max-h-48 rounded-lg border border-gray-200" />
              <button
                onClick={() => onChange('')}
                className="absolute top-2 right-2 p-1.5 bg-red-500 text-white rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* 文件上传模式 */}
      {inputMode === 'file' && (
        <>
          {value && !isUrl ? (
            <div className="relative group">
              <img src={value} alt="上传的图片" className="max-h-48 rounded-lg border border-gray-200" />
              <button
                onClick={() => onChange('')}
                className="absolute top-2 right-2 p-1.5 bg-red-500 text-white rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                isDragging ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileSelect}
                className="hidden"
              />
              {uploading ? (
                <Loader2 className="w-8 h-8 mx-auto mb-2 text-indigo-500 animate-spin" />
              ) : (
                <Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
              )}
              <p className="text-sm text-gray-500">
                拖拽图片到此处，或 <span className="text-indigo-600">点击选择文件</span>
              </p>
              <p className="text-xs text-gray-400 mt-1">支持 PNG、JPG、WebP 等格式</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function SandboxPage() {
  const [activeTool, setActiveTool] = useState<ToolType>('llm');
  const [prompt, setPrompt] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // 历史记录状态
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [manageMode, setManageMode] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<HistoryRecord | null>(null);
  const searchParams = useSearchParams();

  // 获取历史记录
  const fetchHistory = async () => {
    try {
      const resp = await fetch('/api/sandbox/history');
      const data = await resp.json();
      if (data.success) {
        setHistory(data.records);
      }
    } catch (e) {
      console.error('Failed to fetch history:', e);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [showHistory]);

  // 检查 URL 参数，自动加载历史记录
  useEffect(() => {
    const recordId = searchParams.get('record');
    if (recordId && history.length > 0) {
      const record = history.find(r => r.id === recordId);
      if (record) {
        setSelectedRecord(record);
        // 填充输入框
        setActiveTool(record.tool as ToolType);
        setPrompt(record.input.prompt || '');
        setImageUrl(record.input.reference_image || record.input.images?.[0] || '');
        // 显示结果
        if (record.output?.response) {
          setResult(record.output.response);
        } else if (record.output?.images?.length) {
          setResult(`生成完成，共 ${record.output.images.length} 张图片`);
        } else if (record.output?.video_path) {
          setResult('视频生成完成');
        }
      }
    }
  }, [searchParams, history]);

  // 删除历史记录
  const deleteRecord = async (id: string) => {
    setDeleting(id);
    try {
      const resp = await fetch(`/api/sandbox/history/${id}`, { method: 'DELETE' });
      const data = await resp.json();
      if (data.success) {
        setHistory(history.filter(r => r.id !== id));
      }
    } catch (e) {
      console.error('Failed to delete:', e);
    } finally {
      setDeleting(null);
    }
  };

  // 根据工具类型获取模型列表
  const getModels = () => {
    switch (activeTool) {
      case 'llm': return LLM_MODELS;
      case 'vlm': return VLM_MODELS;
      case 't2i': return T2I_MODELS;
      case 'i2i': return I2I_MODELS;
      case 'video': return VIDEO_MODELS;
      default: return LLM_MODELS;
    }
  };

  const [selectedModel, setSelectedModel] = useState(getModels()[0]?.id || '');
  const [webSearch, setWebSearch] = useState(false);

  // 工具切换时重置模型选择
  const handleToolChange = (tool: ToolType) => {
    setActiveTool(tool);
    // 立即更新模型选择
    const models = (() => {
      switch (tool) {
        case 'llm': return LLM_MODELS;
        case 'vlm': return VLM_MODELS;
        case 't2i': return T2I_MODELS;
        case 'i2i': return I2I_MODELS;
        case 'video': return VIDEO_MODELS;
        default: return LLM_MODELS;
      }
    })();
    setSelectedModel(models[0]?.id || '');
    setResult(null);
    setError(null);
    setImageUrl('');
  };

  // 监听工具变化，确保模型选择同步
  useEffect(() => {
    const models = (() => {
      switch (activeTool) {
        case 'llm': return LLM_MODELS;
        case 'vlm': return VLM_MODELS;
        case 't2i': return T2I_MODELS;
        case 'i2i': return I2I_MODELS;
        case 'video': return VIDEO_MODELS;
        default: return LLM_MODELS;
      }
    })();
    // 只有当前模型不在新工具的模型列表中时才更新
    const currentInList = models.some(m => m.id === selectedModel);
    if (!currentInList) {
      setSelectedModel(models[0]?.id || '');
    }
  }, [activeTool]);

  // 检查是否可以提交
  const canSubmit = () => {
    if (!prompt.trim() && activeTool !== 't2i') return false;
    if ((activeTool === 'i2i') && !imageUrl) return false;
    return true;
  };

  const handleSubmit = async () => {
    if (!canSubmit()) return;

    setLoading(true);
    setResult(null);
    setError(null);

    try {
      let apiUrl = '';
      let body: Record<string, unknown> = {
        model: selectedModel,
        prompt: prompt,
      };

      switch (activeTool) {
        case 'llm':
          apiUrl = '/api/sandbox/llm';
          // web_search 只对 LLM 有效
          if (webSearch) {
            body.web_search = true;
          }
          break;
        case 'vlm':
          apiUrl = '/api/sandbox/vlm';
          body.images = [imageUrl];
          break;
        case 't2i':
          apiUrl = '/api/sandbox/t2i';
          break;
        case 'i2i':
          apiUrl = '/api/sandbox/i2i';
          body.image = imageUrl;
          break;
        case 'video':
          apiUrl = '/api/sandbox/video';
          body.image = imageUrl;
          break;
      }

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (data.success) {
        if (activeTool === 't2i' || activeTool === 'i2i' || activeTool === 'video') {
          setResult(JSON.stringify(data.result || data.video_path, null, 2));
        } else {
          setResult(data.result);
        }
        fetchHistory();
      } else {
        setError(data.error || '未知错误');
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '请求失败');
    } finally {
      setLoading(false);
    }
  };

  const copyResult = () => {
    if (result) {
      navigator.clipboard.writeText(result);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // 获取工具名称
  const getToolName = (tool: string) => {
    const t = tools.find(x => x.id === tool);
    return t?.name || tool;
  };

  // 格式化日期
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // 获取图片输入的标签
  const getImageLabel = () => {
    switch (activeTool) {
      case 'vlm': return '上传图片';
      case 'i2i': return '参考图片';
      case 'video': return '首帧图片';
      default: return '图片';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
      {/* 顶部导航 */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-gray-800">临时工作台</h1>
              <p className="text-sm text-gray-500">独立调用各种 AI 工具</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setShowHistory(!showHistory); setManageMode(false); }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                showHistory ? 'bg-indigo-100 text-indigo-700' : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              <FolderOpen className="w-3.5 h-3.5" />
              <span>历史记录</span>
            </button>
            {showHistory && (
              <button
                onClick={() => setManageMode(!manageMode)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  manageMode ? 'bg-red-100 text-red-700' : 'text-gray-500 hover:bg-gray-100'
                }`}
              >
                <Settings2 className="w-3.5 h-3.5" />
                <span>{manageMode ? '取消管理' : '管理'}</span>
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {showHistory ? (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-gray-800">历史记录</h2>
              <span className="text-sm text-gray-500">{history.length} 条记录</span>
            </div>

            {history.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>暂无历史记录</p>
              </div>
            ) : (
              <div className="space-y-4">
                {history.map(record => (
                  <div
                    key={record.id}
                    className="bg-white rounded-xl border border-gray-200 overflow-hidden cursor-pointer hover:border-indigo-300 transition-colors"
                    onClick={() => {
                      setSelectedRecord(record);
                      setActiveTool(record.tool as ToolType);
                      setPrompt(record.input.prompt || '');
                      setImageUrl(record.input.reference_image || record.input.images?.[0] || '');
                      if (record.output?.response) {
                        setResult(record.output.response);
                      } else if (record.output?.images?.length) {
                        setResult(`生成完成，共 ${record.output.images.length} 张图片`);
                      } else if (record.output?.video_path) {
                        setResult('视频生成完成');
                      }
                      setShowHistory(false);
                    }}
                  >
                    <div className="p-4 bg-gray-50 border-b border-gray-100">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            record.tool === 'llm' ? 'bg-blue-100 text-blue-700' :
                            record.tool === 'vlm' ? 'bg-green-100 text-green-700' :
                            record.tool === 't2i' ? 'bg-purple-100 text-purple-700' :
                            record.tool === 'i2i' ? 'bg-orange-100 text-orange-700' :
                            'bg-pink-100 text-pink-700'
                          }`}>
                            {getToolName(record.tool)}
                          </span>
                          <span className="text-xs text-gray-400">{record.model}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400">{formatDate(record.created_at)}</span>
                          {manageMode && (
                            <button
                              onClick={() => deleteRecord(record.id)}
                              disabled={deleting === record.id}
                              className="p-1.5 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
                            >
                              {deleting === record.id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Trash2 className="w-4 h-4" />
                              )}
                            </button>
                          )}
                        </div>
                      </div>
                      <p className="text-sm text-gray-700 line-clamp-2">
                        {record.input.prompt || record.input.reference_image || '(无提示词)'}
                      </p>
                      {record.input.images && record.input.images.length > 0 && (
                        <div className="mt-2 flex gap-2 overflow-x-auto">
                          {record.input.images.map((img, i) => (
                            <img key={i} src={toMediaUrl(img)} alt="input" className="h-16 w-auto rounded border border-gray-200" />
                          ))}
                        </div>
                      )}
                    </div>

                    {record.output && (
                      <div className="p-4">
                        {record.output.response && (
                          <pre className="text-sm text-gray-700 whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                            {record.output.response}
                          </pre>
                        )}
                        {record.output.images && record.output.images.length > 0 && (
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            {record.output.images.map((img, i) => (
                              <div key={i} className="relative group">
                                <img src={toMediaUrl(img)} alt={`output-${i}`} className="w-full h-auto rounded-lg border border-gray-200" />
                                <a href={toMediaUrl(img)} target="_blank" rel="noopener noreferrer" className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-lg">
                                  <span className="text-white text-xs">查看大图</span>
                                </a>
                              </div>
                            ))}
                          </div>
                        )}
                        {record.output.video_path && (
                          <div>
                            <video src={toMediaUrl(record.output.video_path)} controls className="w-full max-w-md rounded-lg border border-gray-200" />
                            <a href={toMediaUrl(record.output.video_path)} target="_blank" rel="noopener noreferrer" className="text-sm text-indigo-600 hover:underline mt-2 inline-block">
                              查看视频
                            </a>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            {/* 工具选择 */}
            <div className="grid grid-cols-5 gap-3 mb-8">
              {tools.map(tool => (
                <button
                  key={tool.id}
                  onClick={() => handleToolChange(tool.id)}
                  className={`p-4 rounded-xl border-2 transition-all text-center ${
                    activeTool === tool.id
                      ? 'border-indigo-500 bg-indigo-50 text-indigo-700 shadow-md'
                      : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:shadow-sm'
                  }`}
                >
                  <div className="flex justify-center mb-2">{tool.icon}</div>
                  <div className="font-medium text-sm">{tool.name}</div>
                  <div className="text-xs text-gray-400">{tool.description}</div>
                </button>
              ))}
            </div>

            {/* 输入区域 */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 mb-6">
              {/* 模型选择 */}
              <div className="mb-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-2">选择模型</label>
                    <select
                      value={selectedModel}
                      onChange={e => setSelectedModel(e.target.value)}
                      className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none"
                    >
                      {getModels().map(m => (
                        <option key={m.id} value={m.id}>{m.label}</option>
                      ))}
                    </select>
                  </div>
                  {/* 联网搜索开关 */}
                  {activeTool === 'llm' && (
                    <button
                      onClick={() => setWebSearch(!webSearch)}
                      className={`ml-4 px-4 py-2.5 rounded-lg border-2 flex items-center gap-2 transition-colors ${
                        webSearch
                          ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                          : 'border-gray-200 text-gray-500 hover:border-gray-300'
                      }`}
                    >
                      <Globe className="w-4 h-4" />
                      <span className="text-sm font-medium">联网搜索</span>
                    </button>
                  )}
                </div>
              </div>

              {/* 图片上传（部分工具需要） */}
              {(activeTool === 'vlm' || activeTool === 'i2i' || activeTool === 'video') && (
                <ImageUploader
                  value={imageUrl}
                  onChange={setImageUrl}
                  required={activeTool === 'i2i'}
                  label={getImageLabel()}
                />
              )}

              {/* 提示词输入 */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {activeTool === 'llm' ? '对话内容' :
                   activeTool === 'vlm' ? '想了解图片的什么问题？' :
                   activeTool === 't2i' ? '图片描述（英文效果更好）' :
                   activeTool === 'i2i' ? '希望生成什么样的图片？' :
                   '视频描述（希望生成什么样的视频？）'}
                </label>
                <textarea
                  value={prompt}
                  onChange={e => setPrompt(e.target.value)}
                  placeholder={
                    activeTool === 'llm' ? '输入你想问的问题...' :
                    activeTool === 'vlm' ? '描述这张图片的内容...' :
                    'A cute cat sitting on a couch, realistic style'
                  }
                  rows={4}
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none resize-none"
                />
              </div>

              {/* 提交按钮 */}
              <button
                onClick={handleSubmit}
                disabled={loading || !canSubmit()}
                className="w-full py-3 px-6 bg-indigo-600 text-white font-medium rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>处理中...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    <span>生成</span>
                  </>
                )}
              </button>
            </div>

            {/* 结果展示 */}
            {(result || error) && (
              <div className={`rounded-2xl border p-6 ${error ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className={`font-medium ${error ? 'text-red-700' : 'text-green-700'}`}>
                    {error ? '错误' : '结果'}
                  </h3>
                  {!error && result && (
                    <button onClick={copyResult} className="p-2 rounded-lg hover:bg-white/50 transition-colors" title="复制结果">
                      {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4 text-gray-500" />}
                    </button>
                  )}
                </div>
                {error ? (
                  <p className="text-red-600 text-sm">{error}</p>
                ) : (
                  <pre className="text-sm text-gray-700 whitespace-pre-wrap break-words max-h-96 overflow-y-auto">
                    {result}
                  </pre>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
