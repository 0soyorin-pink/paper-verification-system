#!/usr/bin/env python3
"""
专利验证测试脚本
使用准备好的专利号数据进行测试
"""

import os
import sys
import asyncio
import csv
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows.verification_workflow import VerificationWorkflow

class PatentTester:
    """专利验证测试器"""
    
    def __init__(self):
        self.workflow = VerificationWorkflow()
        self.results = []
    
    def load_test_patents(self, file_path="test_data/patents_list.txt"):
        """
        从文件加载测试专利号
        """
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        
        if not os.path.exists(full_path):
            print(f"❌ 专利测试数据文件不存在: {full_path}")
            print("请确保 tests/test_data/patents_list.txt 文件存在")
            sys.exit(1)
        
        with open(full_path, 'r', encoding='utf-8') as f:
            patents = [line.strip() for line in f if line.strip()]
        
        print(f"📁 从文件加载了 {len(patents)} 个专利号")
        return patents
    
    async def test_single_patent(self, patent_number):
        """
        测试单个专利 - 修正版本
        """
        print(f"\n🔍 测试专利: {patent_number}")
        
        start_time = datetime.now()
        
        try:
            result = await self.workflow.run(patent_number)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 获取验证结果数据
            raw_data = result.get('raw_data', {})
            is_real = raw_data.get('is_real', False)
            
            test_result = {
                'patent_number': patent_number,
                'status': result.get('status', 'unknown'),
                'is_real': is_real,
                'source': raw_data.get('source', ''),
                'reason': raw_data.get('reason', ''),
                'title': raw_data.get('title', ''),
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
                
                # 显示验证原因（如果专利不真实）
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
                'patent_number': patent_number,
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
        运行批量专利测试
        """
        patent_numbers = self.load_test_patents()
        
        print("🚀 开始专利验证批量测试")
        print("=" * 60)
        print(f"📊 测试专利数量: {len(patent_numbers)}")
        print("=" * 60)
        
        for i, patent in enumerate(patent_numbers, 1):
            print(f"\n📈 进度: {i}/{len(patent_numbers)}")
            await self.test_single_patent(patent)
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
        # 修正：只计算完全成功的测试（工作流成功 + 专利真实）
        success = len([r for r in self.results if r.get('success', False)])
        real_patents = len([r for r in self.results if r.get('is_real', False)])
        workflow_success = len([r for r in self.results if r.get('status') == 'success'])
        
        print("\n" + "📊" * 40)
        print("专利验证测试报告")
        print("📊" * 40)
        print(f"总测试数: {total}")
        print(f"工作流成功: {workflow_success}")
        print(f"完全成功(真实专利): {success}")
        print(f"真实专利数: {real_patents}")
        
        if total > 0:
            print(f"工作流成功率: {(workflow_success/total)*100:.1f}%")
            print(f"完全成功率: {(success/total)*100:.1f}%")
            print(f"真实专利比例: {(real_patents/total)*100:.1f}%")
        
        # 按国家/地区分类统计
        cn_patents = [r for r in self.results if r['patent_number'].startswith(('CN', 'ZL'))]
        us_patents = [r for r in self.results if r['patent_number'].startswith('US')]
        ep_patents = [r for r in self.results if r['patent_number'].startswith('EP')]
        jp_patents = [r for r in self.results if r['patent_number'].startswith('JP')]
        wo_patents = [r for r in self.results if r['patent_number'].startswith('WO')]
        other_patents = [r for r in self.results if r not in cn_patents + us_patents + ep_patents + jp_patents + wo_patents]
        
        # 计算各类专利的真实率
        cn_real = len([r for r in cn_patents if r.get('is_real', False)])
        us_real = len([r for r in us_patents if r.get('is_real', False)])
        ep_real = len([r for r in ep_patents if r.get('is_real', False)])
        jp_real = len([r for r in jp_patents if r.get('is_real', False)])
        wo_real = len([r for r in wo_patents if r.get('is_real', False)])
        other_real = len([r for r in other_patents if r.get('is_real', False)])
        
        print(f"\n📋 专利类型分布:")
        print(f"  中国专利: {len(cn_patents)} (真实: {cn_real})")
        print(f"  美国专利: {len(us_patents)} (真实: {us_real})")
        print(f"  欧洲专利: {len(ep_patents)} (真实: {ep_real})")
        print(f"  日本专利: {len(jp_patents)} (真实: {jp_real})")
        print(f"  WIPO专利: {len(wo_patents)} (真实: {wo_real})")
        print(f"  其他专利: {len(other_patents)} (真实: {other_real})")
        
        # 显示各类专利的真实率
        if len(cn_patents) > 0:
            print(f"  中国专利真实率: {(cn_real/len(cn_patents))*100:.1f}%")
        if len(us_patents) > 0:
            print(f"  美国专利真实率: {(us_real/len(us_patents))*100:.1f}%")
        if len(ep_patents) > 0:
            print(f"  欧洲专利真实率: {(ep_real/len(ep_patents))*100:.1f}%")
        if len(jp_patents) > 0:
            print(f"  日本专利真实率: {(jp_real/len(jp_patents))*100:.1f}%")
        if len(wo_patents) > 0:
            print(f"  WIPO专利真实率: {(wo_real/len(wo_patents))*100:.1f}%")
    
    def save_results(self, filename=None):
        """
        保存测试结果 - 修正版本
        """
        if not self.results:
            print("❌ 没有测试结果可保存")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"patent_test_results_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['patent_number', 'status', 'is_real', 'source', 
                         'reason', 'title', 'link', 'duration_seconds', 'success']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.results)
        
        print(f"💾 结果已保存: {filename}")
        return filename

async def main():
    """主测试函数"""
    tester = PatentTester()
    
    try:
        # 运行测试
        await tester.run_batch_test()
        
        # 生成报告
        tester.generate_report()
        
        # 保存结果
        tester.save_results()
        
        print("\n🎉 专利测试完成!")
        
    except Exception as e:
        print(f"💥 测试过程发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())