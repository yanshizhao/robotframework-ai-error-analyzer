import os

# ================= 路径配置 =================
# 本地保存原始数据的目录
LOCAL_DATA_DIR = os.getenv("SM_LOCAL_DATA_DIR", "./data")

# 确保本地数据目录存在
if not os.path.exists(LOCAL_DATA_DIR):
    try:
        os.makedirs(LOCAL_DATA_DIR)
        print(f"[Config] Created local data directory: {LOCAL_DATA_DIR}")
    except OSError as e:
        print(f"[Config] Error creating directory {LOCAL_DATA_DIR}: {e}")

# 确保目录存在
os.makedirs(LOCAL_DATA_DIR, exist_ok=True)

# 生成的原始数据文件名模板
SMAWS_RAW_FILE_TEMPLATE = "smaps_{pid}.txt"
LIMITS_RAW_FILE_TEMPLATE = "limits_{pid}.txt" 
# 最终分析报告输出文件
OUTPUT_FILE = os.getenv("SM_OUTPUT_FILE", "./report.json")

# 目标服务器 IP
SM_HOST = os.getenv("SM_HOST", "192.168.1.100")

# 如果环境变量未设置，默认使用 22
SM_PORT = int(os.getenv("SM_PORT", "22"))

# SSH 密码 (敏感信息，建议优先使用密钥或环境变量)
SM_PASSWORD = os.getenv("SM_PASSWORD", "")

# SSH 用户名
SM_USER = os.getenv("SM_USER", "root")

# SSH 私钥文件路径 (如果设置了此项，通常优先于密码)
SM_KEY_FILE = os.getenv("SM_KEY_FILE", None)
if SM_KEY_FILE == "":
    SM_KEY_FILE = None  # 防止环境变量设为空字符串导致逻辑错误


# ================= 分析阈值配置 =================
# 栈使用率报警阈值 (%)
# 基于 smaps Size 计算，超过此值视为高风险
STACK_THRESHOLD_PERCENT = float(os.getenv("SM_THRESHOLD", "80.0"))

# ================= 日志配置 =================
LOG_LEVEL = os.getenv("SM_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"