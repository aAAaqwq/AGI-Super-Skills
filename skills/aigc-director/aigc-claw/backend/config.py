import os

# 尝试加载 .env 文件 (需要: pip install python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class Config:
    # ==========================
    # 基础服务配置
    # ==========================
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    
    # 控制是否打印发送给模型的提示词/输入 (LLM, Image, Video)
    PRINT_MODEL_INPUT = os.getenv("PRINT_MODEL_INPUT", "False").lower() == "true"
    
    # ==========================
    # 路径配置 (自动计算绝对路径)
    # ==========================
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # 生成结果存放目录
    CODE_DIR = os.path.join(BASE_DIR, 'code')
    RESULT_DIR = os.path.join(CODE_DIR, 'result')
    
    # 临时文件目录
    TEMP_DIR = os.path.join(BASE_DIR, 'temp')

    # ==========================
    # AI 模型 API 配置
    # ==========================
    # LLM (OpenAI / Gemini)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    # 官方 OpenAI API Key（用于 gpt-image-1.5 等必须直连官方的模型）
    OPENAI_OFFICIAL_API_KEY = os.getenv("OPENAI_OFFICIAL_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GOOGLE_GEMINI_BASE_URL = os.getenv("GOOGLE_GEMINI_BASE_URL", "")

    # Dashscope(Aliyun) API
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")

    # 可灵 (Kling AI) API
    KLING_ACCESS_KEY = os.getenv("KLING_ACCESS_KEY", "")
    KLING_SECRET_KEY = os.getenv("KLING_SECRET_KEY", "")
    KLING_BASE_URL = os.getenv("KLING_BASE_URL", "https://api-beijing.klingai.com")

    # 字节跳动 ARK (Seedream) API
    ARK_API_KEY = os.getenv("ARK_API_KEY", "")
    ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

    # ==========================
    # 第三方中转站（Relay）配置
    # ==========================
    # 统一中转 API，支持 OpenAI 兼容格式，一个 key 调用所有模型
    # 支持的中转站：青云 (qingyun)、Xingsuancode 等
    RELAY_API_KEY = os.getenv("RELAY_API_KEY", "")
    RELAY_BASE_URL = os.getenv("RELAY_BASE_URL", "")
    # 可选：指定中转站名称，用于日志标识
    RELAY_PROVIDER_NAME = os.getenv("RELAY_PROVIDER_NAME", "relay")

    # 管理员密码（用于删除历史记录等管理操作）
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    # 代理设置
    PROXY = os.getenv("PROXY", "")
    LOCAL_PROXY = os.getenv("LOCAL_PROXY", "http://127.0.0.1:7897")
    HTTP_PROXY = os.getenv("HTTP_PROXY", "")
    HTTPS_PROXY = os.getenv("HTTPS_PROXY", "")
    
    # ==========================
    # 视频生成参数配置
    # ==========================
    # 1. 剧本生成
    LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5-plus") # LLM 模型选择

    # 2. VLM 评估模型
    VLM_MODEL = os.getenv("VLM_MODEL", "qwen3.5-plus")

    # 3. 图片生成 (分镜)
    IMAGE_IT2I_MODEL = os.getenv("IMAGE_IT2I_MODEL", "doubao-seedream-5-0-260128")
    IMAGE_T2I_MODEL = os.getenv("IMAGE_T2I_MODEL", "doubao-seedream-5-0-260128")

    # 3. 视频生成
    # 可选: "wan2.6-i2v-flash"
    VIDEO_MODEL = os.getenv("VIDEO_MODEL", "wan2.6-i2v-flash")
    VIDEO_RATIO = os.getenv("VIDEO_RATIO", "16:9") 

    @classmethod
    def check_dirs(cls):
        """自动创建必要的目录"""
        for directory in [cls.CODE_DIR, cls.RESULT_DIR, cls.TEMP_DIR]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"Created directory: {directory}")

# 初始化目录结构
Config.check_dirs()

# 导出一个单例
settings = Config()
