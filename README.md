 🤖 Robot Framework AI 错误分析器

  智能驱动的自动化测试失败分析工具，结合大语言模型自动定位错误根因，给出可落地修复方案

  🎯 项目简介

  基于 Robot Framework自动化测试框架的基础上的二次开发，通过解析output.xml日志、还原关键字调用链、关联对应Python源码，调用大语言模型智能
  分析测试失败原因，大幅降低自动化测试失败的排查成本，让测试人员从繁琐的错误定位中解放出来。

  解决的核心痛点：
  - ❌ 测试失败后需要人工翻日志、查代码，耗时耗力
  - ❌ 新手看不懂复杂的调用链，定位问题效率低
  - ❌ 相同错误重复出现，每次都要重新排查
  - ✅ 使用词错误分析器，可快速得到错误根因+修复方案

  ✨ 功能亮点

                          

   🚀 超高性能解析: 流式增量解析，支持GB级超大output.xml，内存占用<50MB，解析速度提升      

    🧠 智能AI分析 : 对接智谱GLM-4大模型，结合业务代码上下文给出精准的根因分析和修复方案              

    🌐 中文原生支持 ：完美支持中文关键字、中文报错信息                      

    🔗 代码自动关联 : 自动扫描关键字库，建立关键字到Python代码的精准映射，AI分析直接关联源码           

    📊 直观报告输出 : 生成简洁Markdown/结构化JSON双格式报告，支持流水线集成、消息推送                 

    🔧 完整调试能力 : 支持debug模式查看完整Prompt、AI响应、关键字匹配过程，方便排查                   

    🤝 高兼容性 : 兼容Robot Framework 3.x ~ 7.x全版本                  


  🚀 快速开始

  1. 环境准备

  # 克隆项目

  git clone https://github.com/yanshizhao/robotframework-ai-error-analyzer.git

  cd robotframework-ai-analyzer

  # 安装依赖

  pip install -r requirements.txt

  # 配置API Key（替换为你自己的智谱AI Key）

  export ZHIPUAI_API_KEY="your_zhipu_api_key_here"
  Windows PowerShell: $env:ZHIPUAI_API_KEY="your_zhipu_api_key_here"

  # 复制配置文件模板

  cd ai_analyzer/config
  cp config.yaml.template config.yaml

  # 如需自定义配置可修改config.yaml，默认配置可直接使用

  cd ../../

  2. 一键分析

  python ai_analyzer/ai_analyzer.py --input 你的output.xml路径

  3. 查看报告

  分析完成后，报告自动生成在 output/analysis_reports/ 目录：

  latest.md   # 最新Markdown格式报告，直接打开查看
  latest.json # 最新JSON格式报告，用于系统集成

  # 完整使用流程

  1. 运行测试生成output.xml

  # 常规Robot运行，指定输出目录

  robot --output output/output.xml cases/

  # 或使用内置脚本自动运行+分析

  scripts/run_tests.bat  # Windows
  scripts/run_tests.sh   # Linux/Mac

  2. 自动分析失败用例

  测试失败时自动触发AI分析，无需人工干预。

  3. 报告示例

  # 🚨 Robot Framework 测试错误分析报告

  ### 📊 测试概览
  - **失败用例**: 1 / 总用例: 1
  - **分析时间**: 2026-04-07 10:30:00
  ---

  ### ❌ 失败用例 1: 单进程栈内存使用率测试
  **错误摘要**: Failed to download smaps for PID 99999


  ### 🔍 根本原因
  目标PID `99999` 在服务器上不存在，属于测试数据配置错误

  ### 🔧 修复方案
  1. 测试前通过`ps`命令动态获取目标进程PID，不要硬编码
  2. 增加PID合法性校验关键字

  ### 📜 完整调用链
  [OK]    连接 SSH服务器
  [ERROR] 采集并分析进程栈内存
      参数: ${TEST_PID}
      错误: Failed to download smaps for PID 99999

  ## ⚙️ 核心配置
  
  配置文件路径：`ai_analyzer/config/config.yaml`
  ```yaml
  # AI配置
  ai:
    model: glm-4.7-flash    # AI模型，推荐用glm-4.7-flash性价比最高
    timeout: 120            # 超时时间(秒)
    enable_thinking: false  # 深度思考开关，更精准但更慢

  # 代码库配置
  codebase:
    libs_path: ./libs       # 你的关键字库路径
    indexing:
      method: naming        # 索引方式: naming(中文关键字)/decorator(@keyword装饰)

  # 日志配置
  logger:
    debug: false            # 调试模式开关，排查问题时开启


  ❓ 常见问题

  Q: AI调用失败提示网络错误

  A: 检查网络是否能访问智谱AI服务，API Key是否正确，是否还有调用额度。

  Q: 关键字匹配不到，没有代码片段

  A: 检查libs_path是否指向正确的关键字目录，中文关键字请用naming索引模式。

  Q: 超大文件解析内存溢出

  A: 已默认流式解析，不会OOM，确认没有开启parse_all=True全量解析模式。

  Q: 分析结果不符合预期

  A: 开启debug模式--debug查看发送给AI的上下文是否完整，可自定义ai_prompts.yaml优化提示词。


  📄 许可证

  MIT License - 详见 LICENSE 文件