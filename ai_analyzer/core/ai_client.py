import os
import time
import json
from typing import Dict, Any, Optional
from jinja2 import Template
import requests

from ai_analyzer.utils.file_utils import load_yaml_config
from ai_analyzer.utils.logger import setup_logger

class ZhipuAIClient:
    """智谱AI客户端"""

    def __init__(self, config: Dict[str, Any], logger, debug_mode: bool = False):
        self.config = config
        self.logger = logger
        self.debug_mode = debug_mode
        self.timeout = config.get('timeout', 120)
        self.max_retries = config.get('max_retries', 3)
        self.temperature = config.get('temperature', 0.3)
        self.max_tokens = config.get('max_tokens', 4096)

        from zai import ZhipuAiClient
        self.api_key = config['zhipuai']['api_key']
        self.model = config['zhipuai'].get('model', 'glm-4.7-flash')
        self.enable_thinking = config['zhipuai'].get('enable_thinking', False)
        self.client = ZhipuAiClient(api_key=self.api_key)

    def call(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        def _call():
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # 调试模式：打印完整Prompt
            if self.debug_mode:
                self.logger.debug("="*80)
                self.logger.debug("【发送给AI的完整Prompt】")
                self.logger.debug("="*80)
                for msg in messages:
                    self.logger.debug(f"[{msg['role']}]:\n{msg['content']}")
                self.logger.debug("="*80)

            # 构建请求参数
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }

            # 启用深度思考（仅支持glm-4.7-flash及以上模型）
            if self.enable_thinking and 'flash' in self.model.lower():
                params["thinking"] = {"type": "enabled"}

            response = self.client.chat.completions.create(**params)
            result = response.choices[0].message.content.strip()

            # 调试模式：打印AI原始响应
            if self.debug_mode:
                self.logger.debug("="*80)
                self.logger.debug("【AI返回的原始响应】")
                self.logger.debug("="*80)
                self.logger.debug(result)
                self.logger.debug("="*80)

            return result

        for attempt in range(self.max_retries):
            try:
                return _call()
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"AI调用失败，已重试{self.max_retries}次: {str(e)}") from e
                wait_time = 2 ** attempt
                self.logger.warning(f"AI调用失败，{wait_time}秒后重试: {str(e)}")
                time.sleep(wait_time)

class AIPromptManager:
    """AI提示词管理器"""

    def __init__(self, prompts_config_path: str):
        self.prompts = load_yaml_config(prompts_config_path)

    def render_prompt(self, prompt_name: str, **kwargs) -> str:
        """渲染提示词模板"""
        if prompt_name not in self.prompts:
            raise ValueError(f"提示词模板不存在: {prompt_name}")

        template = Template(self.prompts[prompt_name])
        return template.render(**kwargs)
