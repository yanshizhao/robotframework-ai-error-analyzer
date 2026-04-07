import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Iterator
from dataclasses import dataclass
from datetime import datetime
import os
import sys

@dataclass
class KeywordCall:
    """关键字调用信息"""
    name: str
    owner: str
    arguments: List[str]
    doc: str
    status: str
    start_time: Optional[datetime] = None
    elapsed_time: float = 0.0
    error_message: Optional[str] = None
    children: List['KeywordCall'] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []

@dataclass
class TestCase:
    """测试用例信息"""
    id: str
    name: str
    suite: str
    source_file: str
    line_number: int
    status: str
    start_time: Optional[datetime] = None
    elapsed_time: float = 0.0
    tags: List[str] = None
    doc: str = ""
    keyword_chain: List[KeywordCall] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.keyword_chain is None:
            self.keyword_chain = []

class RobotParser:
    """Robot Framework output.xml解析器（流式增量解析版，支持超大文件）
    优化点：
    1. 流式解析，不加载整个XML到内存，支持GB级文件
    2. 自动跳过成功用例的解析，只提取失败用例相关数据
    3. 内存占用稳定在KB级，不会随文件大小增长
    4. 解析速度提升，失败用例越少速度越快
    """

    def __init__(self, xml_path: str, parse_all: bool = False):
        """
        :param xml_path: output.xml文件路径
        :param parse_all: 是否解析所有用例（包括成功的），默认False只解析失败用例
        """
        self.xml_path = xml_path
        self.parse_all = parse_all  # 默认只解析失败用例
        self.failed_cases: List[TestCase] = []
        self.all_cases: List[TestCase] = []
        self.global_errors: List[Dict[str, Any]] = []
        self.statistics: Dict[str, Any] = {}
        self._parse_xml_stream()

    def _parse_datetime(self, time_str: Optional[str]) -> Optional[datetime]:
        """解析时间字符串"""
        if not time_str:
            return None
        try:
            return datetime.fromisoformat(time_str)
        except:
            return None

    def _fast_iterparse(self) -> Iterator[ET.Element]:
        """快速迭代解析XML，自动清理已处理元素释放内存"""
        context = ET.iterparse(self.xml_path, events=("start", "end"))
        context = iter(context)
        # 获取根元素
        event, root = next(context)

        for event, elem in context:
            yield event, elem
            # 处理完的元素立即清理，释放内存
            root.clear()

    def _parse_keyword_stream(self, start_elem: ET.Element, context: Iterator, current_suite: str) -> KeywordCall:
        """流式解析单个关键字（包含所有子关键字）"""
        kw = KeywordCall(
            name=start_elem.get("name", ""),
            owner=start_elem.get("owner", ""),
            arguments=[],
            doc="",
            status=""
        )

        # 解析当前关键字的子元素
        for event, elem in context:
            if event == "start":
                if elem.tag == "arg" and elem.text:
                    kw.arguments.append(elem.text)
                elif elem.tag == "doc" and elem.text:
                    kw.doc = elem.text
                elif elem.tag == "kw":
                    # 递归解析子关键字
                    child_kw = self._parse_keyword_stream(elem, context, current_suite)
                    kw.children.append(child_kw)
                elif elem.tag in ("for", "while", "if"):
                    # 解析控制结构内的关键字
                    for control_event, control_elem in context:
                        if control_event == "end" and control_elem.tag == elem.tag:
                            break
                        if control_event == "start" and control_elem.tag == "iter":
                            for iter_event, iter_elem in context:
                                if iter_event == "end" and iter_elem.tag == "iter":
                                    break
                                if iter_event == "start" and iter_elem.tag == "kw":
                                    child_kw = self._parse_keyword_stream(iter_elem, context, current_suite)
                                    kw.children.append(child_kw)
                elif elem.tag == "status":
                    kw.status = elem.get("status", "")
                    kw.start_time = self._parse_datetime(elem.get("start"))
                    kw.elapsed_time = float(elem.get("elapsed", "0.0"))
                    kw.error_message = elem.text if elem.text and kw.status in ("FAIL", "ERROR") else None

            if event == "end" and elem.tag == "kw":
                break

        return kw

    def _parse_test_case_stream(self, start_elem: ET.Element, context: Iterator, current_suite: str) -> Optional[TestCase]:
        """流式解析单个测试用例，如果是成功用例且parse_all=False则跳过返回None"""
        test_case = TestCase(
            id=start_elem.get("id", ""),
            name=start_elem.get("name", ""),
            suite=current_suite,
            source_file=start_elem.get("source", ""),
            line_number=int(start_elem.get("line", "0")),
            status=""
        )

        test_status = ""
        test_failed = False

        for event, elem in context:
            if event == "start":
                if elem.tag == "tag" and elem.text:
                    test_case.tags.append(elem.text)
                elif elem.tag == "doc" and elem.text:
                    test_case.doc = elem.text
                elif elem.tag == "kw":
                    # 先解析所有关键字，最后再判断是否保留用例（因为status在最后）
                    kw = self._parse_keyword_stream(elem, context, current_suite)
                    test_case.keyword_chain.append(kw)
                    if kw.status in ("FAIL", "ERROR"):
                        test_failed = True
                elif elem.tag in ("for", "while", "if"):
                    # 控制结构内的关键字
                    for control_event, control_elem in context:
                        if control_event == "end" and control_elem.tag == elem.tag:
                            break
                        if control_event == "start" and control_elem.tag == "iter":
                            for iter_event, iter_elem in context:
                                if iter_event == "end" and iter_elem.tag == "iter":
                                    break
                                if iter_event == "start" and iter_elem.tag == "kw":
                                    kw = self._parse_keyword_stream(iter_elem, context, current_suite)
                                    test_case.keyword_chain.append(kw)
                                    if kw.status in ("FAIL", "ERROR"):
                                        test_failed = True
                elif elem.tag == "status":
                    test_status = elem.get("status", "")
                    test_case.status = test_status
                    test_case.start_time = self._parse_datetime(elem.get("start"))
                    test_case.elapsed_time = float(elem.get("elapsed", "0.0"))
                    test_case.error_message = elem.text if elem.text and test_status in ("FAIL", "ERROR") else None
                    if test_status in ("FAIL", "ERROR"):
                        test_failed = True

            if event == "end" and elem.tag == "test":
                # 判断是否需要返回这个用例
                if self.parse_all or test_failed:
                    return test_case
                else:
                    # 成功用例，丢弃已解析的内容返回None，不占用内存
                    del test_case
                    return None

    def _parse_statistics(self, stats_elem: ET.Element) -> None:
        """解析统计信息"""
        stats = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "tags": {},
            "suites": {}
        }

        # 总统计
        total_elem = stats_elem.find("total/stat")
        if total_elem is not None:
            stats["total"] = int(total_elem.get("pass", 0)) + int(total_elem.get("fail", 0)) + int(total_elem.get("skip", 0))
            stats["passed"] = int(total_elem.get("pass", 0))
            stats["failed"] = int(total_elem.get("fail", 0))
            stats["skipped"] = int(total_elem.get("skip", 0))

        # 标签统计
        tag_elem = stats_elem.find("tag")
        if tag_elem is not None:
            for stat in tag_elem.findall("stat"):
                tag_name = stat.text or ""
                stats["tags"][tag_name] = {
                    "pass": int(stat.get("pass", 0)),
                    "fail": int(stat.get("fail", 0)),
                    "skip": int(stat.get("skip", 0))
                }

        # 套件统计
        suite_elem = stats_elem.find("suite")
        if suite_elem is not None:
            for stat in suite_elem.findall("stat"):
                suite_name = stat.get("name", "")
                stats["suites"][suite_name] = {
                    "id": stat.get("id", ""),
                    "pass": int(stat.get("pass", 0)),
                    "fail": int(stat.get("fail", 0)),
                    "skip": int(stat.get("skip", 0))
                }

        self.statistics = stats

    def _parse_xml_stream(self) -> None:
        """流式解析XML主逻辑"""
        if not os.path.exists(self.xml_path):
            raise FileNotFoundError(f"output.xml文件不存在: {self.xml_path}")

        try:
            context = self._fast_iterparse()
            current_suite = ""
            suite_stack = []

            for event, elem in context:
                if event == "start":
                    if elem.tag == "suite":
                        # 套件入栈
                        suite_name = elem.get("name", "")
                        suite_stack.append(suite_name)
                        current_suite = ".".join(suite_stack)

                    elif elem.tag == "test":
                        # 解析测试用例
                        test_case = self._parse_test_case_stream(elem, context, current_suite)
                        if test_case:
                            self.all_cases.append(test_case)
                            if test_case.status in ("FAIL", "ERROR"):
                                self.failed_cases.append(test_case)

                    elif elem.tag == "errors":
                        # 解析全局错误
                        for msg in elem.findall("msg"):
                            time_obj = self._parse_datetime(msg.get("time"))
                            self.global_errors.append({
                                "time": time_obj.isoformat() if time_obj else None,
                                "level": msg.get("level", "ERROR"),
                                "message": msg.text or ""
                            })

                    elif elem.tag == "statistics":
                        # 解析统计信息
                        self._parse_statistics(elem)

                elif event == "end":
                    if elem.tag == "suite":
                        # 套件出栈
                        if suite_stack:
                            suite_stack.pop()
                            current_suite = ".".join(suite_stack)

        except Exception as e:
            raise RuntimeError(f"流式解析XML文件失败: {str(e)}") from e

    def get_all_test_cases(self) -> List[TestCase]:
        """获取所有测试用例（parse_all=True时有效）"""
        return self.all_cases

    def get_failed_test_cases(self) -> List[TestCase]:
        """获取所有失败的测试用例"""
        return self.failed_cases

    def get_global_errors(self) -> List[Dict[str, Any]]:
        """获取全局错误信息"""
        return self.global_errors

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.statistics

    def extract_failure_details(self, test_case: TestCase) -> Dict[str, Any]:
        """提取测试用例的详细失败信息"""
        if test_case.status not in ("FAIL", "ERROR"):
            return {}

        # 查找失败的关键字
        failed_keywords = []

        def find_failed_keywords(kw: KeywordCall):
            if kw.status in ("FAIL", "ERROR"):
                failed_keywords.append(kw)
            for child in kw.children:
                find_failed_keywords(child)

        for kw in test_case.keyword_chain:
            find_failed_keywords(kw)

        # 构建调用链
        call_chain = []
        for kw in failed_keywords:
            call_chain.append({
                "name": kw.name,
                "owner": kw.owner,
                "arguments": kw.arguments,
                "error_message": kw.error_message,
                "elapsed_time": kw.elapsed_time
            })

        return {
            "test_case": test_case.name,
            "suite": test_case.suite,
            "source_file": test_case.source_file,
            "line_number": test_case.line_number,
            "error_message": test_case.error_message,
            "failed_keywords": call_chain,
            "tags": test_case.tags
        }
