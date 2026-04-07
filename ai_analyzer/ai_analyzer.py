#!/usr/bin/env python3
"""
Robot Framework AI错误分析器主入口
"""

import os
import sys
import argparse
import json
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_analyzer.core.robot_parser import RobotParser
from ai_analyzer.core.ai_client import AIPromptManager
from ai_analyzer.core.code_indexer import CodeIndexer
from ai_analyzer.utils.file_utils import load_yaml_config, ensure_dir_exists
from ai_analyzer.utils.logger import setup_logger

class AIAnalyzer:
    """AI分析器主类"""

    def __init__(self, config_path: Optional[str] = None, prompts_path: Optional[str] = None):
        # 加载配置
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = config_path or os.path.join(base_dir, "config", "config.yaml")
        self.prompts_path = prompts_path or os.path.join(base_dir, "config", "ai_prompts.yaml")

        self.config = load_yaml_config(self.config_path)
        self.prompt_manager = AIPromptManager(self.prompts_path)

        # 初始化日志
        self.debug_mode = self.config.get('logger', {}).get('debug', False)
        log_level = 'DEBUG' if self.debug_mode else self.config.get('logger', {}).get('level', 'INFO')

        self.logger = setup_logger(
            log_level=log_level,
            log_file=self.config.get('logger', {}).get('file'),
            console=self.config.get('logger', {}).get('console', True)
        )

        # 初始化智谱AI客户端，传入debug模式
        from ai_analyzer.core.ai_client import ZhipuAIClient
        self.ai_client = ZhipuAIClient(self.config['ai'], self.logger, self.debug_mode)

        # 初始化代码索引器
        self.code_indexer = CodeIndexer(self.config, self.logger)

        # 确保输出目录存在
        self.reports_dir = self.config.get('output', {}).get('reports_dir', './output/analysis_reports')
        ensure_dir_exists(self.reports_dir)

    def analyze_test_failure(self, test_case) -> Dict[str, Any]:
        """分析单个测试用例失败"""
        self.logger.info(f"开始分析测试用例: {test_case.name}")

        # 构建关键字调用链字符串，并收集相关代码片段
        keyword_chain_str = ""
        code_snippets = {}
        include_code = self.config.get('output', {}).get('include_code_snippets', True)
        max_code_lines = self.config.get('output', {}).get('max_code_lines', 20)

        for i, kw in enumerate(test_case.keyword_chain, 1):
            keyword_chain_str += f"{i}. {kw.name} (来自: {kw.owner})\n"
            keyword_chain_str += f"   参数: {', '.join(kw.arguments)}\n"
            if kw.error_message:
                keyword_chain_str += f"   错误: {kw.error_message}\n"
            keyword_chain_str += "\n"

            # 收集相关代码
            if include_code and kw.owner != 'BuiltIn':  # 跳过BuiltIn关键字
                keywords_found = self.code_indexer.find_keyword_by_name(kw.name, kw.owner)
                if keywords_found:
                    code = self.code_indexer.get_keyword_code(kw.name, kw.owner, max_code_lines)
                    key = f"{kw.owner}.{kw.name}"
                    code_snippets[key] = {
                        "file_path": keywords_found[0].file_path,
                        "line_number": keywords_found[0].line_number,
                        "code": code
                    }
                    # 调试模式：打印关键字匹配日志
                    if self.debug_mode:
                        self.logger.debug(f"[关键字匹配] 成功匹配: {kw.owner}.{kw.name} -> 文件: {keywords_found[0].file_path}:{keywords_found[0].line_number}")
                elif self.debug_mode:
                    self.logger.debug(f"[关键字匹配] 未找到: {kw.owner}.{kw.name}")

        # 渲染提示词
        prompt = self.prompt_manager.render_prompt(
            "error_analysis",
            test_case_name=test_case.name,
            suite_name=test_case.suite,
            source_file=test_case.source_file,
            line_number=test_case.line_number,
            error_message=test_case.error_message or "无顶层错误信息，请看关键字错误",
            tags=", ".join(test_case.tags),
            keyword_chain=keyword_chain_str,
            code_snippets=code_snippets if code_snippets else None
        )

        # 调用AI分析
        try:
            analysis_result = self.ai_client.call(
                prompt,
                system_prompt="你是专业的Robot Framework测试错误分析专家，擅长定位测试失败原因并给出可行的修复方案。"
            )
            self.logger.info(f"测试用例 {test_case.name} 分析完成")
        except Exception as e:
            self.logger.error(f"AI分析失败: {str(e)}")
            analysis_result = f"AI分析失败: {str(e)}"

        # 转换关键字调用链为可序列化的字典
        def keyword_to_dict(kw):
            return {
                "name": kw.name,
                "owner": kw.owner,
                "arguments": kw.arguments,
                "status": kw.status,
                "error_message": kw.error_message,
                "children": [keyword_to_dict(child) for child in kw.children]
            }

        keyword_chain_dict = [keyword_to_dict(kw) for kw in test_case.keyword_chain]

        # 构建结果
        result = {
            "test_case": test_case.name,
            "suite": test_case.suite,
            "source_file": test_case.source_file,
            "line_number": test_case.line_number,
            "status": test_case.status,
            "error_message": test_case.error_message,
            "tags": test_case.tags,
            "keyword_chain": keyword_chain_dict,
            "analysis": analysis_result,
            "analyzed_at": datetime.now().isoformat()
        }

        return result

    def analyze_output_xml(self, xml_path: str) -> Dict[str, Any]:
        """分析整个output.xml文件"""
        self.logger.info(f"开始分析Robot输出文件: {xml_path}")

        # 解析XML
        parser = RobotParser(xml_path)
        stats = parser.get_statistics()
        failed_cases = parser.get_failed_test_cases()
        global_errors = parser.get_global_errors()

        self.logger.info(f"解析完成，总用例: {stats['total']}, 失败: {len(failed_cases)}, 全局错误: {len(global_errors)}")

        # 分析每个失败用例
        analysis_results = []
        for case in failed_cases:
            result = self.analyze_test_failure(case)
            analysis_results.append(result)

        # 构建最终结果
        final_result = {
            "summary": {
                "total_tests": stats["total"],
                "passed_tests": stats["passed"],
                "failed_tests": len(failed_cases),
                "skipped_tests": stats["skipped"],
                "global_errors": len(global_errors),
                "analyzed_at": datetime.now().isoformat(),
                "xml_file": xml_path
            },
            "global_errors": global_errors,
            "failed_cases_analysis": analysis_results
        }

        # 保存结果
        self._save_results(final_result)

        return final_result

    def _save_results(self, result: Dict[str, Any]) -> None:
        """保存分析结果"""
        output_format = self.config.get('output', {}).get('format', 'both')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存JSON格式
        if output_format in ('json', 'both'):
            json_file = os.path.join(self.reports_dir, f"error_analysis_{timestamp}.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            # 创建latest副本（Windows下不用软链接）
            latest_json = os.path.join(self.reports_dir, "latest.json")
            import shutil
            shutil.copy2(json_file, latest_json)
            self.logger.info(f"JSON报告已保存到: {json_file}")
     
        # 保存Markdown格式
        if output_format in ('markdown', 'both'):
            md_file = os.path.join(self.reports_dir, f"error_analysis_{timestamp}.md")
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(self._generate_markdown_report(result))

            # 创建latest副本
            latest_md = os.path.join(self.reports_dir, "latest.md")
            shutil.copy2(md_file, latest_md)
            self.logger.info(f"Markdown报告已保存到: {md_file}")

    def _generate_call_chain_tree(self, keywords, indent=0) -> str:
        """生成树状可视化调用链（支持字典格式）"""
        tree_str = ""
        for i, kw in enumerate(keywords):
            prefix = "    " * indent
            # 标记状态
            status_icon = "[ERROR] " if kw.get('status') in ("FAIL", "ERROR") else "[OK]    "
            # 树形前缀
            tree_prefix = "└── " if indent > 0 else ""
            # 添加当前关键字
            tree_str += f"{prefix}{tree_prefix}{status_icon}{kw.get('name')} <{kw.get('owner')}>\n"
            tree_str += f"{prefix}    参数: {', '.join(kw.get('arguments', []))}\n"
            if kw.get('error_message'):
                tree_str += f"{prefix}    错误: {kw.get('error_message', '')[:100]}{'...' if len(kw.get('error_message', '')) > 100 else ''}\n"
            # 递归处理子关键字
            if kw.get('children'):
                tree_str += self._generate_call_chain_tree(kw.get('children'), indent + 1)
        return tree_str

    def _generate_markdown_report(self, result: Dict[str, Any]) -> str:
        """生成简洁版Markdown格式报告，突出核心问题和解决方案"""
        md = "# 🚨 Robot Framework 测试错误分析报告\n\n"
        md += "### 📊 测试概览\n"
        md += f"- **失败用例**: {result['summary']['failed_tests']} / 总用例: {result['summary']['total_tests']}\n"
        md += f"- **分析时间**: {result['summary']['analyzed_at'].split('T')[0]} {result['summary']['analyzed_at'].split('T')[1][:8]}\n"
        md += f"- **日志文件**: {result['summary']['xml_file']}\n\n"

        # 遍历失败用例
        if result['failed_cases_analysis']:
            for i, case in enumerate(result['failed_cases_analysis'], 1):
                md += f"---\n"
                md += f"### ❌ 失败用例 {i}: {case['test_case']}\n\n"   
                # case['error_message'][:150]：截取错误信息中的前 150 个字符，如果原文超过150字符，添加省略号
                md += f"**错误摘要**: {case['error_message'][:150]}{'...' if len(case['error_message'])>150 else ''}\n\n"

                # 提取AI分析中的核心部分：根本原因和修复方案
                analysis = case['analysis']
                if not analysis or "AI分析失败" in analysis:
                    md += "### 🔍 AI分析失败\n网络或API调用异常，请稍后重试\n\n"
                else:
                    # 提取根本原因（支持多种关键词）
                    reason_keywords = ['根本原因', '错误定位', '问题原因', '原因分析']
                    reason_found = False
                    for keyword in reason_keywords:
                        if keyword in analysis:
                            reason_start = analysis.find(keyword)
                            # 将 next_title_pos 初始化为 AI 分析文本的末尾位置。
                            next_title_pos = len(analysis)
                            
                            for next_keyword in ['###', '##', '\n##', '\n###', '修复方案', '解决方案', '修复建议', '影响分析']:
                                pos = analysis.find(next_keyword, reason_start + len(keyword))
                                if pos != -1 and pos < next_title_pos:
                                    next_title_pos = pos
                            reason_content = analysis[reason_start + len(keyword):next_title_pos].strip()
                            # 清理开头的冒号、空格等
                            reason_content = reason_content.lstrip('：: \n')
                            md += f"### 🔍 根本原因\n{reason_content}\n\n"
                            reason_found = True
                            break

                    if not reason_found:
                        # 没找到明确分段，显示前30%内容作为问题分析
                        content_length = len(analysis)
                        md += f"### 🔍 问题分析\n{analysis[:int(content_length*0.3)]}\n...\n\n"

                    # 提取修复方案（支持多种关键词）
                    fix_keywords = ['修复方案', '解决方案', '解决方法', '修复建议', '解决建议']
                    fix_found = False
                    for keyword in fix_keywords:
                        if keyword in analysis:
                            fix_start = analysis.find(keyword)
                            # 查找下一个标题或者结尾作为结束
                            next_title_pos = len(analysis)
                            for next_keyword in ['###', '##', '\n##', '\n###', '预防建议', '影响分析', '总结']:
                                pos = analysis.find(next_keyword, fix_start + len(keyword))
                                if pos != -1 and pos < next_title_pos:
                                    next_title_pos = pos
                            fix_content = analysis[fix_start + len(keyword):next_title_pos].strip()
                            # 清理开头的冒号、空格等
                            fix_content = fix_content.lstrip('：: \n')
                            md += f"### 🔧 修复方案\n{fix_content}\n\n"
                            fix_found = True
                            break

                    if not fix_found:
                        # 没找到明确分段，显示后60%内容作为解决方案
                        content_length = len(analysis)
                        md += f"### 🔧 解决方案\n{analysis[int(content_length*0.4):]}\n\n"

                # 添加树状调用链
                md += "### 📜 完整调用链\n"
                md += "```\n"
                md += self._generate_call_chain_tree(case['keyword_chain'])
                md += "```\n\n"

        md += "---\n"
        md += "💡 完整分析日志已保存到系统，如需查看详细推理过程可查看JSON报告。\n"

        return md

def main():
    parser = argparse.ArgumentParser(description='Robot Framework AI错误分析器')
    parser.add_argument('--input', '-i', required=True, help='Robot Framework output.xml文件路径')
    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument('--prompts', '-p', help='提示词配置文件路径')
    parser.add_argument('--debug', '-d', action='store_true', help='开启调试模式，打印Prompt、AI响应、匹配日志')

    args = parser.parse_args()

    try:
        analyzer = AIAnalyzer(config_path=args.config, prompts_path=args.prompts)
        # 命令行debug参数优先级高于配置文件
        if args.debug:
            analyzer.debug_mode = True
            analyzer.logger.setLevel('DEBUG')
            analyzer.ai_client.debug_mode = True
            analyzer.logger.info("调试模式已开启，将输出详细日志")
        result = analyzer.analyze_output_xml(args.input)

        if result['summary']['failed_tests'] > 0:
            print(f"\n分析完成，共发现 {result['summary']['failed_tests']} 个失败用例")
            print(f"报告已保存到: {analyzer.reports_dir}")
        else:
            print("\n分析完成，没有发现失败的测试用例")

        return 0

    except Exception as e:
        print(f"分析失败: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
