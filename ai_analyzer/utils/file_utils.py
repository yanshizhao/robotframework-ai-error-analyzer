import os
import yaml
import re
from typing import Dict, Any

def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """加载YAML配置文件，自动替换环境变量占位符 ${VAR_NAME:-default}"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"配置文件不存在: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 替换环境变量占位符
    def replace_env_var(match):
        var_def = match.group(1)
        if ':-' in var_def:
            var_name, default = var_def.split(':-', 1)
            return os.environ.get(var_name.strip(), default.strip())
        else:
            var_name = var_def.strip()
            value = os.environ.get(var_name)
            if value is None:
                raise ValueError(f"环境变量未设置: {var_name}")
            return value

    # 匹配 ${VAR_NAME} 或 ${VAR_NAME:-default}
    content = re.sub(r'\$\{([^}]+)\}', replace_env_var, content)

    try:
        config = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise RuntimeError(f"解析YAML配置文件失败: {str(e)}") from e

    return config

def ensure_dir_exists(dir_path: str) -> None:
    """确保目录存在，不存在则创建"""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
