import json
import re
from tools.deepseek_client import DeepSeekClient

class ParserAgent:
    """
    解析智能体：增强版 - 支持文献引用格式解析和元数据提取
    """
    def __init__(self):
        self.llm_client = DeepSeekClient()
        self.system_prompt = (
            "你是一个专业的学术文献解析智能体。你的任务是分析用户提供的文献引用或描述，"
            "提取出完整的文献元数据，并判断该文献是 'paper'（论文）还是 'patent'（专利）。"
            "如果无法判断，则返回 'unknown'。"
            "你必须以 JSON 格式返回结果，格式如下："
            "{\"type\": \"[paper|patent|unknown]\", \"title\": \"[论文标题]\", \"authors\": \"[作者列表，用逗号分隔]\", \"year\": \"[发表年份]\", \"journal\": \"[期刊/会议名称]\", \"details\": \"[其他补充信息]\"}"
            "注意：请确保准确提取标题、作者、年份等关键信息。"
        )

    async def parse(self, user_input: str) -> dict:
        """
        解析用户输入，支持多种文献引用格式
        """
        print(f"--- ParserAgent: 正在解析输入: {user_input[:50]}... ---")
        
        # 先尝试规则匹配快速解析
        quick_result = self._quick_parse(user_input)
        if quick_result and quick_result.get("type") != "unknown":
            print("✅ 使用规则解析结果")
            return quick_result
        
        # 规则解析失败，使用LLM进行智能解析
        print("🔍 规则解析不明确，使用LLM进行智能解析...")
        return await self._llm_parse(user_input)

    def _quick_parse(self, user_input: str) -> dict:
        """
        快速规则解析：针对常见引用格式进行快速提取
        """
        # 清理输入文本
        text = user_input.strip()
        
        # 匹配专利号模式
        patent_patterns = [
            r'[A-Z]{2}\d+',  # CN123456, US123456
            r'专利号?[：:]\s*([A-Z0-9]+)',  # 专利号：CN123456
            r'patent\s*(?:no|number)?[：:]\s*([A-Z0-9]+)',  # patent no: US123456
        ]
        
        for pattern in patent_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return {
                    "type": "patent",
                    "title": text,
                    "authors": "",
                    "year": "",
                    "journal": "",
                    "details": f"检测到专利号: {match.group(1)}"
                }
        
        # 匹配常见的论文引用格式
        # APA格式: Author, A. (Year). Title. Journal.
        apa_match = re.search(r'([A-Z][^.]*)\.\s*\((\d{4})\)\.\s*([^.]*)\.', text)
        if apa_match:
            authors = apa_match.group(1).strip()
            year = apa_match.group(2)
            title = apa_match.group(3).strip()
            return {
                "type": "paper",
                "title": title,
                "authors": authors,
                "year": year,
                "journal": "",
                "details": "APA格式解析"
            }
        
        # 中文格式: 作者. 标题[J]. 期刊, 年份
        chinese_match = re.search(r'([^。]+)\.\s*([^[]+)\[J\]\.\s*([^,]+),\s*(\d{4})', text)
        if chinese_match:
            authors = chinese_match.group(1).strip()
            title = chinese_match.group(2).strip()
            journal = chinese_match.group(3).strip()
            year = chinese_match.group(4)
            return {
                "type": "paper",
                "title": title,
                "authors": authors,
                "year": year,
                "journal": journal,
                "details": "中文期刊格式解析"
            }
        
        # 简单标题-作者格式: 标题 - 作者1, 作者2 (年份)
        simple_match = re.search(r'([^-]+)-([^(]+)\((\d{4})\)', text)
        if simple_match:
            title = simple_match.group(1).strip()
            authors = simple_match.group(2).strip()
            year = simple_match.group(3)
            return {
                "type": "paper",
                "title": title,
                "authors": authors,
                "year": year,
                "journal": "",
                "details": "简单格式解析"
            }
        
        return {"type": "unknown", "title": text, "authors": "", "year": "", "journal": "", "details": "规则解析失败"}

    async def _llm_parse(self, user_input: str) -> dict:
        """
        使用LLM进行智能解析
        """
        user_prompt = (
            f"请解析以下文献引用，提取标题、作者、年份、期刊等信息：\n\n"
            f"输入文本: {user_input}\n\n"
            f"请确保：\n"
            f"1. 标题提取准确完整\n"
            f"2. 作者列表用逗号分隔\n"
            f"3. 年份为4位数字\n"
            f"4. 如果是专利，类型设为'patent'"
        )
        
        json_result = await self.llm_client.chat_completion(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            json_mode=True
        )
        
        if json_result:
            try:
                # 先解析 JSON 字符串为字典
                result_data = json.loads(json_result)
                
                # 验证必要字段
                if not result_data.get("title"):
                    result_data["title"] = user_input
                
                # 清理作者格式
                if result_data.get("authors"):
                    authors = result_data["authors"]
                    if isinstance(authors, list):
                        result_data["authors"] = ", ".join(authors)
                    elif isinstance(authors, str) and "[" in authors and "]" in authors:
                        # 处理可能的列表字符串格式
                        import ast
                        try:
                            authors_list = ast.literal_eval(authors)
                            if isinstance(authors_list, list):
                                result_data["authors"] = ", ".join(authors_list)
                        except:
                            pass
                
                print(f"--- ParserAgent: 解析结果: {result_data} ---")
                return result_data
                
            except Exception as e:
                print(f"ParserAgent: 解析 LLM 输出失败: {e}")
                return self._create_fallback_result(user_input)
        
        return self._create_fallback_result(user_input)

    def _create_fallback_result(self, user_input: str) -> dict:
        """
        创建降级解析结果
        """
        return {
            "type": "unknown",
            "title": user_input,
            "authors": "",
            "year": "",
            "journal": "",
            "details": "LLM解析失败，使用原始输入"
        }

    def extract_authors_list(self, authors_str: str) -> list:
        """
        从作者字符串中提取作者列表
        """
        if not authors_str:
            return []
        
        # 多种分隔符支持
        separators = [',', '，', ';', '；', '、']
        for sep in separators:
            if sep in authors_str:
                return [author.strip() for author in authors_str.split(sep) if author.strip()]
        
        # 空格分隔（英文名）
        if re.search(r'[a-zA-Z]', authors_str):
            return [author.strip() for author in authors_str.split() if author.strip()]
        
        return [authors_str.strip()]