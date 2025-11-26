#!/usr/bin/env python3
"""
论文验证测试脚本
使用准备好的论文标题数据进行测试
"""

import os
import sys
import asyncio
import csv
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows.verification_workflow import VerificationWorkflow

class PaperTester:
    """论文验证测试器"""
    
    def __init__(self):
        self.workflow = VerificationWorkflow()
        self.results = []
    
    def load_test_papers(self, file_path="test_data/papers_list.txt"):
        """
        从文件加载测试论文标题
        """
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        
        if not os.path.exists(full_path):
            print(f"❌ 论文测试数据文件不存在: {full_path}")
            print("请确保 tests/test_data/papers_list.txt 文件存在")
            sys.exit(1)
        
        with open(full_path, 'r', encoding='utf-8') as f:
            papers = [line.strip() for line in f if line.strip()]
        
        print(f"📁 从文件加载了 {len(papers)} 个论文标题")
        return papers
    
    async def test_single_paper(self, paper_title):
        """
        测试单个论文 - 修正版本
        """
        print(f"\n🔍 测试论文: {paper_title}")
        
        start_time = datetime.now()
        
        try:
            result = await self.workflow.run(paper_title)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 获取验证结果数据
            raw_data = result.get('raw_data', {})
            is_real = raw_data.get('is_real', False)
            
            test_result = {
                'paper_title': paper_title,
                'status': result.get('status', 'unknown'),
                'is_real': is_real,
                'source': raw_data.get('source', ''),
                'reason': raw_data.get('reason', ''),
                'title': raw_data.get('title', ''),
                'authors': raw_data.get('authors', ''),
                'link': raw_data.get('link', ''),
                'duration_seconds': round(duration, 2),
                # 修正：只有当工作流成功完成且验证结果为真实时才算测试成功
                'success': result.get('status') == 'success' and is_real
            }
            
            # 打印简要结果 - 根据实际验证结果显示
            workflow_success = result.get('status') == 'success'
            status_icon = "✅" if workflow_success else "❌"
            
            if workflow_success:
                reality_icon = "🟢" if is_real else "🔴"
                reality_text = "真实" if is_real else "不真实"
                print(f"{status_icon} {reality_icon} 验证完成: {reality_text} | 耗时: {test_result['duration_seconds']}s")
                
                # 显示验证原因（如果论文不真实）
                if not is_real:
                    reason = raw_data.get('reason', '未知原因')
                    print(f"   原因: {reason[:80]}...")
            else:
                print(f"{status_icon} 工作流失败 | 耗时: {test_result['duration_seconds']}s")
            
            if test_result['title'] and test_result['title'] != 'N/A':
                print(f"   标题: {test_result['title'][:60]}...")
            
            self.results.append(test_result)
            return test_result
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            error_result = {
                'paper_title': paper_title,
                'status': 'error',
                'is_real': False,
                'source': 'error', 
                'reason': str(e),
                'duration_seconds': 0,
                'success': False
            }
            self.results.append(error_result)
            return error_result
    
    async def run_batch_test(self):
        """
        运行批量论文测试
        """
        paper_titles = self.load_test_papers()
        
        print("🚀 开始论文验证批量测试")
        print("=" * 60)
        print(f"📊 测试论文数量: {len(paper_titles)}")
        print("=" * 60)
        
        for i, paper in enumerate(paper_titles, 1):
            print(f"\n📈 进度: {i}/{len(paper_titles)}")
            await self.test_single_paper(paper)
            # 添加延迟避免请求过于频繁
            await asyncio.sleep(1)
    
    def generate_report(self):
        """
        生成测试报告 - 修正版本
        """
        if not self.results:
            print("❌ 没有测试结果可生成报告")
            return
        
        total = len(self.results)
        # 修正：只计算完全成功的测试（工作流成功 + 论文真实）
        success = len([r for r in self.results if r.get('success', False)])
        real_papers = len([r for r in self.results if r.get('is_real', False)])
        workflow_success = len([r for r in self.results if r.get('status') == 'success'])
        
        print("\n" + "📊" * 40)
        print("论文验证测试报告")
        print("📊" * 40)
        print(f"总测试数: {total}")
        print(f"工作流成功: {workflow_success}")
        print(f"完全成功(真实论文): {success}")
        print(f"真实论文数: {real_papers}")
        
        if total > 0:
            print(f"工作流成功率: {(workflow_success/total)*100:.1f}%")
            print(f"完全成功率: {(success/total)*100:.1f}%")
            print(f"真实论文比例: {(real_papers/total)*100:.1f}%")
        
        # 按语言分类统计
        chinese_papers = [r for r in self.results if any('\u4e00' <= char <= '\u9fff' for char in r['paper_title'])]
        english_papers = [r for r in self.results if r not in chinese_papers]
        
        # 计算各语言的真实率
        chinese_real = len([r for r in chinese_papers if r.get('is_real', False)])
        english_real = len([r for r in english_papers if r.get('is_real', False)])
        
        print(f"\n📋 论文语言分布:")
        print(f"  中文论文: {len(chinese_papers)} (真实: {chinese_real})")
        print(f"  英文论文: {len(english_papers)} (真实: {english_real})")
        
        if len(chinese_papers) > 0:
            print(f"  中文论文真实率: {(chinese_real/len(chinese_papers))*100:.1f}%")
        if len(english_papers) > 0:
            print(f"  英文论文真实率: {(english_real/len(english_papers))*100:.1f}%")
    
    def save_results(self, filename=None):
        """
        保存测试结果 - 修正版本
        """
        if not self.results:
            print("❌ 没有测试结果可保存")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"paper_test_results_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['paper_title', 'status', 'is_real', 'source', 
                         'reason', 'title', 'authors', 'link', 'duration_seconds', 'success']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.results)
        
        print(f"💾 结果已保存: {filename}")
        return filename

async def main():
    """主测试函数"""
    tester = PaperTester()
    
    try:
        # 运行测试
        await tester.run_batch_test()
        
        # 生成报告
        tester.generate_report()
        
        # 保存结果
        tester.save_results()
        
        print("\n🎉 论文测试完成!")
        
    except Exception as e:
        print(f"💥 测试过程发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())