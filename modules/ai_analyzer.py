"""
AI分析器 - 提取完整的图表信息
"""

from openai import OpenAI
import base64
import re
from typing import Dict, Any
from .config import Config
from .prompt_manager import PromptManager


class AIAnalyzer:
    """AI图表分析器"""
    
    def __init__(self):
        """初始化"""
        self.client = OpenAI(
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_BASE_URL
        )
        self.prompt_manager = PromptManager()
    
    def analyze_chart(
        self, 
        image_data: bytes, 
        page_num: int, 
        chart_type: str = 'figure',
        pdf_context: str = None
    ) -> Dict[str, Any]:
        """
        分析图表 - 提取完整信息
        
        Args:
            image_data: 图片数据
            page_num: 页码
            chart_type: 图表类型
            pdf_context: PDF 上下文文本（可选）
        """
        try:
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # 使用 prompt_manager 获取提示词
            base_prompt = self.prompt_manager.get_prompt(chart_type)
            
            # 如果有 PDF 上下文，添加到提示词中
            if pdf_context:
                context_prompt = f"""

【PDF 上下文信息】
以下是该图表所在 PDF 的相关内容，请结合这些信息来分析图表：

{pdf_context[:2000]}

请在分析时：
1. 结合 PDF 的主题和内容背景
2. 理解图表在整个文档中的作用
3. 使用 PDF 中提到的专业术语和概念
4. 如果 PDF 中有相关的解释说明，可以引用

"""
                prompt = context_prompt + base_prompt
            else:
                prompt = base_prompt
            
            response = self.client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }],
                max_tokens=1500,
                temperature=0.1
            )
            
            # 检查响应是否有效
            if not response.choices:
                raise ValueError("API 返回空响应")
            
            result_text = response.choices[0].message.content.strip()
            
            # 解析新格式的响应（【图表标题】、【图表分析】、【数据来源】）
            chart_title = self._extract_section(result_text, '图表标题')
            analysis = self._extract_section(result_text, '图表分析')
            data_source = self._extract_section(result_text, '数据来源')
            
            # 清理分析文本
            analysis_cleaned = self._clean_analysis(analysis)
            
            # 提取关键词（最多3个）
            keywords = self._extract_keywords(chart_title, analysis_cleaned)
            
            return {
                'success': True,
                'chart_title': chart_title,
                'chart_type': chart_type,
                'chart_industry': '其它',
                'content_category': '',
                'category_confidence': 0.0,
                'data_source': data_source,
                'analysis': analysis,
                'analysis_cleaned': analysis_cleaned,
                'keywords': keywords  # 新增关键词字段
            }
            
        except Exception as e:
            print(f"         ⚠️  AI分析失败: {e}")
            return {
                'success': False,
                'chart_title': '',
                'chart_type': '',
                'chart_industry': '其它',
                'content_category': '',
                'category_confidence': 0.0,
                'data_source': '',
                'analysis': '',
                'analysis_cleaned': '',
                'keywords': [],  # 新增关键词字段
                'error': str(e)
            }
    
    def _extract_keywords(self, title: str, analysis: str) -> list:
        """
        从图表标题和分析中提取关键词（最多3个）
        
        Args:
            title: 图表标题
            analysis: 图表分析内容
            
        Returns:
            关键词列表（最多3个）
        """
        try:
            # 构建提取关键词的提示
            prompt = f"""请从以下图表信息中提取最重要的3个关键词：

图表标题：{title}
图表分析：{analysis[:500]}

要求：
1. 提取最能代表图表核心内容的3个关键词
2. 关键词应该是名词或名词短语
3. 优先选择行业术语、专业概念、核心数据指标
4. 每个关键词不超过8个字
5. 按重要性排序

返回格式：关键词1,关键词2,关键词3
例如：市场规模,增长率,产业链"""
            
            response = self.client.chat.completions.create(
                model='qwen-turbo',  # 使用快速模型
                messages=[{
                    'role': 'user',
                    'content': prompt
                }],
                max_tokens=50,
                temperature=0.1
            )
            
            if not response.choices:
                return []
            
            result = response.choices[0].message.content.strip()
            
            # 解析关键词（逗号分隔）
            keywords = [kw.strip() for kw in result.split(',') if kw.strip()]
            
            # 限制最多3个
            keywords = keywords[:3]
            
            return keywords
            
        except Exception as e:
            print(f"         ⚠️  关键词提取失败: {e}")
            return []
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """从响应文本中提取指定章节的内容"""
        if not text:
            return ''
        
        # 匹配【章节名】后的内容，直到下一个【或文本结束
        pattern = f'【{section_name}】(.*?)(?=【|$)'
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            content = match.group(1).strip()
            return content
        
        return ''
    
    def _clean_analysis(self, text: str) -> str:
        """清理分析文本"""
        if not text:
            return ''
        
        # 移除多余的空行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 重新组合
        cleaned = '\n'.join(lines)
        
        return cleaned
    
    def classify_industry(self, pdf_name: str, first_page_text: str = '', full_text: str = '') -> str:
        """
        分类PDF所属行业
        
        Args:
            pdf_name: PDF 文件名
            first_page_text: 首页文本
            full_text: 完整文本（可选）
        """
        try:
            # 使用完整文本或首页文本
            content = full_text if full_text else first_page_text
            content_preview = content[:1000] if content else '无'
            
            prompt = f"""请判断以下PDF文档所属的行业领域：

文件名：{pdf_name}
文档内容：{content_preview}

请从以下行业中选择最合适的一个：
信息科技、大消费、生命健康、传媒娱乐、先进制造、节能环保、地产金融、传统产业

只返回行业名称，不要其他文字。"""
            
            response = self.client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[{
                    'role': 'user',
                    'content': prompt
                }],
                max_tokens=50,
                temperature=0.1
            )
            
            if not response.choices:
                raise ValueError("API 返回空响应")
            
            industry = response.choices[0].message.content.strip()
            
            # 验证返回的行业是否在允许列表中
            allowed_industries = ['信息科技', '大消费', '生命健康', '传媒娱乐', '先进制造', '节能环保', '地产金融', '传统产业']
            if industry not in allowed_industries:
                industry = '传统产业'  # 默认分类
            
            return industry if industry else '传统产业'
            
        except Exception as e:
            print(f"   ⚠️  行业分类失败: {e}")
            return '传统产业'
    
    def classify_chart_industry(self, chart_title: str, analysis: str, pdf_industry: str = None) -> str:
        """分类图表所属行业"""
        try:
            prompt = f"""请判断以下图表所属的行业领域：

图表标题：{chart_title}
图表分析：{analysis[:300] if analysis else '无'}
PDF所属行业：{pdf_industry or '未知'}

请从以下行业中选择最合适的一个：
信息科技、大消费、生命健康、传媒娱乐、先进制造、节能环保、地产金融、传统产业

只返回行业名称，不要其他文字。"""
            
            response = self.client.chat.completions.create(
                model='qwen-turbo',
                messages=[{
                    'role': 'user',
                    'content': prompt
                }],
                max_tokens=20,
                temperature=0.1
            )
            
            if not response.choices:
                return pdf_industry or '传统产业'
            
            industry = response.choices[0].message.content.strip()
            
            # 验证返回的行业是否在允许列表中
            allowed_industries = ['信息科技', '大消费', '生命健康', '传媒娱乐', '先进制造', '节能环保', '地产金融', '传统产业']
            if industry not in allowed_industries:
                industry = pdf_industry or '传统产业'
            
            return industry if industry else (pdf_industry or '传统产业')
            
        except Exception as e:
            print(f"         ⚠️  图表行业分类失败: {e}")
            return pdf_industry or '传统产业'
    
    def classify_content_category(self, chart_title: str, analysis: str) -> tuple:
        """
        分类图表内容类别
        
        Returns:
            (category, confidence) 元组
        """
        try:
            prompt = f"""请判断以下图表的内容类别：

图表标题：{chart_title}
图表分析：{analysis[:300] if analysis else '无'}

请从以下类别中选择最合适的一个，并给出匹配度（0-1）：
- 产业概述
- 产业链
- 市场规模
- 竞争格局
- 技术趋势
- 政策法规
- 投资融资
- 企业分析
- 其它

返回格式：类别名称|匹配度
例如：产业链|0.85"""
            
            response = self.client.chat.completions.create(
                model='qwen-turbo',
                messages=[{
                    'role': 'user',
                    'content': prompt
                }],
                max_tokens=30,
                temperature=0.1
            )
            
            if not response.choices:
                return ('其它', 0.0)
            
            result = response.choices[0].message.content.strip()
            
            # 解析结果
            if '|' in result:
                parts = result.split('|')
                category = parts[0].strip()
                try:
                    confidence = float(parts[1].strip())
                except:
                    confidence = 0.5
                return (category, confidence)
            else:
                return (result, 0.5)
            
        except Exception as e:
            print(f"         ⚠️  内容分类失败: {e}")
            return ('其它', 0.0)
