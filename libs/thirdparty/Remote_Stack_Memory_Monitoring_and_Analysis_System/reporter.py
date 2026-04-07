import json
import logging
from config import OUTPUT_FILE, STACK_THRESHOLD_PERCENT

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self, output_file=OUTPUT_FILE, threshold=STACK_THRESHOLD_PERCENT):
        self.output_file = output_file
        self.threshold = threshold

    def generate(self, pid: int, limit_kb: int, usage_kb: int, threshold: float = None) -> bool:
        """
        生成报告
        :param pid: 进程ID
        :param limit_kb: 栈上限
        :param usage_kb: 栈实际使用量
        :param threshold: (可选) 临时覆盖阈值。如果为 None，则使用 self.threshold
        :return: True if PASS, False if FAIL
        """
        # 如果传入了 threshold 参数，则使用传入的值，否则使用实例自带的默认值
        current_threshold = threshold if threshold is not None else self.threshold

        if limit_kb <= 0:
            logger.error("Stack limit (from smaps Size) is 0 or invalid.")
            usage_percent = 0.0
            status = "ERROR"
        else:
            usage_percent = (usage_kb / limit_kb) * 100
            status = "FAIL" if usage_percent > current_threshold else "PASS"
            
        result_data = {
            "pid": pid,
            "analysis_mode": "Single-Threaded (Local smaps)",
            "stack_limit_source": "smaps Size field (Actual Virtual Allocation)",
            "stack_limit_kb": limit_kb,          
            "stack_actual_usage_kb": usage_kb,   
            "usage_percent": round(usage_percent, 2),
            "threshold_percent": current_threshold, 
            "status": status,
            "note": "Limit is the actual virtual memory size allocated for the stack."
        }
        
        # 保存到本地 JSON
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=4)
            logger.info(f"Report saved to {self.output_file}")
        except IOError as e:
            logger.error(f"Failed to save report: {e}")
            raise

        # 打印控制台报告 
        self._print_console(pid, limit_kb, usage_kb, usage_percent, status, current_threshold)
        
        return status == "PASS"

    def _print_console(self, pid: int, limit: int, usage: int, percent: float, status: str, threshold: float = None):
        """
        打印控制台报告
        :param threshold: 可选参数。如果提供，优先使用此阈值显示；否则使用 self.threshold
        """
        # 确定最终显示的阈值
        display_threshold = threshold if threshold is not None else self.threshold

        print("\n" + "="*60)
        print(f"📊 Single-Process Stack Analysis Report (Local Data)")
        print("="*60)
        print(f"PID:                 {pid}")
        print(f"Stack Limit (smaps Size): {limit} KB  ({round(limit/1024, 2)} MB)")
        print(f"Actual Usage (Rss+Swap):  {usage} KB  ({round(usage/1024, 2)} MB)")
        print("-" * 60)
        print(f"Usage Rate:          {percent:.2f}%")
        print(f"Threshold:           {display_threshold}%") 
        print("="*60)
        
        if status == "FAIL":
            print("❌ [FAIL] Stack usage exceeded threshold!")
            print("   ⚠️  Risk of stack overflow detected in main thread.")
            print("   💡  Suggestion: Check for deep recursion or large local arrays.")
        elif status == "ERROR":
            print("❌ [ERROR] Could not calculate usage rate (Limit is 0).")
        else:
            print("✅ [PASS] Stack usage is within safe limits.")
            print("   Main thread stack is healthy.")
        
        print("="*60 + "\n")