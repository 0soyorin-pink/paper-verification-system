import os
import time
import requests
import re
from typing import List, Dict, Any, Optional
import threading
from urllib.parse import quote
from difflib import SequenceMatcher

class SemanticScholarClient:
    """
    Semantic Scholar API 客户端 - 增强版：支持多查询变体和智能排序
    """
    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self):
        # 从环境变量获取API Key
        self.api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        if not self.api_key:
            raise ValueError("❌ 未找到 SEMANTIC_SCHOLAR_API_KEY 环境变量")
        
        self.headers = {"x-api-key": self.api_key}
        print("✅ Semantic Scholar API 客户端已初始化（认证模式）")
        
        # 严格遵守速率限制：每秒1次请求
        self.rate_limit_lock = threading.Lock()
        self.last_request_time = 0
        self.min_interval = 1.0  # 最低1秒间隔
        
        # 扩展查询字段，获取更丰富的信息
        self.fields = "title,authors,year,venue,abstract,url,externalIds,citationCount,publicationVenue,referenceCount,fieldsOfStudy,tldr"
        
        # 请求统计
        self.request_count = 0
        self.daily_request_count = 0
        self.last_reset_time = time.time()
        
        # 缓存机制减少重复请求
        self.cache = {}
        self.cache_ttl = 3600  # 1小时缓存

    def _enforce_rate_limit(self):
        """严格执行速率限制：每秒1次请求"""
        with self.rate_limit_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                print(f"⏳ 遵守速率限制，等待 {sleep_time:.2f} 秒")
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
            
            # 每日统计重置
            if current_time - self.last_reset_time > 86400:  # 24小时
                self.daily_request_count = 0
                self.last_reset_time = current_time

    def _make_request(self, url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """执行API请求，包含速率限制和错误处理"""
        self._enforce_rate_limit()
        
        try:
            self.request_count += 1
            self.daily_request_count += 1
            
            print(f"📊 API请求 #{self.request_count} (今日第{self.daily_request_count}次)")
            
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.Timeout:
            print("❌ 请求超时")
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print("🚫 触发速率限制，请降低请求频率")
            elif e.response.status_code == 403:
                print("🔒 API密钥无效或权限不足")
            elif e.response.status_code == 404:
                print("🔍 未找到请求的资源")
            else:
                print(f"❌ HTTP错误 {e.response.status_code}: {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络请求异常: {e}")
            return None
        except Exception as e:
            print(f"❌ 未知异常: {e}")
            return None

    def search_paper(self, query: str, limit: int = 5, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        通过关键词查询论文
        
        Args:
            query: 搜索关键词
            limit: 返回结果数量
            use_cache: 是否使用缓存
            
        Returns:
            格式化后的论文列表
        """
        print(f"🔍 Semantic Scholar 搜索: {query}")
        
        # 检查缓存
        cache_key = f"search_{quote(query)}_{limit}"
        if use_cache and cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                print("✅ 使用缓存结果")
                return data
            else:
                # 缓存过期
                del self.cache[cache_key]
        
        url = f"{self.BASE_URL}/paper/search"
        params = {
            "query": query,
            "fields": self.fields,
            "limit": limit
        }
        
        data = self._make_request(url, params)
        
        if data and "data" in data:
            results = data["data"]
            print(f"✅ 找到 {len(results)} 个结果")
            
            formatted_results = self._format_results(results)
            
            # 更新缓存
            if use_cache:
                self.cache[cache_key] = (time.time(), formatted_results)
                
            return formatted_results
        else:
            print("⚠️ 未找到相关论文")
            return []

    def search_paper_enhanced(self, title: str, authors: List[str] = None, year: str = None, 
                        limit: int = 5, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        增强版论文搜索：使用优化的查询策略
        """
        print(f"🔍 Semantic Scholar 增强搜索: {title}")
        print(f"   作者: {authors}")
        print(f"   年份: {year}")
        try:
            # 生成多个查询变体以提高命中率
            query_variants = self._generate_query_variants(title, authors, year)
        
            all_results = []
            for query in query_variants:
                print(f"  尝试查询变体: {query}")
                results = self.search_paper(query, limit=3, use_cache=use_cache)

                # 确保 results 是列表
                if results is None:
                    results = []
                elif not isinstance(results, list):
                    print(f"⚠️ 查询结果不是列表类型: {type(results)}")
                    results = []
                
                all_results.extend(results)
            
                # 如果找到高置信度结果，提前返回
                if results and self._has_high_confidence_result(results, title):
                    print("✅ 找到高置信度结果，提前返回")
                    break
        
            # 去重并重新排序
            unique_results = self._deduplicate_results(all_results)
            scored_results = self._score_and_rank_results(unique_results, title, authors, year)
        
            return scored_results[:limit]
        
        except Exception as e:
            print(f"❌ Semantic Scholar 增强搜索失败: {e}")
            import traceback
            traceback.print_exc()
            return []  # 返回空列表而不是 None

    def _generate_query_variants(self, title: str, authors: List[str] = None, year: str = None) -> List[str]:
        """
        生成多个查询变体
        """
        variants = []
        
        # 变体1: 清理后的标题
        clean_title = self._clean_title(title)
        variants.append(clean_title)
        
        # 变体2: 标题 + 第一作者（如果有）
        if authors and len(authors) > 0:
            first_author = authors[0].split()[0] if ' ' in authors[0] else authors[0]
            variants.append(f"{clean_title} {first_author}")
            
            # 变体3: 仅第一作者 + 年份（如果有）
            if year:
                variants.append(f'{first_author} {year} "{clean_title}"')
        
        # 变体4: 带引号的精确标题
        variants.append(f'"{clean_title}"')
        
        # 变体5: 标题 + 年份（如果有）
        if year:
            variants.append(f"{clean_title} {year}")
        
        print(f"📝 生成 {len(variants)} 个查询变体: {variants}")
        return variants

    def _clean_title(self, title: str) -> str:
        """
        清理标题，提高搜索匹配度
        """
        if not title:
            return ""
        
        # 转换为小写
        title = title.lower()
        
        # 移除常见的标点符号
        title = re.sub(r'[^\w\s-]', ' ', title)
        
        # 移除多余的空白字符
        title = re.sub(r'\s+', ' ', title).strip()
        
        # 谨慎移除停用词（仅当标题较长时）
        words = title.split()
        if len(words) > 4:
            stop_words = {'the', 'a', 'an', 'of', 'on', 'in', 'and', 'or', 'for', 'to', 'with'}
            filtered_words = [word for word in words if word not in stop_words]
            if len(filtered_words) >= 3:  # 确保保留足够的关键词
                title = ' '.join(filtered_words)
        
        return title

    def _has_high_confidence_result(self, results: List[Dict], original_title: str) -> bool:
        """
        检查是否有高置信度结果
        """
        if not results:
            return False
            
        best_result = results[0]
        similarity = self._calculate_title_similarity(original_title, best_result.get('title', ''))
        return similarity > 0.9

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """
        计算两个标题的相似度
        """
        if not title1 or not title2:
            return 0.0
            
        # 转换为小写并移除标点
        t1 = re.sub(r'[^\w\s]', '', title1.lower())
        t2 = re.sub(r'[^\w\s]', '', title2.lower())
        
        # 使用序列匹配器计算相似度
        return SequenceMatcher(None, t1, t2).ratio()

    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """
        基于paperId去重
        """
        seen_ids = set()
        unique_results = []
        
        for result in results:
            paper_id = result.get('paperId') or result.get('title', '')
            if paper_id and paper_id not in seen_ids:
                seen_ids.add(paper_id)
                unique_results.append(result)
        
        print(f"🔄 去重后剩余 {len(unique_results)} 个唯一结果")
        return unique_results

    def _score_and_rank_results(self, results: List[Dict], original_title: str, 
                              authors: List[str] = None, year: str = None) -> List[Dict]:
        """
        为结果评分并排序
        """
        if not results:
            return []
            
        scored_results = []
        
        for result in results:
            score = self._calculate_result_score(result, original_title, authors, year)
            scored_results.append({
                **result,
                'match_score': score
            })
        
        # 按匹配分数降序排序
        scored_results.sort(key=lambda x: x['match_score'], reverse=True)
        
        print(f"📊 结果排序完成，最高分: {scored_results[0]['match_score'] if scored_results else 0}")
        return scored_results

    def _calculate_result_score(self, result: Dict, original_title: str, 
                              authors: List[str] = None, year: str = None) -> float:
        """
        计算单个结果的匹配分数
        """
        score = 0.0
        
        # 1. 标题相似度 (最重要，权重40%)
        result_title = result.get('title', '')
        title_similarity = self._calculate_title_similarity(original_title, result_title)
        score += title_similarity * 0.4
        
        # 2. 作者匹配度 (权重30%)
        if authors:
            result_authors = result.get('authors', '')
            author_match = self._calculate_author_match(authors, result_authors)
            score += author_match * 0.3
        
        # 3. 年份匹配 (权重10%)
        if year and result.get('year'):
            if str(year) == str(result['year']):
                score += 0.1
        
        # 4. 引用数和权威性 (权重20%)
        citation_count = result.get('citationCount', 0)
        if citation_count > 0:
            score += min(0.2, citation_count / 1000)  # 归一化
        
        return round(score, 3)

    def _calculate_author_match(self, query_authors: List[str], result_authors: Any) -> float:
        """
        计算作者匹配度
        """
        if not query_authors or not result_authors:
            return 0.0
            
        # 处理不同类型的作者数据
        if isinstance(result_authors, str):
            result_author_list = [a.strip() for a in result_authors.split(',') if a.strip()]
        elif isinstance(result_authors, list):
            result_author_list = result_authors
        else:
            return 0.0
            
        # 提取姓氏进行比较
        query_last_names = []
        for name in query_authors:
            if name.strip():
                parts = name.split()
                query_last_names.append(parts[-1].lower())
        
        result_last_names = []
        for name in result_author_list:
            if isinstance(name, str) and name.strip():
                parts = name.split()
                result_last_names.append(parts[-1].lower())
        
        if not query_last_names or not result_last_names:
            return 0.0
            
        common_authors = set(query_last_names) & set(result_last_names)
        if not common_authors:
            return 0.0
            
        return len(common_authors) / max(len(query_last_names), len(result_last_names))

    # 以下保持原有方法不变
    def get_paper_by_doi(self, doi: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        通过 DOI 查询论文
        """
        # 清理DOI格式
        clean_doi = doi.strip()
        if clean_doi.startswith('http'):
            clean_doi = clean_doi.split('doi.org/')[-1]
            
        return self.get_paper_by_id(f"DOI:{clean_doi}", use_cache)

    def get_paper_by_arxiv(self, arxiv_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        通过 ArXiv ID 查询论文
        """
        clean_arxiv = arxiv_id.strip()
        if clean_arxiv.startswith('http'):
            clean_arxiv = clean_arxiv.split('arxiv.org/abs/')[-1]
            
        return self.get_paper_by_id(f"ARXIV:{clean_arxiv}", use_cache)

    def get_paper_by_id(self, paper_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        通过 Semantic Scholar ID 或其他外部 ID 查询论文
        """
        print(f"🔍 查询论文: {paper_id}")
        
        # 检查缓存
        cache_key = f"paper_{paper_id}"
        if use_cache and cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                print("✅ 使用缓存结果")
                return data
            else:
                del self.cache[cache_key]
        
        url = f"{self.BASE_URL}/paper/{paper_id}"
        params = {"fields": self.fields}
        
        data = self._make_request(url, params)
        
        if data and data.get("paperId"):
            print("✅ 成功获取论文详情")
            formatted_result = self._format_results([data])[0]
            
            if use_cache:
                self.cache[cache_key] = (time.time(), formatted_result)
                
            return formatted_result
        else:
            print("❌ 未找到论文")
            return {}

    def _format_results(self, raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将 Semantic Scholar 的原始结果格式化为统一格式
        """
        formatted_results = []
    
        for item in raw_results:
            try:
                # 处理作者信息 - 添加空值检查
                authors_list = item.get('authors') or []
                authors = [author.get('name', '') for author in authors_list if isinstance(author, dict)]
                authors_str = ", ".join(authors) if authors else ""
            
                # 处理摘要 - 添加空值检查
                snippet = item.get('abstract', '')
                if not snippet:
                    tldr_obj = item.get('tldr')
                    if isinstance(tldr_obj, dict):
                        snippet = tldr_obj.get('text', '')
                if snippet and len(snippet) > 200:
                    snippet = snippet[:200] + "..."
            
                # 生成最佳链接
                external_ids = item.get('externalIds', {}) or {}
                link = item.get('url', '')  # 默认使用Semantic Scholar链接
            
                if 'DOI' in external_ids and external_ids['DOI']:
                    link = f"https://doi.org/{external_ids['DOI']}"
                elif 'ArXiv' in external_ids and external_ids['ArXiv']:
                    link = f"https://arxiv.org/abs/{external_ids['ArXiv']}"
                elif 'PubMed' in external_ids and external_ids['PubMed']:
                    link = f"https://pubmed.ncbi.nlm.nih.gov/{external_ids['PubMed']}"
            
                # 生成displayLink - 修复空值问题
                venue = item.get('venue', '')
                publication_venue_obj = item.get('publicationVenue')
                publication_venue = ''
                if publication_venue_obj and isinstance(publication_venue_obj, dict):
                    publication_venue = publication_venue_obj.get('name', '')
            
                year = item.get('year', '')
            
                display_link = venue or publication_venue or "Semantic Scholar"
                if year:
                    display_link = f"{display_link} ({year})"
            
                # 计算置信度
                confidence = self._calculate_confidence_score(item)
            
                formatted_results.append({
                    "title": item.get("title", ""),
                    "link": link,
                    "snippet": snippet,
                    "displayLink": display_link,
                    "authors": authors_str,
                    "year": item.get("year"),
                    "citationCount": item.get("citationCount", 0),
                    "referenceCount": item.get("referenceCount", 0),
                    "venue": venue,
                    "fieldsOfStudy": item.get("fieldsOfStudy", []),
                    "source": "Semantic Scholar",
                    "confidence": confidence,
                    "paperId": item.get("paperId", ""),
                    "externalIds": external_ids
                })
            
            except Exception as e:
                print(f"⚠️ 格式化结果时出错: {e}")
                print(f"   出错的数据项: {item}")
                continue  # 跳过这个有问题的结果
    
        return formatted_results

    def _calculate_confidence_score(self, paper: Dict[str, Any]) -> float:
        """
        计算论文结果的置信度分数
        """
        score = 0.0
        
        # 基础信息检查
        if paper.get('title'):
            score += 0.2
        if paper.get('authors'):
            score += 0.2
        if paper.get('year'):
            score += 0.1
        if paper.get('venue') or paper.get('publicationVenue'):
            score += 0.2
        
        # 引用和参考文献
        citation_count = paper.get('citationCount', 0)
        if citation_count > 0:
            score += min(0.2, citation_count / 100)
        
        reference_count = paper.get('referenceCount', 0)
        if reference_count > 0:
            score += 0.1
        
        # 外部标识符
        external_ids = paper.get('externalIds', {})
        if any(external_ids.values()):
            score += 0.2
        
        return min(1.0, round(score, 2))

    def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计信息"""
        return {
            "total_requests": self.request_count,
            "daily_requests": self.daily_request_count,
            "cache_size": len(self.cache),
            "rate_limit_interval": self.min_interval
        }

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        print("✅ 缓存已清空")

    def get_attribution_text(self) -> str:
        """
        生成引用文本，符合Semantic Scholar的引用要求
        """
        return """此服务使用了 Semantic Scholar API 的数据。
请引用：Waleed Ammar, et al. "Construction of the Literature Graph in Semantic Scholar." 
NAACL 2018. https://api.semanticscholar.org/"""