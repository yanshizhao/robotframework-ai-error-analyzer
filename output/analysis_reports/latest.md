# 🚨 Robot Framework 测试错误分析报告

### 📊 测试概览
- **失败用例**: 1 / 总用例: 1
- **分析时间**: 2026-04-04 11:58:10
- **日志文件**: reports/output.xml

---
### ❌ 失败用例 1: 单进程栈内存使用率测试

**错误摘要**: Failed to download smaps for PID 99999

### 🔍 根本原因
**：在尝试从远程服务器下载 PID 为 `99999` 的进程的 `/proc/[pid]/smaps` 文件时失败。
    *   **可能原因**：
        1.  **进程不存在**：PID 99999 可能是一个无效的进程 ID（通常 PID 从 1 开始），或者该进程在测试执行前已经终止。
        2.  **权限不足**：SSH 用户可能没有权限读取 `/proc` 下的文件。
        3.  **网络/SSH 问题**：虽然 SSH 连接建立成功，但在下载特定文件时出现超时或连接中断。

### 🔧 修复方案
建议在 `StackMonitorKeywords.采集并分析进程栈内存` 方法中增加 **异常捕获** 机制，以便更清晰地定位是网络问题还是进程不存在问题。

**修改代码片段** (`StackMonitorKeywords.py`):

```python
    def 采集并分析进程栈内存(self, 进程ID):
        """
        采集指定PID的栈内存数据并进行分析
        :param 进程ID: 目标进程ID
        :return: (栈上限KB, 实际使用KB)
        """
        if not self.ssh_client:
            raise Exception("请先建立SSH连接")

        # 下载原始数据
        try:
            local_files = self.ssh_client.download_proc_files(int(进程ID))
            logger.info(f"栈内存原始数据已下载：smaps={local_files['smaps']}, limits={local_files['limits']}")
        except Exception as e:
            # 记录详细错误日志，便于排查
            logger.error(f"下载进程 {进程ID} 的 smaps 失败: {str(e)}")
            # 重新抛出异常，确保 Robot Framework 能捕获到并标记测试失败
            raise Exception(f"Failed to download smaps for PID {进程ID}: {str(e)}")

        # 分析数据
        analyzer = StackAnalyzer(
            smaps_file_path=local_files['smaps'],
            limits_file_path=local_files['limits']
        )
        limit_kb, usage_kb = analyzer.analyze_smaps()
        self.analysis_result = (int(进程ID), limit_kb, usage_kb)
        # ... (省略后续代码)
```

### 📜 完整调用链
```
[OK]    连接 SSH服务器 <StackMonitorKeywords>
    参数: ${TEST_HOST}, ${TEST_USER}, 密码=ysz3868082
[ERROR] 采集并分析进程栈内存 <StackMonitorKeywords>
    参数: ${TEST_PID}
    错误: Failed to download smaps for PID 99999
[OK]    Set Variable <BuiltIn>
    参数: ${OUTPUT_DIR}/stack_monitor/stack_report_${TEST_PID}.json
[OK]    生成栈内存分析报告 <StackMonitorKeywords>
    参数: 输出文件路径=${report_path}, 使用率阈值=${USAGE_THRESHOLD}
[OK]    Should Be Equal <BuiltIn>
    参数: ${status}, PASS
```

---
💡 完整分析日志已保存到系统，如需查看详细推理过程可查看JSON报告。
