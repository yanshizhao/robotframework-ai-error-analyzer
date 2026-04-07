import logging
import os
from config import LOCAL_DATA_DIR, SMAWS_RAW_FILE_TEMPLATE, LIMITS_RAW_FILE_TEMPLATE

logger = logging.getLogger(__name__)

class SSHClientWrapper:
    """
    连接服务器并【下载】原始数据到本地文件。
    """
    def __init__(self, hostname, username, password=None, key_file=None, port=22):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_file = key_file
        self.port = port
        self.client = None
        try:
            import paramiko
            self.paramiko = paramiko
        except ImportError:
            logger.error("Paramiko library not found. Please install: pip install paramiko")
            raise

    def connect(self):
        """建立 SSH 连接"""
        try:
            self.client = self.paramiko.SSHClient()
            self.client.set_missing_host_key_policy(self.paramiko.AutoAddPolicy())
            
            if self.key_file:
                self.client.connect(self.hostname, port=self.port, username=self.username, key_filename=self.key_file)
            else:
                self.client.connect(self.hostname, port=self.port, username=self.username, password=self.password)
                logger.info(f"Connected to {self.hostname} as {self.username}")
                return True
        except Exception as e:
            logger.error(f"SSH Connection failed: {e}")
            return False

    def close(self):
        """关闭 SSH 连接"""
        if self.client:
            self.client.close()
            logger.info("SSH connection closed.")

    def download_proc_files(self, pid: int) -> dict:
        """
        从服务器抓取 /proc/{pid}/smaps (仅栈相关) 和 /proc/{pid}/limits
        并保存到本地文件。
        """
        if not self.client:
            raise Exception("SSH client not connected. Call connect() first.")
        
        local_paths = {}
        
        # ---------------------------------------------------------
        # 1. 抓取 smaps (核心数据源) - 【仅过滤 [stack] 段】
        # ---------------------------------------------------------
        # 使用 awk 进行流式过滤：
        # 逻辑：
        # 1. 匹配到包含 "[stack" 的行 (例如 [stack] 或 [stack:123]) -> 设置标志位 printing=1
        # 2. 如果 printing=1，打印当前行。
        # 3. 如果遇到新的内存段起始行 (格式为 十六进制-十六进制 ...) 且不是 stack -> 设置 printing=0
        # 注意：/proc/pid/smaps 的段头格式通常是 "0000...-0000... ..."
        smaps_remote_cmd = (
            f"awk '/\\[stack/{{printing=1}} "
            f"printing && /^[0-9a-f]+-[0-9a-f]+/{{if(!/\\[stack/) printing=0}} "
            f"printing' /proc/{pid}/smaps"
        )
        
        smaps_local_file = os.path.join(LOCAL_DATA_DIR, SMAWS_RAW_FILE_TEMPLATE.format(pid=pid))
        
        logger.info(f"Downloading stack-only smaps for PID {pid} to {smaps_local_file}...")
        success = self._exec_and_save(smaps_remote_cmd, smaps_local_file)
        
        if not success:
            # 如果过滤命令失败，尝试降级为完整下载（以防 awk 版本兼容性问题）
            logger.warning("Stack filtering failed via awk. Falling back to full smaps download...")
            fallback_cmd = f"cat /proc/{pid}/smaps"
            success = self._exec_and_save(fallback_cmd, smaps_local_file)
            if not success:
                raise Exception(f"Failed to download smaps for PID {pid}")
        
        # 验证是否抓到了数据
        if os.path.getsize(smaps_local_file) == 0:
            logger.error(f"Downloaded smaps file is empty. PID {pid} might not have a stack or does not exist.")
            # raise Exception(f"No stack data found for PID {pid}")
            
        local_paths['smaps'] = smaps_local_file
        
        # ---------------------------------------------------------
        # 2. 抓取 limits
        # ---------------------------------------------------------
        limits_remote_cmd = f"cat /proc/{pid}/limits"
        limits_local_file = os.path.join(LOCAL_DATA_DIR, LIMITS_RAW_FILE_TEMPLATE.format(pid=pid))
        
        logger.info(f"Downloading limits for PID {pid} to {limits_local_file}...")
        success = self._exec_and_save(limits_remote_cmd, limits_local_file)
        
        if not success:
            logger.warning("Failed to download limits file, but continuing with smaps analysis.")
            local_paths['limits'] = None
        else:
            local_paths['limits'] = limits_local_file
        
        return local_paths

    def _exec_and_save(self, cmd: str, local_path: str) -> bool:
        """执行命令并将 stdout 保存到本地文件"""
        try:
            stdin, stdout, stderr = self.client.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status != 0:
                error_msg = stderr.read().decode('utf-8')
                logger.error(f"Command failed ({exit_status}): {error_msg}")
                return False
            
            content = stdout.read().decode('utf-8')
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.debug(f"Saved {len(content)} bytes to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing command or saving file: {e}")
            return False