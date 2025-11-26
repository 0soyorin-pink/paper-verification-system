import json
import re
from difflib import SequenceMatcher
from tools.deepseek_client import DeepSeekClient
from tools.web_query import WebQuery

class PatentAgent:
    """
    专利验证智能体：增强版 - 支持智能匹配和结果优化
    """
    def __init__(self):
        self.llm_client = DeepSeekClient()
        self.web_query = WebQuery()
        self.system_prompt = (
            "你是一个专业的专利信息验证智能体。你的任务是分析提供的网络搜索结果，"
            "判断用户查询的专利是否真实存在于权威专利数据库。"
            "搜索结果已经过预处理，最佳候选结果已根据相关性排序。"
            "你需要："
            "1. 确认最佳候选结果与查询专利的匹配程度"
            "2. 如果专利号完全匹配或标题高度相似，判定为真实"
            "3. 如果信息不完整但核心内容匹配，可判定为可能真实"
            "4. 如果完全不匹配或找不到相关信息，判定为虚假"
            "你必须以 JSON 格式返回结果，格式如下："
            "{\"is_real\": [true|false], \"confidence\": [0.0-1.0], \"source\": \"[官方专利号和出处]\", \"reason\": \"[判断的详细理由]\", \"title\": \"[专利标题]\", \"inventor\": \"[发明人列表]\", \"published_date\": \"[公开/授权日期]\", \"link\": \"[来源链接]\"}"
        )

    def normalize_patent_number(self, patent_number: str) -> str:
        """
        标准化专利号格式
        """
        if not patent_number:
            return ""
        
        # 移除空格和特殊字符，只保留字母数字
        normalized = re.sub(r'[^\w]', '', patent_number.upper())
        
        # 常见的专利号格式处理
        if normalized.startswith('CN'):
            # 中国专利号
            if len(normalized) > 2:
                return f"CN{normalized[2:]}"
        elif normalized.startswith('US'):
            # 美国专利号
            if len(normalized) > 2:
                return f"US{normalized[2:]}"
        elif normalized.startswith('EP'):
            # 欧洲专利号
            if len(normalized) > 2:
                return f"EP{normalized[2:]}"
        elif normalized.startswith('WO'):
            # PCT专利号
            if len(normalized) > 2:
                return f"WO{normalized[2:]}"
        elif re.match(r'^\d+[A-Z]*$', normalized):
            # 纯数字，可能是美国专利号
            return f"US{normalized}"
            
        return normalized

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度
        """
        if not text1 or not text2:
            return 0.0
            
        # 清理标点符号
        t1 = re.sub(r'[^\w\s]', '', text1.lower())
        t2 = re.sub(r'[^\w\s]', '', text2.lower())
        
        return SequenceMatcher(None, t1, t2).ratio()

    def extract_inventor_from_details(self, details: str) -> list:
        """
        从details中提取发明人信息
        """
        if not details:
            return []
        
        inventors = []
        try:
            # 方法1: 查找"发明人"、"申请人"等关键词
            inventor_keywords = ['发明人', '申请人', 'inventor', 'applicant']
            for keyword in inventor_keywords:
                if keyword in details:
                    inventor_part = details.split(keyword)[-1].split('。')[0].split('\n')[0].strip()
                    # 尝试用逗号、分号分隔
                    if '，' in inventor_part:  # 中文逗号
                        inventors = [a.strip() for a in inventor_part.split('，') if a.strip()]
                        break
                    elif ',' in inventor_part:  # 英文逗号
                        inventors = [a.strip() for a in inventor_part.split(',') if a.strip()]
                        break
                    elif ';' in inventor_part:  # 分号
                        inventors = [a.strip() for a in inventor_part.split(';') if a.strip()]
                        break
            
            # 方法2: 如果没找到发明人，但details看起来像名字列表
            if not inventors and details and len(details) < 100:
                if '，' in details:
                    inventors = [a.strip() for a in details.split('，') if a.strip()]
                elif ',' in details:
                    inventors = [a.strip() for a in details.split(',') if a.strip()]
                    
        except Exception as e:
            print(f"⚠️ 提取发明人信息失败: {e}")
            
        print(f"📝 提取到发明人: {inventors}")
        return inventors

    def calculate_patent_confidence(self, query_patent: str, query_title: str, result: dict) -> float:
        """
        计算专利搜索结果的置信度
        """
        confidence = 0.0
        
        # 1. 专利号匹配 (权重最高)
        result_title = result.get('title', '')
        result_link = result.get('link', '')
        
        # 检查专利号匹配
        if query_patent:
            normalized_query = self.normalize_patent_number(query_patent)
            
            # 在标题和链接中查找专利号
            combined_text = f"{result_title} {result_link}".upper()
            if normalized_query in combined_text:
                confidence += 0.6  # 专利号完全匹配
        
        # 2. 标题相似度 (权重次高)
        if query_title:
            title_similarity = self.calculate_similarity(query_title, result_title)
            confidence += title_similarity * 0.4
        else:
            # 如果没有查询标题，使用专利号查询的默认相似度
            confidence += 0.3
        
        # 3. 来源权威性加分
        source = result.get('source', '')
        authoritative_sources = ['Google Patents', 'USPTO', 'CNIPA', 'EPO', 'WIPO']
        if any(auth_source in source for auth_source in authoritative_sources):
            confidence += 0.1
        
        return min(confidence, 1.0)

    def rerank_patent_results(self, query_patent: str, query_title: str, results: list) -> list:
        """
        根据多种因素重新排序专利搜索结果
        """
        if not results:
            return []
        
        scored_results = []
        for result in results:
            confidence = self.calculate_patent_confidence(query_patent, query_title, result)
            scored_results.append({
                **result,
                'confidence': confidence
            })
        
        # 按置信度降序排序
        scored_results.sort(key=lambda x: x['confidence'], reverse=True)
        
        # 打印排序结果
        print("📊 专利搜索结果重排序完成:")
        for i, result in enumerate(scored_results[:3]):  # 只显示前3个
            print(f"  {i+1}. 置信度: {result.get('confidence', 0):.3f} - {result.get('title', '')}")
            
        return scored_results

    def _is_high_confidence_patent_match(self, candidate: dict, query_patent: str, query_title: str) -> bool:
        """
        判断是否为高置信度专利匹配
        """
        # 检查置信度
        if candidate.get('confidence', 0) > 0.8:
            return True
            
        # 检查专利号匹配
        if query_patent:
            normalized_query = self.normalize_patent_number(query_patent)
            result_title = candidate.get('title', '').upper()
            result_link = candidate.get('link', '').upper()
            
            if normalized_query in result_title or normalized_query in result_link:
                return True
        
        # 检查标题相似度
        if query_title:
            candidate_title = candidate.get('title', '')
            similarity = self.calculate_similarity(query_title, candidate_title)
            return similarity > 0.9
            
        return False

    def _create_high_confidence_patent_result(self, candidate: dict, query_patent: str) -> dict:
        """
        创建高置信度专利结果
        """
        # 从候选结果中提取专利号
        patent_number = query_patent
        if not patent_number:
            # 尝试从标题或链接中提取专利号
            title = candidate.get('title', '')
            link = candidate.get('link', '')
            # 简单的专利号提取逻辑
            patent_match = re.search(r'[A-Z]{2}\d+', title + ' ' + link)
            if patent_match:
                patent_number = patent_match.group()
        
        source_info = candidate.get('source', '专利数据库')
        if patent_number:
            source_info = f"{patent_number} - {source_info}"
        
        return {
            "is_real": True,
            "confidence": candidate.get('confidence', 0.9),
            "source": source_info,
            "reason": f"高置信度匹配: 专利信息验证通过",
            "title": candidate.get('title', ''),
            "inventor": candidate.get('inventor', '') or candidate.get('authors', ''),
            "published_date": candidate.get('date', '') or candidate.get('year', ''),
            "link": candidate.get('link', '')
        }

    async def verify(self, query: str, details: str) -> dict:
        """
        验证专利的真实性 - 增强版
        """
        print(f"--- PatentAgent: 正在验证专利: {query} ---")
        
        # 判断query是专利号还是标题
        is_patent_number = self._looks_like_patent_number(query)
        patent_number = query if is_patent_number else None
        title = details if is_patent_number else query
        
        extracted_inventors = self.extract_inventor_from_details(details)
        
        print(f"专利号: {patent_number}")
        print(f"标题: {title}")
        print(f"提取的发明人: {extracted_inventors}")
        
        # 调用 web_query
        web_results = await self.web_query.query_patent(
            patent_number=patent_number, 
            title=title, 
            inventor=details
        )
        
        # 智能结果处理
        results_list = web_results.get("results", [])
        best_candidate = None
        
        if isinstance(results_list, list) and results_list:
            # 对专利结果进行重排序
            reranked_results = self.rerank_patent_results(patent_number, title, results_list)
            web_results["results"] = reranked_results
            best_candidate = reranked_results[0] if reranked_results else None
            
            # 高置信度直接返回（减少LLM调用）
            if best_candidate and self._is_high_confidence_patent_match(best_candidate, patent_number, title):
                print("🎯 高置信度专利匹配，直接返回结果")
                return self._create_high_confidence_patent_result(best_candidate, patent_number)
        
        # 如果没有高置信度结果，继续使用LLM判断
        print("🤖 使用LLM进行专利综合判断...")
        
        # 格式化搜索结果给 LLM
        search_results_str = json.dumps(web_results, indent=2, ensure_ascii=False)
        
        user_prompt = (
            f"请根据以下网络搜索结果验证专利的真实性：\n\n"
            f"专利号: {patent_number or '未提供'}\n"
            f"标题: {title}\n"
            f"补充信息: {details}\n"
            f"提取的发明人: {extracted_inventors}\n\n"
            f"搜索结果 (已按置信度排序):\n{search_results_str}\n\n"
            f"请注意：专利号匹配的权重最高，其次是标题相似度。"
        )
        
        json_result = self.llm_client.chat_completion(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            json_mode=True
        )
        
        if json_result:
            # 补充信息：如果LLM未能提取某些字段，从最佳候选结果中补充
            if best_candidate:
                json_result["title"] = json_result.get("title") or best_candidate.get("title", "")
                json_result["link"] = json_result.get("link") or best_candidate.get("link", "")
                json_result["inventor"] = json_result.get("inventor") or best_candidate.get("inventor", "") or best_candidate.get("authors", "")
                json_result["published_date"] = json_result.get("published_date") or best_candidate.get("date", "") or str(best_candidate.get("year", ""))
                # 添加置信度
                if "confidence" not in json_result:
                    json_result["confidence"] = best_candidate.get("confidence", 0)
                
            try:
                print(f"--- PatentAgent: 验证结果: {json_result} ---")
                return json_result
            except Exception as e:
                print(f"PatentAgent: 解析 LLM 输出失败: {e}")
                return {"is_real": False, "source": "验证过程出错", "reason": "LLM 输出格式错误", "confidence": 0.0}
        
        return {"is_real": False, "source": "验证失败", "reason": "LLM 调用失败", "confidence": 0.0}

    def _looks_like_patent_number(self, text: str) -> bool:
        """
        判断文本是否看起来像专利号
        """
        if not text:
            return False
            
        # 移除空格
        clean_text = re.sub(r'\s', '', text.upper())
        
        # 检查常见的专利号格式
        patterns = [
            r'^[A-Z]{2}\d+',  # CN123456, US123456, EP123456
            r'^US\d+',        # US123456
            r'^CN\d+',        # CN123456
            r'^EP\d+',        # EP123456
            r'^WO\d+',        # WO123456
            r'^\d+[A-Z]?$',   # 123456, 123456A
        ]
        
        for pattern in patterns:
            if re.match(pattern, clean_text):
                return True
                
        return False