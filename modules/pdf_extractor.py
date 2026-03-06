"""
PDF 提取器模块
封装 PDF-Extract-Kit 的图表提取功能
"""
import os
import sys
from pathlib import Path
from PIL import Image
from typing import List, Dict, Any

# 添加 PDF-Extract-Kit 根目录到路径
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

# 导入 pdf_extract.py 的功能
from pdf_extract import extract_figures_with_captions, create_default_config
from pdf_extract_kit.utils.config_loader import initialize_tasks_and_models

from .config import Config


class PDFExtractor:
    """PDF 图表提取器"""
    
    def __init__(self):
        """初始化"""
        self.layout_task = None
        print("📦 初始化 PDF 提取器...")
    
    def extract_charts(self, pdf_path: str, output_dir: str = None) -> List[Dict[str, Any]]:
        """
        提取 PDF 中的图表和表格
        
        Args:
            pdf_path: PDF 文件路径
            output_dir: 输出目录（临时）
            
        Returns:
            提取的图表列表
        """
        if output_dir is None:
            output_dir = Config.OUTPUT_DIR
        
        print(f"\n🔍 提取图表: {Path(pdf_path).name}")
        
        # 1. 创建配置
        config = create_default_config(
            pdf_path,
            output_dir,
            tasks=['layout'],
            visualize=False,
            extract_figures_mode=True
        )
        
        # 2. 初始化模型
        print("   加载布局检测模型...")
        task_instances = initialize_tasks_and_models(config)
        
        if 'layout_detection' not in task_instances:
            raise ValueError("布局检测任务初始化失败")
        
        # 3. 执行布局检测
        print("   执行布局检测...")
        layout_task = task_instances['layout_detection']
        layout_output = os.path.join(output_dir, 'layout_detection')
        layout_results = layout_task.predict_pdfs(pdf_path, layout_output)
        
        # 4. 提取图表
        print("   提取图表和表格...")
        extract_output = os.path.join(output_dir, 'extracted')
        stats = extract_figures_with_captions(
            pdf_path,
            layout_results,
            extract_output,
            max_distance=Config.CAPTION_DISTANCE,
            min_confidence=Config.MIN_CONFIDENCE,
            verbose=False,
            visualize=False
        )
        
        print(f"   ✅ 提取完成: {len(stats['extracted_items'])} 个图表")
        
        # 5. 转换为统一格式
        extracted_charts = []
        for item in stats['extracted_items']:
            # 确定图片路径
            subfolder = 'figures' if item['type'] == 'figure' else 'tables'
            image_path = os.path.join(extract_output, subfolder, item['filename'])
            
            if not os.path.exists(image_path):
                print(f"   ⚠️  图片不存在: {image_path}")
                continue
            
            # 读取图片信息
            try:
                img = Image.open(image_path)
                width, height = img.size
                
                # 读取图片数据
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                
                chart_info = {
                    'type': item['type'],
                    'page_num': item['page'],
                    'filename': item['filename'],
                    'image_path': image_path,
                    'image_data': image_data,
                    'width': width,
                    'height': height,
                    'confidence': item.get('confidence', 1.0),
                    'has_caption': True,
                    'has_footnotes': item.get('has_footnotes', False)
                }
                
                extracted_charts.append(chart_info)
                
            except Exception as e:
                print(f"   ⚠️  处理图片失败 {item['filename']}: {e}")
                continue
        
        return extracted_charts
    
    def cleanup_temp_files(self, output_dir: str):
        """清理临时文件"""
        if not Config.SAVE_LOCAL_IMAGES:
            print("\n🗑️  清理临时文件...")
            try:
                import shutil
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir)
                print("   ✅ 临时文件已清理")
            except Exception as e:
                print(f"   ⚠️  清理失败: {e}")
