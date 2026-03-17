"""
主程序 - 本地缓存版本
将提取的图片保存到本地文件夹（不上传到 OSS）
但数据仍然上传到 NocoDB
"""
import torch
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from modules import Config, PDFExtractor, AIAnalyzer, ImageFilter, DataExporter,PDFTextExtractor

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

class LocalCachePDFProcessor:
    """PDF 处理器 - 本地缓存版本"""
    
    def __init__(self, pdf_path: str, cache_dir: str = "pdf_cache"):
        """
        初始化
        
        Args:
            pdf_path: PDF 文件路径
            cache_dir: 本地缓存目录
        """
        self.pdf_path = pdf_path
        self.pdf_name = Path(pdf_path).name
        self.cache_dir = Path(cache_dir)
        
        # 为每个 PDF 创建独立的缓存文件夹
        pdf_stem = Path(self.pdf_name).stem
        self.pdf_cache_dir = self.cache_dir / pdf_stem
        self.pdf_cache_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📄 PDF: {self.pdf_name}")
        print(f"📁 缓存目录: {self.pdf_cache_dir}")
        
        # 初始化各个模块
        self.extractor = PDFExtractor()
        self.text_extractor = PDFTextExtractor()
        self.analyzer = AIAnalyzer()
        self.data_exporter = DataExporter.from_env()  # 用于上传到 NocoDB
        self.image_filter = ImageFilter(
            min_text_length=Config.MIN_TEXT_LENGTH,
            min_number_count=Config.MIN_NUMBER_COUNT,
            strict_mode=Config.OCR_STRICT_MODE,
        )
        
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
    
    def _save_analysis_results(self, analyzed_charts: List[Dict[str, Any]], timestamp: str):
        """
        保存分析结果到 JSON 文件
        
        Args:
            analyzed_charts: 分析后的图表列表
            timestamp: 时间戳
        """
        # 准备保存的数据（移除二进制数据）
        save_data = []
        for chart in analyzed_charts:
            chart_copy = chart.copy()
            # 移除二进制数据，只保留文件路径
            chart_copy.pop('image_data', None)
            save_data.append(chart_copy)
        
        # 构建完整的结果
        result = {
            'pdf_name': self.pdf_name,
            'pdf_industry': self.pdf_industry,
            'analysis_time': timestamp,
            'total_charts': len(analyzed_charts),
            'charts': save_data
        }
        
        # 保存到 JSON 文件
        json_path = self.pdf_cache_dir / 'analysis_result.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 分析结果已保存: {json_path}")
    
    def process(self) -> Dict[str, Any]:
        """处理 PDF - 完整流程"""
        print("\n" + "="*80)
        print("🚀 开始处理（本地缓存模式）")
        print("="*80)
        
        start_time = time.time()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. 提取图表
        print("\n步骤 1: 提取图表...")
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
        
        # 1.5. OCR 过滤空白图片
        if Config.ENABLE_OCR_FILTER:
            charts, filtered_charts = self.image_filter.filter_charts(charts)
            
            if not charts:
                print("⚠️  所有图表都是空白的（已被过滤）")
                return {
                    'success': False,
                    'message': '所有图表都是空白的',
                    'elapsed_time': time.time() - start_time
                }
        else:
            print("   ℹ️  OCR 过滤已禁用")
        
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
                
                # 保存图片到本地
                local_filename = f"page_{chart['page_num']}_chart_{idx}.png"
                local_filepath = self.pdf_cache_dir / local_filename
                
                with open(local_filepath, 'wb') as f:
                    f.write(chart['image_data'])
                
                print(f"  💾 保存图片: {local_filename}")
                
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
                    'image_url': '',  # 不上传 OSS，留空
                    'image_relative_path': str(local_filepath),  # 本地路径
                    'chart_title': title,
                    'analysis': analysis_text,
                    'analysis_length': len(analysis_text),
                    'data_source': analysis_result['data_source'],
                    'keywords': keywords_str,
                    'image_data': chart['image_data'],
                    'image_path': chart['image_path'],
                    'local_cache_path': str(local_filepath)
                }
                
                analyzed_charts.append(chart_data)
        
        # 3. 保存分析结果到 JSON
        print("\n步骤 3: 保存分析结果到本地...")
        self._save_analysis_results(analyzed_charts, timestamp)
        
        # 4. 上传到 NocoDB（不上传图片到 OSS）
        if self.data_exporter.nocodb_enabled:
            print("\n步骤 4: 上传数据到 NocoDB...")
            result = self.data_exporter.export_to_nocodb(
                images=analyzed_charts,
                source_file=self.pdf_name,
                timestamp=timestamp,
                pdf_industry=self.pdf_industry
            )
            
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
        print(f"   缓存目录: {self.pdf_cache_dir}")
        print(f"   耗时: {elapsed_time:.2f}秒")
        print("="*80)
        
        return {
            'success': True,
            'charts': analyzed_charts,
            'pdf_industry': self.pdf_industry,
            'elapsed_time': elapsed_time,
            'timestamp': timestamp,
            'cache_dir': str(self.pdf_cache_dir)
        }


def process_single_pdf(pdf_path: str, cache_dir: str = "pdf_cache"):
    """处理单个 PDF"""
    print("="*80)
    print("📊 PDF-Extract-Kit - 本地缓存模式")
    print("="*80)
    
    Config.print_config()
    
    # 检查文件是否存在
    if not Path(pdf_path).exists():
        print(f"❌ 文件不存在: {pdf_path}")
        return None
    
    try:
        processor = LocalCachePDFProcessor(pdf_path, cache_dir)
        result = processor.process()
        
        if result['success']:
            print(f"\n🎉 处理完成！")
            print(f"\n统计信息:")
            print(f"  图表数量: {len(result['charts'])}")
            print(f"  PDF 行业: {result['pdf_industry']}")
            print(f"  处理时间: {result['elapsed_time']:.2f}秒")
            print(f"  缓存位置: {result['cache_dir']}")
            return result
        else:
            print(f"\n⚠️  {result.get('message', '处理失败')}")
            return None
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_folder(folder_path: str, cache_dir: str = "pdf_cache", recursive: bool = True):
    """批量处理文件夹中的所有 PDF"""
    folder = Path(folder_path)
    
    if not folder.exists() or not folder.is_dir():
        print(f"❌ 文件夹不存在: {folder_path}")
        return
    
    # 查找所有 PDF 文件
    if recursive:
        pdf_files = list(folder.rglob("*.pdf"))
    else:
        pdf_files = list(folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"⚠️  文件夹中没有找到 PDF 文件: {folder_path}")
        return
    
    print("="*80)
    print("📊 PDF-Extract-Kit - 批量处理模式（本地缓存）")
    print("="*80)
    print(f"📁 文件夹: {folder_path}")
    print(f"🔍 递归模式: {'是' if recursive else '否'}")
    print(f"📄 找到 {len(pdf_files)} 个 PDF 文件")
    print(f"💾 缓存目录: {cache_dir}")
    print("="*80)
    
    Config.print_config()
    
    # 统计信息
    total_count = len(pdf_files)
    success_count = 0
    fail_count = 0
    total_charts = 0
    
    # 处理每个 PDF
    for idx, pdf_file in enumerate(pdf_files, 1):
        relative_path = pdf_file.relative_to(folder)
        
        print(f"\n{'='*80}")
        print(f"[{idx}/{total_count}] 处理: {relative_path}")
        print(f"{'='*80}")
        
        try:
            processor = LocalCachePDFProcessor(str(pdf_file), cache_dir)
            result = processor.process()
            
            if result and result['success']:
                success_count += 1
                total_charts += len(result.get('charts', []))
                print(f"✅ 成功: {pdf_file.name}")
            else:
                fail_count += 1
                print(f"❌ 失败: {pdf_file.name}")
                
        except Exception as e:
            fail_count += 1
            print(f"❌ 异常: {pdf_file.name} - {e}")
    
    # 打印总结
    print(f"\n{'='*80}")
    print("📊 批量处理完成")
    print(f"{'='*80}")
    print(f"  总文件数: {total_count}")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    print(f"  提取图表总数: {total_charts}")
    print(f"  缓存位置: {cache_dir}")
    print(f"{'='*80}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PDF Extract with AI Analysis - Local Cache Mode')
    parser.add_argument('--pdf', help='PDF 文件路径（单个文件）')
    parser.add_argument('--folder', help='PDF 文件夹路径（批量处理）')
    parser.add_argument('--cache-dir', default='pdf_cache', help='本地缓存目录（默认: pdf_cache）')
    parser.add_argument('--no-recursive', action='store_true', help='不递归子文件夹（仅处理当前层）')
    
    args = parser.parse_args()
    
    # 检查参数
    if not args.pdf and not args.folder:
        parser.error("请指定 --pdf 或 --folder 参数")
    
    # 单文件模式
    if args.pdf:
        process_single_pdf(args.pdf, args.cache_dir)
    
    # 批量模式
    elif args.folder:
        recursive = not args.no_recursive
        process_folder(args.folder, args.cache_dir, recursive=recursive)


if __name__ == '__main__':
    main()
