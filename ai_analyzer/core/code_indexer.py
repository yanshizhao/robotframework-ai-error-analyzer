import os
import ast
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import importlib.util

from ai_analyzer.utils.logger import setup_logger

@dataclass
class KeywordInfo:
    """关键字信息"""
    name: str
    owner: str
    file_path: str
    line_number: int
    docstring: str = ""
    source_code: str = ""
    parameters: List[str] = None
    return_type: Optional[str] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = []

class CodeIndexer:
    """代码库索引器，建立Robot关键字到Python代码的映射"""

    def __init__(self, config: Dict[str, Any], logger=None):
        self.config = config
        self.logger = logger or setup_logger(name="code_indexer")
        self.libs_path = os.path.abspath(config.get('codebase', {}).get('libs_path', './libs'))
        self.index_method = config.get('codebase', {}).get('indexing', {}).get('method', 'decorator')
        self.auto_scan = config.get('codebase', {}).get('indexing', {}).get('auto_scan', True)
        self.exclude_dirs = set(config.get('codebase', {}).get('indexing', {}).get('exclude_dirs', []))
        self.exclude_dirs.update({'__pycache__', '.git', 'venv', '.idea', '.vscode'})

        # 关键字索引: key = "owner.keyword_name", value = KeywordInfo
        self.keyword_index: Dict[str, KeywordInfo] = {}
        # 别名索引: key = 关键字名称, value = 列表的KeywordInfo（可能重名）
        self.name_index: Dict[str, List[KeywordInfo]] = {}

        if self.auto_scan:
            self.scan_libs()

    def scan_libs(self) -> None:
        """扫描libs目录下的所有Python文件，索引关键字"""
        self.logger.info(f"开始扫描代码库: {self.libs_path}")
        self.keyword_index.clear()
        self.name_index.clear()

        if not os.path.exists(self.libs_path):
            self.logger.warning(f"代码库目录不存在: {self.libs_path}")
            return

        for root, dirs, files in os.walk(self.libs_path):
            # 排除不需要的目录
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                if file.endswith('.py') and not file.startswith('_'):
                    file_path = os.path.join(root, file)
                    self._index_python_file(file_path)

        self.logger.info(f"扫描完成，共索引到 {len(self.keyword_index)} 个关键字")

    def _index_python_file(self, file_path: str) -> None:
        """索引单个Python文件中的关键字"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=file_path)
            file_lines = content.splitlines()

            # 获取类名和函数名
            class_names = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_names.append(node.name)
                    self._index_class(node, file_path, file_lines)
                elif isinstance(node, ast.FunctionDef) and not self._is_private_function(node.name):
                    self._index_function(node, file_path, file_lines, class_name=None)

        except Exception as e:
            self.logger.warning(f"解析文件失败 {file_path}: {str(e)}")

    def _is_private_function(self, name: str) -> bool:
        """判断是否是私有函数"""
        return name.startswith('_') and not (name.startswith('__') and name.endswith('__'))

    def _index_class(self, class_node: ast.ClassDef, file_path: str, file_lines: List[str]) -> None:
        """索引类中的关键字方法"""
        class_name = class_node.name

        for node in class_node.body:
            if isinstance(node, ast.FunctionDef) and not self._is_private_function(node.name):
                self._index_function(node, file_path, file_lines, class_name)

    def _index_function(self, func_node: ast.FunctionDef, file_path: str, file_lines: List[str],
                       class_name: Optional[str] = None) -> None:
        """索引函数/方法，判断是否是关键字"""
        is_keyword = False
        keyword_name = func_node.name

        # 根据索引方式判断是否是关键字
        if self.index_method == 'decorator':
            # 查找@keyword装饰器
            for decorator in func_node.decorator_list:
                if (isinstance(decorator, ast.Name) and decorator.id == 'keyword') or \
                   (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and
                    decorator.func.id == 'keyword'):
                    is_keyword = True
                    # 提取装饰器中指定的关键字名称
                    if isinstance(decorator, ast.Call) and decorator.args:
                        if isinstance(decorator.args[0], ast.Constant):
                            keyword_name = decorator.args[0].value
                    break

        elif self.index_method == 'naming':
            # 通过命名约定判断，方法名首字母大写、包含keyword，或是中文方法名
            first_char = func_node.name[0]
            if (first_char.isupper() or
                'keyword' in func_node.name.lower() or
                '\u4e00' <= first_char <= '\u9fff'):  # 判断是否是中文字符
                is_keyword = True

        if not is_keyword:
            return

        # 提取参数
        parameters = []
        for arg in func_node.args.args:
            if arg.arg != 'self':  # 排除self参数
                parameters.append(arg.arg)

        # 提取返回值类型注解
        return_type = None
        if func_node.returns:
            return_type = ast.unparse(func_node.returns) if hasattr(ast, 'unparse') else str(func_node.returns)

        # 提取docstring
        docstring = ast.get_docstring(func_node) or ""

        # 提取源代码
        start_line = func_node.lineno - 1  # ast是1-based
        end_line = func_node.end_lineno if hasattr(func_node, 'end_lineno') else start_line
        source_code = '\n'.join(file_lines[start_line:end_line])

        # 构建关键字信息
        owner = class_name if class_name else os.path.splitext(os.path.basename(file_path))[0]
        full_key = f"{owner}.{keyword_name}"

        keyword_info = KeywordInfo(
            name=keyword_name,
            owner=owner,
            file_path=file_path,
            line_number=func_node.lineno,
            docstring=docstring,
            source_code=source_code,
            parameters=parameters,
            return_type=return_type
        )

        # 加入索引
        self.keyword_index[full_key] = keyword_info
        if keyword_name not in self.name_index:
            self.name_index[keyword_name] = []
        self.name_index[keyword_name].append(keyword_info)

        self.logger.debug(f"索引关键字: {full_key} (文件: {file_path}:{func_node.lineno})")
    
    def find_keyword_by_name(self, keyword_name: str, owner: Optional[str] = None) -> List[KeywordInfo]:
        """根据关键字名称查找关键字信息"""
        if owner:
            full_key = f"{owner}.{keyword_name}"
            if full_key in self.keyword_index:
                return [self.keyword_index[full_key]]
            return []

        return self.name_index.get(keyword_name, [])

    def get_keyword_code(self, keyword_name: str, owner: Optional[str] = None,
                        max_lines: int = 20) -> Optional[str]:
        """获取关键字的源代码"""
        keywords = self.find_keyword_by_name(keyword_name, owner)
        if not keywords:
            return None

        # 取第一个匹配的
        kw = keywords[0]
        lines = kw.source_code.splitlines()
        if len(lines) > max_lines:
            return '\n'.join(lines[:max_lines]) + f"\n... (省略了{len(lines) - max_lines}行)"
        return kw.source_code

    def get_keyword_doc(self, keyword_name: str, owner: Optional[str] = None) -> Optional[str]:
        """获取关键字的文档字符串"""
        keywords = self.find_keyword_by_name(keyword_name, owner)
        if not keywords:
            return None
        return keywords[0].docstring

    def search_keywords(self, query: str) -> List[KeywordInfo]:
        """搜索关键字，支持模糊匹配"""
        results = []
        query = query.lower()

        for kw in self.keyword_index.values():
            if (query in kw.name.lower() or
                query in kw.owner.lower() or
                query in kw.docstring.lower() or
                query in kw.file_path.lower()):
                results.append(kw)

        return results

    def get_index_summary(self) -> Dict[str, Any]:
        """获取索引摘要信息"""
        return {
            "total_keywords": len(self.keyword_index),
            "libs_path": self.libs_path,
            "index_method": self.index_method,
            "owners": list({kw.owner for kw in self.keyword_index.values()}),
            "keywords": [{"name": kw.name, "owner": kw.owner, "file": kw.file_path}
                        for kw in self.keyword_index.values()]
        }
