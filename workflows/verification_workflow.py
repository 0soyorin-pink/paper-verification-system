from agents.parser_agent import ParserAgent
from agents.paper_agent import PaperAgent
from agents.patent_agent import PatentAgent

class VerificationWorkflow:
    """
    验证工作流：增强版 - 支持结构化文献数据传递
    """
    def __init__(self):
        self.parser_agent = ParserAgent()
        self.paper_agent = PaperAgent()
        self.patent_agent = PatentAgent()

    async def run(self, user_input: str) -> dict:
        """
        执行验证工作流 - 支持文献引用格式解析
        """
        print("\n==================================================")
        print(f"--- 启动验证工作流 ---")
        print("==================================================")

        # 1. 解析输入（增强版：支持文献引用格式）
        parsed_data = self.parser_agent.parse(user_input)
        
        task_type = parsed_data.get("type")
        title = parsed_data.get("title", "")
        authors = parsed_data.get("authors", "")
        year = parsed_data.get("year", "")
        journal = parsed_data.get("journal", "")
        details = parsed_data.get("details", "")
        
        print(f"📋 解析结果:")
        print(f"   类型: {task_type}")
        print(f"   标题: {title}")
        print(f"   作者: {authors}")
        print(f"   年份: {year}")
        print(f"   期刊: {journal}")
        
        if task_type == "unknown":
            return {
                "status": "failure",
                "message": "无法识别输入内容是论文还是专利，请提供更明确的信息。",
                "details": parsed_data
            }

        # 2. 路由任务并执行验证
        verification_result = None
        if task_type == "paper":
            print("\n--- 路由至 PaperAgent ---")
            # 传递结构化数据给PaperAgent
            verification_result = await self.paper_agent.verify(
                title=title,
                authors=authors,
                year=year,
                journal=journal,
                original_input=user_input
            )
        elif task_type == "patent":
            print("\n--- 路由至 PatentAgent ---")
            # 专利验证保持原有逻辑
            verification_result = await self.patent_agent.verify(title, details)
        
        # 3. 汇总结果
        if verification_result:
            is_real = verification_result.get("is_real", False)
            source = verification_result.get("source", "N/A")
            reason = verification_result.get("reason", "N/A")
            
            # 确保 is_real 是布尔值
            if isinstance(is_real, str):
                is_real = is_real.lower() == 'true'
            
            # 提取详细信息
            found_title = verification_result.get("title", "N/A")
            link = verification_result.get("link", "N/A")
            
            if task_type == "paper":
                author_or_inventor = verification_result.get("authors", "N/A")
                date = verification_result.get("published_date", "N/A")
                confidence = verification_result.get("confidence", 0)
            elif task_type == "patent":
                author_or_inventor = verification_result.get("inventor", "N/A")
                date = verification_result.get("published_date", "N/A")
                confidence = verification_result.get("confidence", 0)
            else:
                author_or_inventor = "N/A"
                date = "N/A"
                confidence = 0

            if is_real:
                status_msg = f"✅ 验证成功：该{task_type}是真实的，权威出处已找到。"
                output_msg = (
                    f"--- 权威出处信息 ---\n"
                    f"标题: {found_title}\n"
                    f"作者/发明人: {author_or_inventor}\n"
                    f"发表/公开时间: {date}\n"
                    f"来源链接: {link}\n"
                    f"权威出处名称: {source}\n"
                    f"置信度: {confidence:.2f}\n"
                    f"判断理由: {reason}"
                )
            else:
                status_msg = f"❌ 验证失败：该{task_type}无法被权威验证。"
                output_msg = f"原因：{reason}。请注意，我不会编造信息，如果无法找到权威出处，则判定为假。"

            return {
                "status": "success",
                "message": status_msg,
                "output": output_msg,
                "parsed_data": parsed_data,  # 包含解析的元数据
                "raw_data": verification_result
            }
        else:
            return {
                "status": "error",
                "message": f"执行 {task_type} 验证时发生错误。",
                "parsed_data": parsed_data,
                "details": verification_result
            }