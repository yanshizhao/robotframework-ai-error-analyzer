import re
import logging
import os

logger = logging.getLogger(__name__)

class StackAnalyzer:
    """
    专用于单进程单线程场景的分析器。
    输入：本地 smaps 文件路径 (limits 文件可选，仅作保留)
    输出：(栈上限 KB, 栈实际使用量 KB)
    
    核心逻辑：
    1. 栈上限 (Limit) = smaps 中 [stack] 段的 Size 字段 (实际分配的虚拟内存)
    2. 栈使用量 (Usage) = smaps 中 [stack] 段的 (Rss + Swap) 字段
    """
    
    def __init__(self, smaps_file_path: str, limits_file_path: str = None):
        if not os.path.exists(smaps_file_path):
            raise FileNotFoundError(f"Smaps file not found: {smaps_file_path}")
            
        self.smaps_path = smaps_file_path
        self.limits_path = limits_file_path # 仅保留引用，暂未使用

    def analyze_smaps(self) -> tuple:
        """
        从本地 smaps 文件解析主线程栈的【上限】和【实际使用量】。
        
        返回:
        tuple: (limit_kb, usage_kb)
            - limit_kb: [stack] 段的 Size (虚拟地址空间大小，即真实上限)
            - usage_kb: [stack] 段的 Rss + Swap (实际物理占用)
        """
        try:
            with open(self.smaps_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            stack_data = {
                "size_kb": 0,
                "rss_kb": 0,
                "swap_kb": 0,
                "found": False
            }
            
            current_is_stack = False
            
            lines = content.split('\n')
            for line in lines:
                line_stripped = line.strip()
                
                # 1. 检测映射行 (地址行)
                # 格式: 00007ffeed6ca000-00007ffeed6db000 rw-p 00000000 00:00 0 [stack]
                if re.match(r'^[0-9a-f]+-[0-9a-f]+', line_stripped):
                    if '[stack' in line_stripped:
                        current_is_stack = True
                        # 重置数据，准备读取新段 (单线程通常只有一个)
                        stack_data = {"size_kb": 0, "rss_kb": 0, "swap_kb": 0, "found": True}
                    else:
                        current_is_stack = False
                    continue
                
                # 2. 如果是栈段，提取关键指标
                if current_is_stack:
                    if line_stripped.startswith('Size:'):
                        match = re.search(r'Size:\s+(\d+)\s+kB', line_stripped)
                        if match:
                            stack_data["size_kb"] = int(match.group(1))
                    
                    elif line_stripped.startswith('Rss:'):
                        match = re.search(r'Rss:\s+(\d+)\s+kB', line_stripped)
                        if match:
                            stack_data["rss_kb"] = int(match.group(1))
                            
                    elif line_stripped.startswith('Swap:'):
                        match = re.search(r'Swap:\s+(\d+)\s+kB', line_stripped)
                        if match:
                            stack_data["swap_kb"] = int(match.group(1))
            
            if not stack_data["found"]:
                logger.error("No [stack] segment found in smaps file! Is the process single-threaded?")
                return (0, 0)
            
            if stack_data["size_kb"] == 0:
                logger.error("Found [stack] segment but Size is 0. Invalid data.")
                return (0, 0)
            
            limit_kb = stack_data["size_kb"]
            usage_kb = stack_data["rss_kb"] + stack_data["swap_kb"]
            
            logger.info(f"[Local Analysis] Stack Segment Found:")
            logger.info(f"  - Limit (Size):   {limit_kb} KB ({round(limit_kb/1024, 2)} MB)")
            logger.info(f"  - Usage (Rss):    {stack_data['rss_kb']} KB")
            logger.info(f"  - Usage (Swap):   {stack_data['swap_kb']} KB")
            logger.info(f"  - Total Usage:    {usage_kb} KB ({round(usage_kb/1024, 2)} MB)")
            
            return (limit_kb, usage_kb)

        except Exception as e:
            logger.error(f"Error parsing smaps file: {e}")
            raise