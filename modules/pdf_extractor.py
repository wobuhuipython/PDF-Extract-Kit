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
    
    # 类变量：共享的模型实例
    _shared_task_instances = None
    _model_initialized = False
    
    def __init__(self):
        """初始化"""
        print("📦 初始化 PDF 提取器...")
        # 延迟加载模型，只在第一次使用时加载
        if not PDFExtractor._model_initialized:
            self._init_models()
    
    def _init_models(self):
        """初始化模型（只执行一次）"""
        if PDFExtractor._model_initialized:
            return
        
        print("   🔧 加载布局检测模型（首次加载）...")
        
        # 设置环境变量，尝试兼容新 GPU
        import os
        os.environ['TORCH_CUDA_ARCH_LIST'] = '5.0;6.0;7.0;7.5;8.0;8.6;9.0;12.0'
        os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
        
        # 创建一个临时配置来初始化模型
        temp_config = {
            'tasks': {
                'layout_detection': {
                    'model': 'layout_detection_yolo',
                    'model_config': {
                        'device': 'cuda',  # 使用 GPU 加速
                        'img_size': 1024,
                        'conf_thres': 0.85,
                        'iou_thres': 0.45,
                        'model_path': Config.LAYOUT_MODEL_PATH,
                        'visualize': False
                    }
                }
            }
        }
        
        try:
            PDFExtractor._shared_task_instances = initialize_tasks_and_models(temp_config)
            PDFExtractor._model_initialized = True
            print("   ✅ 模型加载完成（已缓存，后续调用将复用）")
        except RuntimeError as e:
            if "CUDA error" in str(e) or "no kernel image" in str(e):
                print(f"   ⚠️  GPU 不兼容，切换到 CPU 模式...")
                # 切换到 CPU
                temp_config['tasks']['layout_detection']['model_config']['device'] = 'cpu'
                PDFExtractor._shared_task_instances = initialize_tasks_and_models(temp_config)
                PDFExtractor._model_initialized = True
                print("   ✅ 模型加载完成（CPU 模式）")
            else:
                raise
    
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
        
        # 使用共享的模型实例
        if 'layout_detection' not in PDFExtractor._shared_task_instances:
            raise ValueError("布局检测任务初始化失败")
        
        try:
            # 执行布局检测
            print("   执行布局检测...")
            layout_task = PDFExtractor._shared_task_instances['layout_detection']
            layout_output = os.path.join(output_dir, 'layout_detection')
            layout_results = layout_task.predict_pdfs(pdf_path, layout_output)
        except Exception as e:
            error_msg = str(e)
            # 检查是否为 MuPDF 错误
            if 'MuPDF error' in error_msg or 'syntax error' in error_msg:
                print(f"   ⚠️  检测到 MuPDF 错误，尝试修复 PDF...")
                fixed_path = self._try_fix_pdf(pdf_path)
                if fixed_path:
                    print(f"   ✅ PDF 修复成功，重新尝试提取...")
                    # 递归调用，使用修复后的 PDF
                    return self.extract_charts(fixed_path, output_dir)
                else:
                    print(f"   ❌ PDF 修复失败，无法处理此文件")
                    raise Exception(f"PDF 文件损坏且无法修复: {error_msg}")
            # 其他错误直接抛出
            raise
        
        # 提取图表
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
    
    def _try_fix_pdf(self, pdf_path: str):
        """
        尝试修复损坏的 PDF
        
        Args:
            pdf_path: 原始 PDF 路径
            
        Returns:
            修复后的 PDF 路径，失败返回 None
        """
        try:
            print(f"   🔧 尝试使用 PyPDF2 修复 PDF...")
            from PyPDF2 import PdfReader, PdfWriter
            
            # 读取原始 PDF
            reader = PdfReader(pdf_path, strict=False)  # 非严格模式，容忍错误
            writer = PdfWriter()
            
            # 复制所有页面
            page_count = 0
            for page in reader.pages:
                try:
                    writer.add_page(page)
                    page_count += 1
                except Exception as e:
                    print(f"   ⚠️  跳过损坏的页面: {e}")
                    continue
            
            if page_count == 0:
                print(f"   ❌ 没有可用的页面")
                return None
            
            # 保存修复后的 PDF
            fixed_path = pdf_path.replace('.pdf', '_fixed.pdf')
            with open(fixed_path, 'wb') as f:
                writer.write(f)
            
            print(f"   ✅ PDF 修复成功: {page_count} 页")
            return fixed_path
            
        except Exception as e:
            print(f"   ❌ PyPDF2 修复失败: {e}")
            
            # 尝试使用 pikepdf 修复
            try:
                print(f"   🔧 尝试使用 pikepdf 修复 PDF...")
                import pikepdf
                
                pdf = pikepdf.open(pdf_path, allow_overwriting_input=True)
                fixed_path = pdf_path.replace('.pdf', '_fixed.pdf')
                pdf.save(fixed_path)
                pdf.close()
                
                print(f"   ✅ pikepdf 修复成功")
                return fixed_path
                
            except ImportError:
                print(f"   ℹ️  pikepdf 未安装，跳过")
                return None
            except Exception as e2:
                print(f"   ❌ pikepdf 修复失败: {e2}")
                return None
