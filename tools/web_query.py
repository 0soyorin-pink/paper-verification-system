import os
import requests
import asyncio
import aiohttp
import re
import json
from urllib.parse import quote
from dotenv import load_dotenv
from .semantic_scholar_client import SemanticScholarClient
from playwright.async_api import async_playwright

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

class WebQuery:
    """
    WebQuery：增强版 - 支持结构化元数据查询（无Google API版本）
    """
    
    def __init__(self):
        self.ss_client = SemanticScholarClient() # 初始化 Semantic Scholar 客户端
        self.baidu_api_key = os.getenv("BAIDU_API_KEY")
        
        # 定义国内权威网站白名单
        self.domestic_paper_sites = [
            "cnki.net",           # 中国知网
            "wanfangdata.com.cn", # 万方数据
            "cqvip.com",          # 维普资讯
        ]
        
        # 定义国际权威网站白名单
        self.international_paper_sites = [
            "semanticscholar.org",
            "aclweb.org",
            "aclanthology.org",
            "ieee.org",
            "springer.com",
            "sciencedirect.com",
            "dl.acm.org",
        ]

        # 定义国内专利网站白名单
        self.domestic_patent_sites = [
            "cnpatent.com",       # 中国专利公布公告网
            "pss-system.gov.cn",  # 国家知识产权局专利检索系统
            "cpquery.cnipa.gov.cn" # 国家知识产权局专利查询
        ]

        # 定义国际专利网站白名单
        self.international_patent_sites = [
            "patents.google.com",
            "uspto.gov",
            "epo.org",
            "wipo.int",
        ]
    
    def _should_use_baidu(self, query: str, title: str = "") -> bool:
        """
        智能判断是否使用百度搜索
        基于中文字符和中文关键词检测
        """
        combined_text = f'{query} {title}'
        
        # 检查中文字符
        if re.search(r'[\u4e00-\u9fff]', combined_text):
            return True
            
        # 检查中文关键词
        chinese_keywords = ['知网', '万方', '维普', '中国', '中文', '专利', '论文', '学术']
        for keyword in chinese_keywords:
            if keyword in combined_text:
                return True
                
        return False

    async def query_paper_enhanced(self, title: str, authors: str = "", year: str = "", journal: str = "", max_results: int = 5):
        """
        增强版论文查询：支持结构化元数据输入
        """
        print(f"📚 增强查询论文: {title}")
        print(f"   作者: {authors}")
        print(f"   年份: {year}")
        print(f"   期刊: {journal}")
    
        query = f'{title} {authors or ""}'
    
        # 只有在英文内容时才使用增强查询
        if not self._should_use_baidu(query, title):
            print("🔍 检测到英文内容，使用增强策略查询 Semantic Scholar...")
            try:
                # 解析作者信息
                extracted_authors = self._extract_authors_from_details(authors)
                
                ss_results = self.ss_client.search_paper_enhanced(
                    title=title, 
                    authors=extracted_authors,
                    year=year,
                    limit=max_results
                )
            
                if ss_results:
                    print(f"✅ Semantic Scholar 增强查询找到 {len(ss_results)} 个结果")
                    return {
                        "source": "semantic_scholar_enhanced",
                        "query": title,
                        "authors": authors,
                        "year": year,
                        "journal": journal,
                        "results": ss_results
                    }
            except Exception as e:
                print(f"⚠️ Semantic Scholar 增强查询失败: {e}")
        else:
            print("🔍 检测到中文内容，增强查询将使用标准中文路由...")
    
        # 增强查询失败或中文内容，回退到标准逻辑
        return await self.query_paper(title, authors, year, journal, max_results)
    
    def _extract_authors_from_details(self, details: str) -> list:
        """
        从details中提取作者列表
        """
        if not details:
            return []
            
        authors = []
        try:
            # 方法1: 查找"作者"关键词
            if '作者' in details:
                author_part = details.split('作者')[-1].split('。')[0].strip()
                # 尝试用逗号、分号或空格分隔作者
                if '，' in author_part:  # 中文逗号
                    authors = [a.strip() for a in author_part.split('，') if a.strip()]
                elif ',' in author_part:  # 英文逗号
                    authors = [a.strip() for a in author_part.split(',') if a.strip()]
                elif ';' in author_part:  # 分号
                    authors = [a.strip() for a in author_part.split(';') if a.strip()]
                else:
                    # 尝试用空格分隔（仅当明显是英文名字时）
                    if re.search(r'[a-zA-Z]', author_part):
                        authors = [a.strip() for a in author_part.split() if a.strip() and len(a) > 1]
            
            # 方法2: 如果没找到作者，但details看起来像作者列表
            if not authors and details and len(details) < 100:
                if '，' in details:
                    authors = [a.strip() for a in details.split('，') if a.strip()]
                elif ',' in details:
                    authors = [a.strip() for a in details.split(',') if a.strip()]
            
        except Exception as e:
            print(f"⚠️ 提取作者信息失败: {e}")
            
        print(f"📝 提取到作者: {authors}")
        return authors

    def _extract_year_from_details(self, details: str) -> str:
        """
        从details中提取年份
        """
        if not details:
            return None
            
        try:
            # 查找4位数字的年份 (1900-2099)
            year_match = re.search(r'\b(19|20)\d{2}\b', details)
            if year_match:
                year = year_match.group()
                print(f"📅 提取到年份: {year}")
                return year
        except Exception as e:
            print(f"⚠️ 提取年份信息失败: {e}")
            
        return None

    async def query_paper(self, title: str, authors: str = "", year: str = "", journal: str = "", max_results: int = 5):
        """
        查询论文信息 - 修正版：严格按语言路由（无Google API版本）
        """
        print(f"📚 查询论文: {title}")
        query = f'{title} {authors or ""}'

        # 智能路由：判断使用百度还是Semantic Scholar
        if self._should_use_baidu(query, title):
            print("🔍 检测到中文内容，优先使用百度搜索...")
            # 1. 尝试百度千帆API搜索
            baidu_results = await self._baidu_qianfan_search(query, "论文")
            if baidu_results and "error" not in baidu_results and len(baidu_results) > 0:
                print("✅ 通过百度千帆API找到结果。")
                return {
                    "source": "baidu_qianfan",
                    "query": query,
                    "authors": authors,
                    "year": year,
                    "journal": journal,
                    "results": baidu_results
                }
        
            # 2. 百度API无结果，尝试网页版百度搜索
            print("⚠️ 百度千帆API未找到结果，尝试网页版百度搜索...")
            baidu_web_results = await self._baidu_web_search(query, self.domestic_paper_sites, "论文-国内")
            if baidu_web_results and "error" not in baidu_web_results and len(baidu_web_results) > 0:
                print("✅ 通过网页版百度搜索找到结果。")
                return {
                    "source": "baidu_web",
                    "query": query,
                    "authors": authors,
                    "year": year,
                    "journal": journal,
                    "results": baidu_web_results
                }
        
            # 3. 百度搜索都失败，才考虑使用Semantic Scholar作为备用
            print("⚠️ 中文搜索无结果，尝试Semantic Scholar作为备用...")
            try:
                extracted_authors = self._extract_authors_from_details(authors)
                
                ss_results = self.ss_client.search_paper_enhanced(
                    title=title, 
                    authors=extracted_authors,
                    year=year,
                    limit=max_results
                )
            
                if ss_results:
                    print("✅ 通过 Semantic Scholar 找到中文论文的英文版本。")
                    return {
                        "source": "semantic_scholar_backup",
                        "query": query,
                        "authors": authors,
                        "year": year,
                        "journal": journal,
                        "results": ss_results
                    }
            except Exception as e:
                print(f"⚠️ Semantic Scholar 备用查询也失败: {e}")
    
        else:
            # 英文内容，直接使用 Semantic Scholar
            print("🔍 检测到英文内容，优先使用 Semantic Scholar...")
            try:
                # 使用增强查询（包含多查询变体和智能排序）
                extracted_authors = self._extract_authors_from_details(authors)
                
                ss_results = self.ss_client.search_paper_enhanced(
                    title=title, 
                    authors=extracted_authors,
                    year=year,
                    limit=max_results
                )
            
                if ss_results:
                    print("✅ 通过 Semantic Scholar 增强查询找到结果。")
                    return {
                        "source": "semantic_scholar_enhanced",
                        "query": query,
                        "authors": authors,
                        "year": year,
                        "journal": journal,
                        "results": ss_results
                    }
            except Exception as e:
                print(f"⚠️ Semantic Scholar 增强查询失败，回退到基础查询: {e}")
                # 回退到基础查询
                ss_results = self.ss_client.search_paper(query, max_results)
                if ss_results:
                    print("✅ 通过 Semantic Scholar 基础查询找到结果。")
                    return {
                        "source": "semantic_scholar_api",
                        "query": query,
                        "authors": authors,
                        "year": year,
                        "journal": journal,
                        "results": ss_results
                    }

        # 4. 所有API查询均失败，直接使用爬虫模式
        print("🔄 所有API查询均无结果，切换到爬虫模式...")
        crawl_results = await self._crawl_paper_sites(title, authors, max_results)
        return {
            "source": "crawler", 
            "query": query,
            "authors": authors,
            "year": year,
            "journal": journal,
            "results": crawl_results
        }
    
    async def query_patent(self, patent_number=None, title=None, inventor=None, max_results=5):
        """
        查询专利信息 - 增强版：智能选择搜索引擎（无Google API版本）
        """
        print(f"📜 查询专利: {patent_number or title}")
        
        if patent_number:
            query = patent_number
        else:
            query = f'{title} {inventor or ""}'

        # 智能路由：判断使用百度还是其他方式
        if self._should_use_baidu(query, title or ""):
            print("🔍 检测到中文内容，优先使用百度搜索...")
            # 1. 尝试百度千帆API搜索
            baidu_results = await self._baidu_qianfan_search(query, "专利")
            if baidu_results and "error" not in baidu_results and len(baidu_results) > 0:
                print("✅ 通过百度千帆API找到结果。")
                return {
                    "source": "baidu_qianfan",
                    "query": query,
                    "results": baidu_results
                }
            
            # 2. 百度API无结果，尝试网页版百度搜索
            print("⚠️ 百度千帆API未找到结果，尝试网页版百度搜索...")
            baidu_web_results = await self._baidu_web_search(query, self.domestic_patent_sites, "专利-国内")
            if baidu_web_results and "error" not in baidu_web_results and len(baidu_web_results) > 0:
                print("✅ 通过网页版百度搜索找到结果。")
                return {
                    "source": "baidu_web",
                    "query": query,
                    "results": baidu_web_results
                }
        else:
            print("🔍 检测到国际内容，直接使用爬虫模式查询国际专利网站...")
            # 对于国际专利，直接使用爬虫模式
            crawl_results = await self._crawl_patent_sites(patent_number, title, max_results)
            if crawl_results and any(site_results for site_results in crawl_results.values() if not site_results.get("error")):
                print("✅ 通过爬虫模式找到国际专利结果。")
                return {
                    "source": "patent_crawler",
                    "query": query,
                    "results": crawl_results
                }

        # 3. 所有查询方法均失败，使用爬虫模式作为最终备用
        print("🔄 所有查询方法均无结果，切换到爬虫模式...")
        crawl_results = await self._crawl_patent_sites(patent_number, title, max_results)
        return {
            "source": "crawler",
            "query": query,
            "results": crawl_results
        }
    
    async def _baidu_qianfan_search(self, query: str, search_type: str):
        """
        使用百度千帆官方搜索API - 仅使用API Key
        """
        if not self.baidu_api_key:
            print("❌ 百度API Key未配置，跳过API搜索")
            return {"error": "百度API Key未配置"}
    
        try:
            print(f"🔍 调用百度千帆API搜索: {query}")
        
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.baidu_api_key}'
            }
        
            # 根据搜索类型选择站点
            if search_type == "论文":
                sites = self.domestic_paper_sites
            else:
                sites = self.domestic_patent_sites
        
            # 在查询字符串中直接添加站点过滤（百度搜索的标准语法）
            site_filters = " OR ".join([f"site:{site}" for site in sites])
            enhanced_query = f'{query} ({site_filters})'
            
            # 构建搜索请求
            payload = {
                'messages': [
                    {
                        'content': enhanced_query,
                        'role': 'user'
                    }
                ],
                'search_source': 'baidu_search_v2'
            }
        
            # 百度 AI 搜索接口
            url = "https://qianfan.baidubce.com/v2/ai_search/web_search"
        
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ 百度千帆API响应成功")
                        return self._parse_baidu_qianfan_response(data)
                    else:
                        error_text = await response.text()
                        print(f"❌ 百度千帆API请求失败: {response.status}, {error_text}")
                        return {"error": f"API请求失败: {response.status}"}
                        
        except Exception as e:
            print(f"❌ 百度千帆API调用异常: {e}")
            return {"error": f"API调用异常: {str(e)}"}
    
    def _parse_baidu_qianfan_response(self, response: dict):
        """
        解析百度千帆搜索返回结果
        """
        try:
            results = []
            
            # 百度千帆 AI 搜索的结果位于 'result' 字段下的 'references' 列表中
            references = response.get('references', [])
            print(f"📊 找到 {len(references)} 个引用结果")
            for item in references:
                result = {
                    "title": item.get('title', ''),
                    "link": item.get('url', ''),
                    "snippet": item.get('content', ''),
                    "displayLink": item.get('web_anchor', '') # 使用 web_anchor 作为 displayLink
                }
                # 确保有有效数据才添加
                if result["title"] or result["link"]:
                    results.append(result)
            print(f"🎯 最终返回 {len(results)} 个有效结果")
            return results
            
        except Exception as e:
            print(f"❌ 百度千帆API结果解析失败: {e}")
            return {"error": f"百度千帆API结果解析失败: {str(e)}"}
    
    async def _baidu_web_search(self, query, sites, search_type):
        """
        网页版百度搜索（降级方案）
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # 构建搜索查询 - 放宽站点限制
                site_filters = " OR ".join([f"site:{site}" for site in sites])
                full_query = f'{query} ({site_filters})'
                encoded_query = quote(full_query)
                
                url = f"https://www.baidu.com/s?wd={encoded_query}"
                print(f"🔍 访问百度网页: {url}")
                
                await page.goto(url, timeout=20000)
                
                # 等待结果加载
                try:
                    await page.wait_for_selector('.result', timeout=10000)
                except:
                    print("⚠️ 未找到标准结果容器，尝试其他选择器...")
                
                # 解析百度搜索结果 - 更健壮的选择器
                baidu_results = await page.evaluate("""() => {
                    const results = [];
                    
                    // 尝试多种选择器
                    const selectors = ['.result', '.c-container', '.result-op'];
                    
                    for (const selector of selectors) {
                        const items = document.querySelectorAll(selector);
                        if (items.length > 0) {
                            console.log(`找到 ${items.length} 个结果使用选择器: ${selector}`);
                            
                            for (let i = 0; i < Math.min(items.length, 10); i++) {
                                const item = items[i];
                                const titleElem = item.querySelector('h3 a') || item.querySelector('.t a') || item.querySelector('a');
                                const snippetElem = item.querySelector('.c-abstract') || item.querySelector('.c-span-last') || item.querySelector('.content-right_2g7x9');
                                const linkElem = item.querySelector('.c-showurl') || item.querySelector('.c-showurl-color');
                                
                                if (titleElem) {
                                    results.push({
                                        title: titleElem.innerText || titleElem.textContent || '',
                                        link: titleElem.href || '',
                                        snippet: snippetElem ? (snippetElem.innerText || snippetElem.textContent) : '',
                                        displayLink: linkElem ? (linkElem.innerText || linkElem.textContent) : ''
                                    });
                                }
                            }
                            break;
                        }
                    }
                    
                    return results;
                }""")
                
                await browser.close()
                print(f"✅ 百度网页搜索 ({search_type}) 返回 {len(baidu_results)} 个结果")
                return baidu_results
                
            except Exception as e:
                await browser.close()
                print(f"❌ 百度网页搜索失败: {e}")
                return {"error": f"百度网页搜索失败: {str(e)}"}
    
    # 移除 _google_api_search 方法
    
    # 保持原有的爬虫方法不变
    async def _crawl_paper_sites(self, title, authors, max_results):
        """
        爬虫方式查询论文网站 - 仅限国际网站
        """
        results = {}
        sites_to_crawl = ["scholar.google.com"]
        
        for site in sites_to_crawl:
            try:
                if "scholar.google.com" in site:
                    site_results = await self._crawl_google_scholar(title, authors)
                else:
                    continue
                    
                results[site] = site_results
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"❌ {site} 爬虫失败: {e}")
                results[site] = {"error": str(e)}
        
        return results
    
    async def _crawl_patent_sites(self, patent_number, title, max_results):
        """
        爬虫方式查询专利网站 - 仅限国际网站
        """
        results = {}
        sites_to_crawl = ["patents.google.com"]
        
        for site in sites_to_crawl:
            try:
                if "patents.google.com" in site:
                    site_results = await self._crawl_google_patents(patent_number, title)
                    results[site] = site_results
                    
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"❌ {site} 爬虫失败: {e}")
                results[site] = {"error": str(e)}
        
        return results
    
    async def _crawl_google_scholar(self, title, authors):
        """
        爬取Google Scholar
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                query = f'{title} {authors or ""}'
                encoded_query = quote(query)
                url = f"https://scholar.google.com/scholar?q={encoded_query}"
                
                await page.goto(url, timeout=15000)
                await page.wait_for_selector('.gs_r', timeout=10000)
                
                content = await page.content()
                if "对不起" in content or "Sorry" in content or "detected unusual" in content:
                    await browser.close()
                    return {"error": "访问被Google Scholar屏蔽"}
                
                scholar_results = await page.evaluate("""() => {
                    const items = document.querySelectorAll('.gs_r');
                    return Array.from(items).slice(0, 3).map(item => ({
                        title: item.querySelector('.gs_rt')?.innerText,
                        link: item.querySelector('.gs_rt a')?.href,
                        authors: item.querySelector('.gs_a')?.innerText,
                        snippet: item.querySelector('.gs_rs')?.innerText,
                        pdf_link: item.querySelector('.gs_ggs a')?.href
                    })).filter(item => item.title);
                }""")
                
                await browser.close()
                return scholar_results
                
            except Exception as e:
                await browser.close()
                return {"error": f"爬取失败: {str(e)}"}
    
    async def _crawl_google_patents(self, patent_number, title):
        """
        爬取Google Patents
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                if patent_number:
                    query = patent_number
                else:
                    query = title
                    
                encoded_query = quote(query)
                url = f"https://patents.google.com/?q={encoded_query}"
                
                await page.goto(url, timeout=15000)
                await page.wait_for_selector('search-result-item', timeout=10000)
                
                patent_results = await page.evaluate("""() => {
                    const items = document.querySelectorAll('search-result-item');
                    return Array.from(items).slice(0, 3).map(item => ({
                        title: item.querySelector('h3')?.innerText,
                        link: item.querySelector('a')?.href,
                        inventor: item.querySelector('.inventor')?.innerText,
                        assignee: item.querySelector('.assignee')?.innerText,
                        date: item.querySelector('.date')?.innerText
                    })).filter(item => item.title);
                }""")
                
                await browser.close()
                return patent_results
                
            except Exception as e:
                await browser.close()
                return {"error": f"爬取失败: {str(e)}"}