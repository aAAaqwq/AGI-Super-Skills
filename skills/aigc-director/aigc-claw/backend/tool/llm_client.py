import os
import logging

try:
    from tool.llm_gpt import GPT
    from tool.llm_gemini import Gemini
    from tool.llm_deepseek import DeepSeek
    from tool.llm_dashscope import QwenLLM
    from tool.relay_client import RelayClient
except ImportError:
    from llm_gpt import GPT
    from llm_gemini import Gemini
    from llm_deepseek import DeepSeek
    from llm_dashscope import QwenLLM
    from relay_client import RelayClient

from config import Config

logger = logging.getLogger(__name__)

class LLM:
    def __init__(self, gemini_base_url="", gemini_api_key="", gpt_base_url="", gpt_api_key="", deepseek_base_url="", deepseek_api_key="", dashscope_api_key=""):
        self.gemini_base_url = gemini_base_url or os.getenv("GOOGLE_GEMINI_BASE_URL", "")
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.gpt_base_url = gpt_base_url or os.getenv("OPENAI_BASE_URL", "")
        self.gpt_api_key = gpt_api_key or os.getenv("OPENAI_API_KEY", "")
        self.deepseek_base_url = deepseek_base_url or os.getenv("DEEPSEEK_BASE_URL", "")
        self.deepseek_api_key = deepseek_api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.dashscope_api_key = dashscope_api_key or os.getenv("DASHSCOPE_API_KEY", "")

        # 初始化中转站客户端（如果配置了）
        self._relay_client = None
        relay_key = os.getenv("RELAY_API_KEY", "")
        relay_url = os.getenv("RELAY_BASE_URL", "")
        if relay_key and relay_url:
            try:
                self._relay_client = RelayClient(api_key=relay_key, base_url=relay_url)
                logger.info("Relay client 初始化成功")
            except Exception as e:
                logger.warning(f"Relay client 初始化失败: {e}")

    def full_to_half(self, text):
        if not isinstance(text, str):
            return text
        
        translation_table = {0x3000: 0x0020}
        for i in range(65281, 65375):
            translation_table[i] = i - 65248
            
        return text.translate(translation_table)

    def query(self, prompt, image_urls=[], model="gemini-3-flash-preview", safe_content=True, task_id=None, web_search=False):
        """
        Query the LLM with a prompt and optional image URLs.
        Selects the backend (GPT or Gemini) based on the model name.

        :param web_search: Enable web search for supported providers
        """
        if safe_content:
            prompt = self.full_to_half(prompt)

        if not model:
            model = "gemini-3-flash-preview"
            
        if Config.PRINT_MODEL_INPUT:
            print("---- LLM QUERY REQUEST ----")
            print(f"Model: {model}")
            if task_id:
                print(f"Task ID: {task_id}")
            if image_urls:
                print(f"Images: {len(image_urls)}")
                for u in image_urls:
                    print(f"  - {u}")
            print(f"Prompt: {prompt[:200]}{'...' if len(prompt) > 200 else ''}")
            print("-" * 30)
            
        result = ""
        model_lower = model.lower()

        # 判断是否通过中转站调用（优先级：config_model.json 中 provider=relay）
        is_relay_model = self._is_relay_model(model_lower)

        if is_relay_model and self._relay_client:
            # 通过中转站统一调用
            result = self._relay_client.chat(prompt, model=model, image_urls=image_urls, web_search=web_search)
        elif model_lower.startswith("gemini"):
            # Gemini client handles its own credentials internally in the current implementation,
            # but we pass args for consistency/future compatibility.
            # Note: Gemini doesn't have built-in web search parameter, user needs to use Function Calling
            client = Gemini(base_url=self.gemini_base_url, api_key=self.gemini_api_key)
            result = client.query(prompt, image_urls=image_urls, model=model)
        elif model_lower.startswith("deepseek"):
            client = DeepSeek(base_url=self.deepseek_base_url, api_key=self.deepseek_api_key)
            result = client.query(prompt, image_urls=image_urls, model=model, web_search=web_search)
        elif "qwen" in model_lower:
            # Qwen models via DashScope Generation API (text-only mode)
            client = QwenLLM(api_key=self.dashscope_api_key)
            result = client.query(prompt, image_urls=image_urls, model=model, web_search=web_search)
        else:
            # OpenAI 系列: gpt-4, gpt-4o, gpt-5, gpt-5.1, o3 等
            client = GPT(base_url=self.gpt_base_url, api_key=self.gpt_api_key)
            result = client.query(prompt, image_urls=image_urls, model=model, web_search=web_search)

        if safe_content:
            result = self.full_to_half(result)
        
        # Remove empty lines
        return '\n'.join([line for line in result.split('\n') if line.strip() != ''])

    def _is_relay_model(self, model_lower: str) -> bool:
        """
        判断模型是否应通过中转站调用
        优先读取 config_model.json 中的 provider 字段，
        如果未配置或中转站不可用，则回退到直连。
        """
        if not self._relay_client:
            return False

        # 尝试从 config_model.json 读取 provider
        try:
            import json
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config_model.json"
            )
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                model_info = config.get("models", {}).get(model_lower)
                if model_info and model_info.get("provider") == "relay":
                    return True
        except Exception:
            pass

        return False
