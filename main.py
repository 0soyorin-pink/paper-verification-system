import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from workflows.verification_workflow import VerificationWorkflow

# 确保能正确加载 .env 文件
# 由于 main.py 在 your_project/ 下，.env 也在 your_project/ 下
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

async def async_main():
    """
    异步主程序入口。
    """
    print("==================================================")
    print("  论文/专利真实性验证系统 (Multi-Agent)")
    print("==================================================")
    
    # 检查 API Key 是否设置
    if not os.getenv("OPENAI_API_KEY"):
        print("错误：未找到 OPENAI_API_KEY 环境变量。")
        print("请在 your_project/.env 文件中设置您的 API 密钥。")
        sys.exit(1)
    # 检查 百度搜索API Key 是否设置 (现在是可选的，因为有爬虫降级)
    if not os.getenv("BAIDU_API_KEY"):
        print("警告：未找到 BAIDU_API_KEY")
        print("系统将自动降级使用 Playwright 爬虫模式进行查询。")
        print("爬虫模式可能较慢且不稳定，建议配置百度搜索API。")
    workflow = VerificationWorkflow()

    while True:
        user_input = input("\n请输入您要验证的论文标题、专利号或相关描述 (输入 'exit' 退出): \n> ")
        
        if user_input.lower() == 'exit':
            print("程序退出。")
            break
        
        if not user_input.strip():
            continue

        try:
            # 调用异步的工作流
            result = await workflow.run(user_input)
            
            print("\n==================================================")
            print("                ✨ 最终验证结果 ✨")
            print("==================================================")
            print(result["message"])
            print(result["output"])
            print("--------------------------------------------------")
            # print("原始数据 (供调试):")
            # print(json.dumps(result["raw_data"], indent=4, ensure_ascii=False))
            print("==================================================")

        except Exception as e:
            print(f"\n[系统错误] 验证过程中发生未预期的错误: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # 为了让 import 正常工作，需要将 your_project 目录添加到 Python 路径
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # 运行异步主函数
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n程序被用户中断。")
