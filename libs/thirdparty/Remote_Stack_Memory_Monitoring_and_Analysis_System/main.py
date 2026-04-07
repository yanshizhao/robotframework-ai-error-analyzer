import logging
import sys
import os
import argparse 

from config import LOG_LEVEL, LOG_FORMAT, LOCAL_DATA_DIR, STACK_THRESHOLD_PERCENT
from ssh_client import SSHClientWrapper
from analyzer import StackAnalyzer
from reporter import ReportGenerator

# 配置日志
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Linux 进程栈内存监控工具 (单进程版)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # SSH 连接参数
    parser.add_argument("--host", type=str, default=None, 
                        help="目标服务器 IP 地址 (优先级高于环境变量 SM_HOST)")
    parser.add_argument("--port", type=int, default=22, 
                        help="SSH 端口 (默认: 22)")
    parser.add_argument("--user", type=str, default=None, 
                        help="SSH 用户名 (优先级高于环境变量 SM_USER)")
    parser.add_argument("--password", type=str, default=None, 
                        help="SSH 密码 (优先级高于环境变量 SM_PASSWORD)")
    parser.add_argument("--key-file", type=str, default=None, dest="key_file",
                        help="SSH 私钥文件路径 (优先级高于环境变量 SM_KEY_FILE)")
    
    # 监控目标参数
    parser.add_argument("--pid", type=int, default=None, 
                        help="目标进程 PID (优先级高于环境变量 SM_PID)")
    
    # 其他参数
    parser.add_argument("--threshold", type=float, default=None, 
                        help=f"栈使用率报警阈值 %% (默认: {STACK_THRESHOLD_PERCENT}, 优先级高于环境变量 SM_THRESHOLD)")

    return parser.parse_args()

def main():
    # 1. 解析命令行参数
    args = parse_args()
    
    # 2. 配置合并逻辑：命令行参数 > 环境变量 > 默认值
    # 如果命令行传了值就用命令行的，否则读环境变量，最后给个兜底默认值
    HOST = args.host if args.host else os.getenv("SM_HOST", "192.168.1.100")
    PORT = args.port if args.port != 22 else int(os.getenv("SM_PORT", "22"))
    USER = args.user if args.user else os.getenv("SM_USER", "root")
    PASSWORD = args.password if args.password else os.getenv("SM_PASSWORD", "")
    KEY_FILE = args.key_file if args.key_file else os.getenv("SM_KEY_FILE", None)
    
    # PID 必须提供，要么通过命令行，要么通过环境变量
    if args.pid is not None:
        TARGET_PID = args.pid
    elif os.getenv("SM_PID"):
        TARGET_PID = int(os.getenv("SM_PID"))
    else:
        logger.error("Missing target PID. Please use --pid <PID> or set env SM_PID.")
        sys.exit(1)
        
    # 阈值处理
    THRESHOLD = args.threshold if args.threshold is not None else STACK_THRESHOLD_PERCENT

    logger.info(f"Starting Stack Monitor for PID {TARGET_PID} on {USER}@{HOST}:{PORT}")
    logger.info(f"Threshold set to {THRESHOLD}%")
    
    ssh = None
    try:
        # 1. 连接并下载数据
        logger.info("Step 1: Connecting to server and downloading raw data...")
        ssh = SSHClientWrapper(HOST, USER, password=PASSWORD, key_file=KEY_FILE, port=PORT)
        
        if not ssh.connect():
            logger.error("Failed to connect to server. Exiting.")
            sys.exit(1)
            
        local_files = ssh.download_proc_files(TARGET_PID)
        smaps_path = local_files['smaps']
        limits_path = local_files.get('limits') 
        
        logger.info("Data download complete.")
        
        # 2. 关闭 SSH 连接
        ssh.close()
        ssh = None 
        
        # 3. 初始化分析器
        logger.info("Step 2: Analyzing local smaps file...")
        analyzer = StackAnalyzer(smaps_path, limits_path)
        
        limit_kb, usage_kb = analyzer.analyze_smaps()
        
        if limit_kb == 0:
            logger.error("Analysis failed: Stack limit is 0.")
            sys.exit(1)
            
        logger.info(f"Analysis complete: Limit={limit_kb}KB, Usage={usage_kb}KB")
        
        # 4. 生成报告
        logger.info("Step 3: Generating report...")
        reporter = ReportGenerator()
        # 将用户设定的阈值传给报告生成器
        is_pass = reporter.generate(TARGET_PID, limit_kb, usage_kb, threshold=THRESHOLD)
        
        if is_pass:
            logger.info("Process finished successfully. Status: PASS")
            sys.exit(0)
        else:
            logger.warning("Process finished with warnings. Status: FAIL")
            sys.exit(1)
            
    except FileNotFoundError as e:
        logger.error(f"File error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        if ssh:
            ssh.close()
        sys.exit(1)

if __name__ == "__main__":
    main()