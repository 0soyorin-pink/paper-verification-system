import json
import re
from difflib import SequenceMatcher
from tools.deepseek_client import DeepSeekClient
from tools.web_query import WebQuery

class PaperAgent:
    """
    论文验证智能体：增强版 - 支持结构化元数据输入
    """
    def __init__(self):
        self.llm_client = DeepSeekClient()
        self.web_query = WebQuery()
        self.system_prompt = (
            "你是一个专业的学术信息验证智能体。你的任务是分析提供的网络搜索结果，判断用户查询的论文是否真实存在于权威学术数据库。"
            "搜索结果已经过预处理，最佳候选结果已根据标题相似度、作者匹配度等指标排序。"
            "你需要综合考虑以下元数据：\n"
            "1. 标题相似度（最重要）\n"
            "2. 作者匹配度\n"
            "3. 发表年份一致性\n"
            "4. 期刊/会议名称匹配\n"
            "如果匹配度足够高（标题核心内容一致，作者信息吻合，年份相近），判定为真实。"
            "你必须以 JSON 格式返回结果，格式如下："
            "{\"is_real\": [true|false], \"confidence\": [0.0-1.0], \"source\": \"[权威发表地址或出处]\", \"reason\": \"[判断的详细理由]\", \"title\": \"[论文标题]\", \"authors\": \"[作者列表]\", \"published_date\": \"[发表时间]\", \"link\": \"[来源链接]\"}"
        )

    async def verify(self, title: str, authors: str = "", year: str = "", journal: str = "", original_input: str = "") -> dict:
        """
        验证论文的真实性 - 支持结构化元数据输入
        """
        print(f"--- PaperAgent: 正在验证论文 ---")
        print(f"   标题: {title}")
        print(f"   作者: {authors}")
        print(f"   年份: {year}")
        print(f"   期刊: {journal}")
        
        # 预处理作者信息
        extracted_authors = self._parse_authors(authors)
        
        # 调用增强版 web_query，传递完整元数据
        web_results = await self.web_query.query_paper_enhanced(
            title=title, 
            authors=", ".join(extracted_authors) if extracted_authors else "",
            year=year,
            journal=journal
        )
        
        # 智能结果处理
        results_list = web_results.get("results", [])
        best_candidate = None
        
        if isinstance(results_list, list) and results_list:
            # 使用完整元数据进行重排序
            reranked_results = self._rerank_with_metadata(results_list, title, extracted_authors, year, journal)
            web_results["results"] = reranked_results
            best_candidate = reranked_results[0] if reranked_results else None
            
            # 高置信度直接返回（减少LLM调用）
            if best_candidate and self._is_high_confidence_match(best_candidate, title, extracted_authors, year):
                print("🎯 高置信度匹配，直接返回结果")
                return self._create_high_confidence_result(best_candidate, title)
        
        # 如果没有高置信度结果，继续使用LLM判断
        print("🤖 使用LLM进行综合判断...")
        
        # 格式化搜索结果给 LLM，包含完整元数据信息
        search_results_str = json.dumps(web_results, indent=2, ensure_ascii=False)
        
        user_prompt = (
            f"请根据以下网络搜索结果验证论文的真实性：\n\n"
            f"查询论文信息:\n"
            f"- 标题: {title}\n"
            f"- 作者: {authors}\n"
            f"- 年份: {year}\n"
            f"- 期刊: {journal}\n"
            f"- 原始输入: {original_input}\n\n"
            f"搜索结果 (已按综合置信度排序):\n{search_results_str}\n\n"
            f"请综合考虑标题相似度、作者匹配、年份一致性和期刊信息进行判断。"
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
                
                # 补充信息：如果LLM未能提取某些字段，从最佳候选结果中补充
                if best_candidate:
                    result_data["title"] = result_data.get("title") or best_candidate.get("title", "")
                    result_data["link"] = result_data.get("link") or best_candidate.get("link", "") or best_candidate.get("url", "")
                    result_data["authors"] = result_data.get("authors") or best_candidate.get("authors", "")
                    result_data["published_date"] = result_data.get("published_date") or str(best_candidate.get("year", ""))
                    # 添加置信度
                    if "confidence" not in result_data:
                        result_data["confidence"] = best_candidate.get("confidence") or best_candidate.get("match_score", 0)
                
                print(f"--- PaperAgent: 验证结果: {result_data} ---")
                return result_data
                
            except json.JSONDecodeError as e:
                print(f"PaperAgent: JSON 解析失败: {e}, 原始响应: {json_result}")
                # 如果 JSON 解析失败，创建默认结果
                fallback_result = {
                    "is_real": False, 
                    "confidence": 0.0,
                    "source": "解析错误",
                    "reason": f"LLM 响应格式错误: {str(e)}"
                }
                if best_candidate:
                    fallback_result.update({
                        "title": best_candidate.get("title", ""),
                        "authors": best_candidate.get("authors", ""),
                        "published_date": str(best_candidate.get("year", "")),
                        "link": best_candidate.get("link", "") or best_candidate.get("url", "")
                    })
                return fallback_result
            except Exception as e:
                print(f"PaperAgent: 处理 LLM 输出失败: {e}")
                return {"is_real": False, "source": "验证过程出错", "reason": f"处理失败: {str(e)}", "confidence": 0.0}
        
        return {"is_real": False, "source": "验证失败", "reason": "LLM 调用失败", "confidence": 0.0}

    def _parse_authors(self, authors_str: str) -> list:
        """
        解析作者字符串为列表
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

    def _rerank_with_metadata(self, results: list, original_title: str, authors: list, year: str, journal: str) -> list:
        """
        使用完整元数据重新排序结果
        """
        if not results:
            return []
        
        scored_results = []
        for result in results:
            confidence = self._calculate_comprehensive_confidence(result, original_title, authors, year, journal)
            scored_results.append({
                **result,
                'confidence': confidence
            })
        
        # 按置信度降序排序
        scored_results.sort(key=lambda x: x['confidence'], reverse=True)
        
        print("📊 基于完整元数据的重排序完成:")
        for i, result in enumerate(scored_results[:3]):
            print(f"  {i+1}. 置信度: {result.get('confidence', 0):.3f} - {result.get('title', '')}")
            
        return scored_results

    def _calculate_comprehensive_confidence(self, result: dict, original_title: str, authors: list, year: str, journal: str) -> float:
        """
        计算基于完整元数据的综合置信度
        """
        confidence = 0.0
        
        # 1. 标题相似度 (权重40%)
        result_title = result.get('title', '')
        title_similarity = self.calculate_similarity(original_title, result_title)
        confidence += title_similarity * 0.4
        
        # 2. 作者匹配度 (权重25%)
        result_authors = result.get('authors', '')
        if isinstance(result_authors, str):
            result_authors_list = [a.strip() for a in result_authors.split(',') if a.strip()]
        else:
            result_authors_list = result_authors
            
        if authors and result_authors_list:
            author_match = self._calculate_author_match(authors, result_authors_list)
            confidence += author_match * 0.25
        
        # 3. 年份匹配 (权重15%)
        if year and result.get('year'):
            if str(year) == str(result['year']):
                confidence += 0.15
            else:
                # 年份相近也有部分分数
                year_diff = abs(int(year) - int(result['year']))
                if year_diff <= 2:  # 允许2年内的误差
                    confidence += 0.1
        
        # 4. 期刊信息匹配 (权重10%)
        if journal and result.get('venue'):
            journal_similarity = self.calculate_similarity(journal, result['venue'])
            confidence += journal_similarity * 0.1
        
        # 5. 引用数和权威性 (权重10%)
        citation_count = result.get('citationCount', 0)
        if citation_count > 0:
            confidence += min(0.1, citation_count / 1000)
        
        return min(confidence, 1.0)

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def _calculate_author_match(self, query_authors: list, result_authors: list) -> float:
        """计算作者匹配度"""
        if not query_authors or not result_authors:
            return 0.0
            
        # 提取姓氏进行比较
        query_last_names = []
        for name in query_authors:
            if name.strip():
                parts = name.split()
                query_last_names.append(parts[-1].lower())
        
        result_last_names = []
        for name in result_authors:
            if isinstance(name, str) and name.strip():
                parts = name.split()
                result_last_names.append(parts[-1].lower())
        
        if not query_last_names or not result_last_names:
            return 0.0
            
        common_authors = set(query_last_names) & set(result_last_names)
        if not common_authors:
            return 0.0
            
        return len(common_authors) / max(len(query_last_names), len(result_last_names))

    def _is_high_confidence_match(self, candidate: dict, original_title: str, authors: list, year: str) -> bool:
        """判断是否为高置信度匹配"""
        confidence = self._calculate_comprehensive_confidence(candidate, original_title, authors, year, "")
        return confidence > 0.8

    def _create_high_confidence_result(self, candidate: dict, original_title: str) -> dict:
        """创建高置信度结果"""
        return {
            "is_real": True,
            "confidence": candidate.get('confidence', 0.9),
            "source": candidate.get('source', '学术数据库'),
            "reason": f"高置信度匹配: 综合评分{candidate.get('confidence', 0):.2f}",
            "title": candidate.get('title', ''),
            "authors": candidate.get('authors', ''),
            "published_date": str(candidate.get('year', '')),
            "link": candidate.get('link', '') or candidate.get('url', '')
        }