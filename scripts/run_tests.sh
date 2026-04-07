#!/bin/bash
set -e

# ============================================================
# Robot Framework 测试运行 + AI错误分析包装脚本 (Linux/Mac版)
# ============================================================

echo "========================================"
echo "Robot Framework 测试 + AI错误分析"
echo "========================================"

# 设置环境变量
# 优先读取系统环境变量，如果没有设置请手动修改
export SSH_PASSWORD=${SSH_PASSWORD:-""}
export TEST_PID=${TEST_PID:-"4107"}  # 示例PID，可根据实际情况修改
export ZHIPUAI_API_KEY=${ZHIPUAI_API_KEY:-""}

# 本地测试示例配置
# export SSH_PASSWORD="你的SSH密码"
# export TEST_PID="4107"
# export ZHIPUAI_API_KEY="你的智谱AI API Key"

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "${SCRIPT_DIR}/.."

# 创建输出目录
mkdir -p output
mkdir -p output/temp
mkdir -p output/analysis_reports

# 执行Robot测试
echo
echo "[1/2] 开始执行Robot测试..."
echo

robot --output output/output.xml \
      --log output/log.html \
      --report output/report.html \
      --outputdir output \
      --xunit output/xunit.xml \
      --loglevel TRACE \
      cases/stack_monitor/

TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    echo
    echo "========================================"
    echo "测试执行成功！"
    echo "========================================"
    echo
    echo "测试报告: output/report.html"
    echo "日志报告: output/log.html"
    echo
    exit 0
fi

# 测试失败，执行AI错误分析
echo
echo "========================================"
echo "测试执行失败！"
echo "========================================"
echo
echo "[2/2] 开始AI错误分析..."
echo

python ai_analyzer/ai_analyzer.py --input output/output.xml

AI_RESULT=$?

if [ $AI_RESULT -eq 0 ]; then
    echo
    echo "========================================"
    echo "AI分析完成！"
    echo "========================================"
    echo
    echo "测试报告: output/report.html"
    echo "日志报告: output/log.html"
    echo "AI分析报告: output/analysis_reports/latest.md"
    echo
else
    echo
    echo "========================================"
    echo "AI分析失败！"
    echo "========================================"
    echo
fi

exit $TEST_RESULT
