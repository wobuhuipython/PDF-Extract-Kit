"""
PDF 处理器模块
整合提取、分析、上传功能
"""
import os
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from .config import Config
from .pdf_extractor import PDFExtractor
from .pdf_text_extractor import PDFTextExtractor
from .ai_analyzer import AIAnalyzer
from .oss_uploader import OSSUploader
from .data_exporter import DataExporter


class PDFProcessor:
    """PDF 处理器 - 完整流程"""
    
    def __init__(self, pdf_path: str, original_name: str = None):
        """
        初始化
        
        Args:
            pdf_path: PDF 文件路径（可能是临时文件）
            original_name: 原始 PDF 文件名（用于 OSS 上传和数据库记录）
        """
        self.pdf_path = pdf_path
        # 如果提供了原始名称，使用原始名称；否则从路径提取
        self.pdf_name = original_name if original_name else Path(pdf_path).name
        
        print(f"\n📄 PDF: {self.pdf_name}")
        if original_name:
            print(f"   本地路径: {pdf_path}")
        
        # 初始化各个模块
        self.extractor = PDFExtractor()
        self.text_extractor = PDFTextExtractor()
        self.analyzer = AIAnalyzer()
        self.oss_uploader = OSSUploader.from_env()
        self.data_exporter = DataExporter.from_env()  # 修复：使用 from_env() 加载配置
        
        # 提取 PDF 全文
        self.pdf_full_text = self._extract_pdf_text()
        
        # 识别 PDF 行业
        self.pdf_industry = self._classify_pdf_industry()
    
    def _extract_pdf_text(self) -> str:
        """提取 PDF 全文"""
        if not Config.EXTRACT_FULL_TEXT:
            print(f"\n📖 跳过 PDF 文本提取（已禁用）")
            return ""
        
        print(f"\n📖 提取 PDF 文本...")
        try:
            # 根据配置决定提取页数
            max_pages = Config.MAX_TEXT_PAGES if Config.MAX_TEXT_PAGES > 0 else None
            full_text = self.text_extractor.extract_full_text(self.pdf_path, max_pages=max_pages)
            if full_text:
                print(f"   ✅ 提取完成")
                return full_text
            else:
                print(f"   ⚠️  未提取到文本")
                return ""
        except Exception as e:
            print(f"   ⚠️  提取失败: {e}")
            return ""
    
    def _classify_pdf_industry(self) -> str:
        """识别 PDF 所属行业"""
        print(f"\n🏭 识别 PDF 行业...")
        try:
            industry = self.analyzer.classify_industry(
                self.pdf_name,
                full_text=self.pdf_full_text
            )
            print(f"   行业: {industry}")
            return industry
        except Exception as e:
            print(f"   ⚠️  识别失败: {e}")
            return '其它'
    
    def process(self) -> Dict[str, Any]:
        """处理 PDF - 完整流程"""
        print("\n" + "="*80)
        print("🚀 开始处理")
        print("="*80)
        
        start_time = time.time()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. 提取图表
        print("\n步骤 1: 提取图表...")
        # 使用原始 PDF 文件名（不带扩展名）作为输出目录名
        output_dir = os.path.join(Config.OUTPUT_DIR, Path(self.pdf_name).stem)
        charts = self.extractor.extract_charts(self.pdf_path, output_dir)
        
        if not charts:
            print("⚠️  未提取到图表")
            return {
                'success': False,
                'message': '未提取到图表',
                'elapsed_time': time.time() - start_time
            }
        
        print(f"✅ 提取到 {len(charts)} 个图表")
        
        # 2. AI 分析每个图表
        print("\n步骤 2: AI 分析图表...")
        analyzed_charts = []
        
        for idx, chart in enumerate(charts, 1):
            print(f"\n[{idx}/{len(charts)}] 分析图表 {chart['filename']}...")
            
            # 提取图表所在页面的上下文
            page_context = self.text_extractor.extract_context_around_page(
                self.pdf_path,
                chart['page_num'],
                context_pages=1
            )
            
            # 构建完整上下文
            # 策略：使用 PDF 摘要（前2000字）+ 页面详细上下文
            pdf_summary = self.pdf_full_text[:2000] if len(self.pdf_full_text) > 2000 else self.pdf_full_text
            
            full_context = f"""PDF 主题和背景（摘要）：
{pdf_summary}

图表所在页面及前后页内容（详细）：
{page_context}
"""
            
            # AI 分析（带上下文）
            analysis_result = self.analyzer.analyze_chart(
                chart['image_data'],
                chart['page_num'],
                chart_type=chart['type'],
                pdf_context=full_context
            )
            
            if analysis_result['success']:
                title = analysis_result['chart_title']
                analysis_text = analysis_result['analysis_cleaned']
                
                print(f"  标题: {title[:50]}...")
                print(f"  分析长度: {len(analysis_text)} 字符")
                
                # 调试：显示分析内容的前100字
                if analysis_text:
                    print(f"  分析预览: {analysis_text[:100]}...")
                else:
                    print(f"  ⚠️  警告：分析内容为空！")
                
                # 图表行业分类
                chart_industry = self.analyzer.classify_chart_industry(
                    title,
                    analysis_text,
                    self.pdf_industry
                )
                
                # 内容分类
                content_category, category_confidence = self.analyzer.classify_content_category(
                    title,
                    analysis_text
                )
                
                # 获取关键词
                keywords = analysis_result.get('keywords', [])
                keywords_str = ', '.join(keywords) if keywords else '无'
                
                print(f"  行业: {chart_industry}")
                print(f"  分类: {content_category} ({category_confidence:.2f})")
                print(f"  关键词: {keywords_str}")
                
                # 构建完整数据
                chart_data = {
                    'source_file': self.pdf_name,
                    'analysis_time': timestamp,
                    'pdf_industry': self.pdf_industry,
                    'chart_industry': chart_industry,
                    'content_category': content_category,
                    'category_confidence': category_confidence,
                    'page_num': chart['page_num'],
                    'image_index': idx,
                    'image_size': f"{chart['width']}x{chart['height']}",
                    'image_width': chart['width'],
                    'image_height': chart['height'],
                    'image_format': 'png',
                    'image_filename': chart['filename'],
                    'image_url': '',
                    'image_relative_path': '',
                    'chart_title': title,
                    'analysis_cleaned': analysis_text,  # 使用 analysis_text 变量
                    'analysis_length': len(analysis_text),
                    'data_source': analysis_result['data_source'],
                    'keywords': ', '.join(keywords) if keywords else '',  # 关键词（逗号分隔）
                    'image_data': chart['image_data'],
                    'image_path': chart['image_path']
                }

                
                analyzed_charts.append(chart_data)
        
        # 3. 上传到 OSS
        if self.oss_uploader.is_enabled():
            print("\n步骤 3: 上传到 OSS...")
            # 使用原始 PDF 文件名（不带扩展名）作为文件夹名
            folder = Path(self.pdf_name).stem
            
            for chart in analyzed_charts:
                url = self.oss_uploader.upload(
                    chart['image_data'],
                    chart['image_filename'],
                    folder
                )
                if url:
                    chart['image_url'] = url
                    print(f"  ✓ {chart['image_filename']}")
        
        # 4. 上传到 NocoDB
        print(f"\n步骤 4: 检查 NocoDB 上传...")
        print(f"   data_exporter.nocodb_enabled: {self.data_exporter.nocodb_enabled}")
        print(f"   analyzed_charts 数量: {len(analyzed_charts)}")
        
        if self.data_exporter.nocodb_enabled:
            print("\n步骤 4: 上传到 NocoDB...")
            result = self.data_exporter.export_to_nocodb(
                images=analyzed_charts,
                source_file=self.pdf_name,
                timestamp=timestamp,
                pdf_industry=self.pdf_industry
            )
            
            print(f"   [调试] export_to_nocodb 返回结果: {result}")
            
            if result['success']:
                print(f"  ✓ 成功上传 {result.get('inserted_count', 0)} 条记录")
            else:
                print(f"  ✗ 上传失败: {result.get('message', '未知错误')}")
        else:
            print("\n步骤 4: 跳过 NocoDB 上传（未启用）")
        
        # 5. 清理临时文件
        self.extractor.cleanup_temp_files(output_dir)
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "="*80)
        print("✅ 处理完成")
        print(f"   图表数量: {len(analyzed_charts)}")
        print(f"   PDF 行业: {self.pdf_industry}")
        print(f"   耗时: {elapsed_time:.2f}秒")
        print("="*80)
        
        return {
            'success': True,
            'charts': analyzed_charts,
            'pdf_industry': self.pdf_industry,
            'elapsed_time': elapsed_time,
            'timestamp': timestamp
        }
