# -*- coding: utf-8 -*-
"""
智能体基类 - 所有阶段智能体的抽象接口
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, Callable

logger = logging.getLogger(__name__)


class AgentInterface(ABC):
    """所有智能体必须实现的接口"""

    def __init__(self, name: str = ""):
        self.name = name
        self.cancellation_check: Optional[Callable] = None
        self.progress_callback: Optional[Callable] = None

    def set_cancellation_check(self, fn: Callable):
        self.cancellation_check = fn

    def set_progress_callback(self, fn: Callable):
        self.progress_callback = fn

    def _report_progress(self, phase: str, step_desc: str, percent: float, data: dict = None):
        if self.progress_callback:
            self.progress_callback(phase, step_desc, percent, data)

    def _check_cancel(self):
        if self.cancellation_check and self.cancellation_check():
            raise RuntimeError(f"Agent [{self.name}] cancelled by user")

    def _cancellable_query(self, llm, prompt: str, **kwargs):
        """在 LLM 调用前后检查取消状态"""
        self._check_cancel()
        result = llm.query(prompt, **kwargs)
        self._check_cancel()
        return result

    # -------- 抽象方法 --------

    @abstractmethod
    async def process(self, input_data: Any, intervention: Optional[Dict] = None) -> Dict:
        """
        核心处理逻辑

        Args:
            input_data: 来自上一阶段的输入数据
            intervention: 用户介入修改内容

        Returns:
            dict: { "payload": ..., "requires_intervention": bool }
        """
        pass
