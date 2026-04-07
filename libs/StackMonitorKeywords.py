import sys
import os
# 添加内部源项目到Python路径，自包含部署
SOURCE_PROJECT_PATH = os.path.join(os.path.dirname(__file__), "thirdparty", "Remote_Stack_Memory_Monitoring_and_Analysis_System")
sys.path.append(SOURCE_PROJECT_PATH)

from ssh_client import SSHClientWrapper
from analyzer import StackAnalyzer
from reporter import ReportGenerator
from config import *
from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn

class StackMonitorKeywords:
    """远程栈内存监控系统关键字库，支持SSH连接、栈内存采集、分析和报告生成"""
    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'  # 测试套件级别作用域，连接复用

    def __init__(self):
        self.ssh_client = None
        self.analysis_result = None
        self.report_path = None

    def 连接SSH服务器(self, 主机地址, 用户名, 密码=None, 密钥文件路径=None, 端口=22):
        """
        建立与远程Linux服务器的SSH连接
        :param 主机地址: 服务器IP或域名
        :param 用户名: SSH登录用户名
        :param 密码: SSH登录密码（可选，优先使用密钥）
        :param 密钥文件路径: SSH私钥文件路径（可选）
        :param 端口: SSH端口，默认22
        :return: 连接成功返回True，失败抛出异常
        """
        self.ssh_client = SSHClientWrapper(
            hostname=主机地址,
            username=用户名,
            password=密码,
            key_file=密钥文件路径,
            port=int(端口)
        )
        success = self.ssh_client.connect()
        if not success:
            raise Exception(f"SSH连接失败：{主机地址}:{端口}")
        logger.info(f"SSH连接成功：{主机地址}:{端口}，用户名：{用户名}")
        return True

    def 关闭SSH连接(self):
        """关闭当前SSH连接"""
        if self.ssh_client:
            self.ssh_client.close()
            logger.info("SSH连接已关闭")

    def 采集并分析进程栈内存(self, 进程ID):
        """
        采集指定PID的栈内存数据并进行分析
        :param 进程ID: 目标进程ID
        :return: (栈上限KB, 实际使用KB)
        """
        if not self.ssh_client:
            raise Exception("请先建立SSH连接")

        # 下载原始数据
        local_files = self.ssh_client.download_proc_files(int(进程ID))
        logger.info(f"栈内存原始数据已下载：smaps={local_files['smaps']}, limits={local_files['limits']}")

        # 分析数据
        analyzer = StackAnalyzer(
            smaps_file_path=local_files['smaps'],
            limits_file_path=local_files['limits']
        )
        limit_kb, usage_kb = analyzer.analyze_smaps()
        self.analysis_result = (int(进程ID), limit_kb, usage_kb)

        usage_percent = round(usage_kb/limit_kb*100, 2) if limit_kb > 0 else 0
        logger.info(f"进程{进程ID}栈内存分析结果：上限={limit_kb}KB，实际使用={usage_kb}KB，使用率={usage_percent}%")
        return limit_kb, usage_kb

    def 生成栈内存分析报告(self, 输出文件路径=None, 使用率阈值=80.0):
        """
        生成栈内存分析报告
        :param 输出文件路径: 报告保存路径，默认使用系统配置路径
        :param 使用率阈值: 报警阈值百分比，默认80%
        :return: 报告结果，PASS/FAIL/ERROR
        """
        if not self.analysis_result:
            raise Exception("请先执行栈内存采集分析")

        pid, limit_kb, usage_kb = self.analysis_result
        reporter = ReportGenerator(
            output_file=输出文件路径 if 输出文件路径 else OUTPUT_FILE,
            threshold=float(使用率阈值)
        )
        is_pass = reporter.generate(pid, limit_kb, usage_kb)
        self.report_path = reporter.output_file

        status = "PASS" if is_pass else "FAIL" if limit_kb > 0 else "ERROR"
        logger.info(f"分析报告已生成：{self.report_path}，结果：{status}")
        return status

    def 验证栈使用率是否合格(self, 最大允许使用率=80.0):
        """
        验证栈内存使用率是否在允许范围内，超过则测试失败
        :param 最大允许使用率: 最大允许使用率百分比，默认80%
        """
        if not self.analysis_result:
            raise Exception("请先执行栈内存采集分析")

        pid, limit_kb, usage_kb = self.analysis_result
        if limit_kb <= 0:
            BuiltIn().fail(f"进程{pid}栈上限数据无效，无法验证")

        usage_percent = (usage_kb / limit_kb) * 100
        if usage_percent > float(最大允许使用率):
            BuiltIn().fail(f"进程{pid}栈使用率{round(usage_percent, 2)}%超过阈值{最大允许使用率}%，上限={limit_kb}KB，使用={usage_kb}KB")
        logger.info(f"进程{pid}栈使用率验证通过：{round(usage_percent, 2)}% ≤ {最大允许使用率}%")
