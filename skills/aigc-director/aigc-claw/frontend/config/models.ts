/* ─── Provider + Model 分组结构 ─── */
export interface ModelOption {
    id: string;
    label: string;
    default?: boolean;
}

export interface ProviderGroup {
    provider: string;
    label: string;
    models: ModelOption[];
}

/* ─── LLM 模型（按 Provider 分组） ─── */
export const LLM_PROVIDERS: ProviderGroup[] = [
    {
        provider: 'qwen',
        label: 'Qwen (DashScope)',
        models: [
            { id: 'qwen3.5-plus', label: 'qwen3.5-plus', default: true },
            { id: 'qwen3.5-max', label: 'qwen3.5-max' },
        ],
    },
    {
        provider: 'deepseek',
        label: 'DeepSeek',
        models: [
            { id: 'deepseek-chat', label: 'deepseek-chat' },
            { id: 'deepseek-reasoner', label: 'deepseek-reasoner' },
        ],
    },
    {
        provider: 'openai',
        label: 'OpenAI',
        models: [
            { id: 'gpt-4o', label: 'gpt-4o' },
            { id: 'gpt-4', label: 'gpt-4' },
            { id: 'gpt-5', label: 'gpt-5' },
            { id: 'gpt-5.1', label: 'gpt-5.1' },
            { id: 'o3', label: 'o3' },
        ],
    },
    {
        provider: 'gemini',
        label: 'Gemini',
        models: [
            { id: 'gemini-3-flash-preview', label: 'gemini-3-flash-preview' },
            { id: 'gemini-3-pro-preview', label: 'gemini-3-pro-preview' },
        ],
    },
];

/** 扁平 LLM 列表（向后兼容） */
export const LLM_MODELS: ModelOption[] = LLM_PROVIDERS.flatMap(p => p.models);

/* ─── 文生图 ─── */
export const T2I_PROVIDERS: ProviderGroup[] = [
    {
        provider: 'seedream',
        label: 'Seedream',
        models: [
            { id: 'doubao-seedream-5-0-260128', label: 'Seedream 5.0', default: true },
            { id: 'doubao-seedream-4-5-251128', label: 'Seedream 4.5' },
            { id: 'doubao-seedream-4-0-250828', label: 'Seedream 4.0' },
        ],
    },
    {
        provider: 'jimeng',
        label: 'JiMeng',
        models: [
            { id: 'jimeng_t2i_v40', label: 'jimeng_t2i_v40' },
        ],
    },
    {
        provider: 'dashscope',
        label: 'DashScope',
        models: [
            { id: 'wan2.6-t2i', label: 'wan2.6-t2i' },
        ],
    },
    {
        provider: 'openai',
        label: 'OpenAI',
        models: [
            { id: 'sora_image', label: 'sora_image' },
            { id: 'gpt-image-1.5', label: 'gpt-image-1.5' },
        ],
    },
];

export const T2I_MODELS: ModelOption[] = T2I_PROVIDERS.flatMap(p => p.models);

/* ─── 图生图 ─── */
export const I2I_PROVIDERS: ProviderGroup[] = [
    {
        provider: 'seedream',
        label: 'Seedream',
        models: [
            { id: 'doubao-seedream-5-0-260128', label: 'Seedream 5.0', default: true },
            { id: 'doubao-seedream-4-5-251128', label: 'Seedream 4.5' },
            { id: 'doubao-seedream-4-0-250828', label: 'Seedream 4.0' },
        ],
    },
    {
        provider: 'jimeng',
        label: 'JiMeng',
        models: [
            { id: 'jimeng_t2i_v40', label: 'jimeng_t2i_v40' },
        ],
    },
    {
        provider: 'dashscope',
        label: 'DashScope',
        models: [
            { id: 'wan2.6-image', label: 'wan2.6-image' },
        ],
    },
];

export const I2I_MODELS: ModelOption[] = I2I_PROVIDERS.flatMap(p => p.models);

/* ─── 视频 ─── */
export const VIDEO_PROVIDERS: ProviderGroup[] = [
    {
        provider: 'dashscope',
        label: 'DashScope',
        models: [
            { id: 'wan2.6-i2v-flash', label: 'wan2.6-i2v-flash', default: true },
        ],
    },
    {
        provider: 'kling',
        label: 'Kling',
        models: [
            { id: 'kling-v3', label: 'kling-v3' },
            { id: 'kling-v2-6', label: 'kling-v2-6' },
            { id: 'kling-v2-5-turbo', label: 'kling-v2-5-turbo' },
        ],
    },
];

export const VIDEO_MODELS: ModelOption[] = VIDEO_PROVIDERS.flatMap(p => p.models);

/* ─── VLM 评估模型 ─── */
export const VLM_PROVIDERS: ProviderGroup[] = [
    {
        provider: 'qwen',
        label: 'Qwen (DashScope)',
        models: [
            { id: 'qwen-vl-plus', label: 'qwen-vl-plus', default: true },
            { id: 'qwen3.5-plus', label: 'qwen3.5-plus' },
            { id: 'qwen3.5-max', label: 'qwen3.5-max' },
        ],
    },
    {
        provider: 'gemini',
        label: 'Gemini (Google)',
        models: [
            { id: 'gemini-2.5-flash-image', label: 'gemini-2.5-flash-image' },
            { id: 'gemini-2.5-pro-image', label: 'gemini-2.5-pro-image' },
            { id: 'gemini-3-pro-preview', label: 'gemini-3-pro-preview' },
            { id: 'gemini-3-pro-image-preview', label: 'gemini-3-pro-image-preview' },
        ],
    },
];

export const VLM_MODELS: ModelOption[] = VLM_PROVIDERS.flatMap(p => p.models);

export const STYLES = [
    { id: 'comic-book', label: 'Comic Book / 漫画' },
    { id: 'anime', label: 'Anime / 动漫' },
    { id: 'realistic', label: 'Realistic / 写实' },
    { id: '3d-disney', label: '3D Disney / 迪士尼' },
    { id: 'watercolor', label: 'Watercolor / 水彩' },
    { id: 'oil-painting', label: 'Oil Painting / 油画' },
    { id: 'cyberpunk', label: 'Cyberpunk / 赛博朋克' },
    { id: 'chinese-ink', label: 'Chinese Ink / 水墨' },
];

/* ─── 视频比例 ─── */
export const VIDEO_RATIOS = [
    { id: '16:9', label: '16:9', ratio: '16:9' },
    { id: '9:16', label: '9:16', ratio: '9:16' },
    { id: '1:1', label: '1:1', ratio: '1:1' },
    { id: '4:3', label: '4:3', ratio: '4:3' },
    { id: '3:4', label: '3:4', ratio: '3:4' },
    { id: '21:9', label: '21:9', ratio: '21:9' },
];
