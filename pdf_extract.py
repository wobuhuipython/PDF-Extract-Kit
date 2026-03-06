"""
PDF Extract - 完整的 PDF 内容提取工具
支持布局检测、公式检测/识别、OCR、表格解析等功能
支持提取带标题的图片和表格
"""
import os
import sys
import argparse
import json
from pathlib import Path
from PIL import Image
import numpy as np

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from pdf_extract_kit.utils.config_loader import load_config, initialize_tasks_and_models
from pdf_extract_kit.utils.data_preprocess import load_pdf
import pdf_extract_kit.tasks


def parse_args():
    parser = argparse.ArgumentParser(
        description="PDF 内容提取工具 - 支持布局检测、公式检测/识别、OCR、表格解析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 使用默认配置提取 PDF
  python pdf_extract.py --pdf path/to/file.pdf
  python pdf_extract.py --input path/to/pdf_or_folder
  
  # 指定输出目录
  python pdf_extract.py --pdf path/to/file.pdf --output results
  
  # 只进行 OCR
  python pdf_extract.py --pdf path/to/file.pdf --tasks ocr
  
  # 进行布局检测和 OCR
  python pdf_extract.py --pdf path/to/file.pdf --tasks layout ocr
  
  # 使用自定义配置文件
  python pdf_extract.py --config configs/custom_config.yaml
        """
    )
    
    parser.add_argument('--pdf', type=str, help='输入 PDF 文件路径')
    parser.add_argument('--input', type=str, help='输入 PDF 文件或文件夹路径（与 --pdf 二选一）')
    parser.add_argument('--output', type=str, default='outputs/pdf_extract', 
                        help='输出结果保存路径 (默认: outputs/pdf_extract)')
    parser.add_argument('--config', type=str, help='配置文件路径 (可选)')
    parser.add_argument('--tasks', nargs='+', 
                        choices=['layout', 'formula_det', 'formula_rec', 'ocr', 'table', 'extract_figures'],
                        default=['layout','extract_figures'],
                        help='要执行的任务列表 (默认: 如果使用 --extract-figures 则只执行 layout，否则执行 ocr)')
    parser.add_argument('--extract-figures', action='store_true',
                        help='提取带标题的图片和表格（自动启用布局检测）')
    parser.add_argument('--caption-distance', type=int, default=200,
                        help='图片/表格与标题的最大距离（像素），默认 200')
    parser.add_argument('--min-confidence', type=float, default=0.5,
                        help='最小置信度阈值（0-1），默认 0.5，只提取置信度高于此值的图片/表格')
    parser.add_argument('--visualize', action='store_true', 
                        help='是否可视化结果',default='True')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='显示详细调试信息')
    
    return parser.parse_args()


def create_default_config(input_path, output_path, tasks, visualize=False, extract_figures_mode=False):
    """创建默认配置"""
    config = {
        'inputs': input_path,
        'outputs': output_path,
        'visualize': visualize,
        'tasks': {}
    }
    
    # 布局检测 - 如果是提取图片模式，不在布局检测阶段可视化
    if 'layout' in tasks:
        config['tasks']['layout_detection'] = {
            'model': 'layout_detection_yolo',
            'model_config': {
                'img_size': 1024,
                'conf_thres': 0.85,
                'iou_thres': 0.45,
                'model_path': '/home/root123/文档/liang/PDF-Extract-Kit/models/opendatalab/pdf-extract-kit-1/models/Layout/YOLO/doclayout_yolo_ft.pt',
                'visualize': False if extract_figures_mode else visualize  # 提取图片模式下不可视化布局
            }
        }
    
    # 公式检测
    if 'formula_det' in tasks:
        config['tasks']['formula_detection'] = {
            'model': 'formula_detection_yolo',
            'model_config': {
                'img_size': 1280,
                'conf_thres': 0.25,
                'iou_thres': 0.45,
                'model_path': 'models/MFD/weights.pt',
                'visualize': visualize
            }
        }
    
    # 公式识别
    if 'formula_rec' in tasks:
        config['tasks']['formula_recognition'] = {
            'model': 'formula_recognition_unimernet',
            'model_config': {
                'cfg_path': 'pdf_extract_kit/configs/unimernet.yaml',
                'model_path': 'models/MFR/UniMERNet',
                'visualize': visualize
            }
        }
    
    # OCR
    if 'ocr' in tasks:
        config['tasks']['ocr'] = {
            'model': 'ocr_ppocr',
            'model_config': {
                'lang': 'ch',
                'show_log': False,
                'use_gpu': False,  # 默认使用 CPU，避免 cuDNN 问题
                'det_model_dir': 'models/OCR/PaddleOCR/det/ch_PP-OCRv4_det',
                'rec_model_dir': 'models/OCR/PaddleOCR/rec/ch_PP-OCRv4_rec',
                'det_db_box_thresh': 0.3
            }
        }
    
    # 表格解析
    if 'table' in tasks:
        config['tasks']['table_parsing'] = {
            'model': 'table_parsing_struct_eqtable',
            'model_config': {
                'model_path': 'models/TabRec/StructEqTable',
                'max_new_tokens': 1024,
                'max_time': 30,
                'output_format': 'latex',
                'lmdeploy': False,
                'flash_atten': True
            }
        }
    
    return config


def calculate_distance(box1, box2):
    """计算两个边界框之间的距离
    
    Args:
        box1, box2: [x1, y1, x2, y2] 格式的边界框
        
    Returns:
        float: 两个框之间的最小距离
    """
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    
    # 计算垂直距离
    if y1_max < y2_min:  # box1 在 box2 上方
        vertical_dist = y2_min - y1_max
    elif y2_max < y1_min:  # box1 在 box2 下方
        vertical_dist = y1_min - y2_max
    else:  # 垂直方向有重叠
        vertical_dist = 0
    
    # 计算水平距离
    if x1_max < x2_min:  # box1 在 box2 左侧
        horizontal_dist = x2_min - x1_max
    elif x2_max < x1_min:  # box1 在 box2 右侧
        horizontal_dist = x1_min - x2_max
    else:  # 水平方向有重叠
        horizontal_dist = 0
    
    # 返回欧氏距离
    return np.sqrt(vertical_dist**2 + horizontal_dist**2)


def find_nearest_caption(figure_box, captions, max_distance=200):
    """找到最近的标题（标题必须在图片/表格的上方或左侧，且距离合理）
    
    严格约束确保只匹配真正的图表标题，而不是正文段落
    
    Args:
        figure_box: 图片/表格的边界框 [x1, y1, x2, y2]
        captions: 标题列表，每个标题包含 'bbox' 和其他信息
        max_distance: 最大允许距离
        
    Returns:
        dict or None: 最近的标题信息，如果没有找到则返回 None
    """
    if not captions:
        return None
    
    min_distance = float('inf')
    nearest_caption = None
    
    fig_x1, fig_y1, fig_x2, fig_y2 = figure_box
    fig_center_y = (fig_y1 + fig_y2) / 2
    fig_center_x = (fig_x1 + fig_x2) / 2
    fig_top = fig_y1
    fig_width = fig_x2 - fig_x1
    
    for caption in captions:
        caption_box = caption['bbox']
        cap_x1, cap_y1, cap_x2, cap_y2 = caption_box
        cap_center_y = (cap_y1 + cap_y2) / 2
        cap_center_x = (cap_x1 + cap_x2) / 2
        cap_bottom = cap_y2
        cap_width = cap_x2 - cap_x1
        cap_height = cap_y2 - cap_y1
        
        # 约束1：标题必须在图片上方
        is_above = cap_center_y < fig_center_y
        
        if not is_above:
            continue  # 严格要求标题在上方
        
        # 约束2：标题底部与图片顶部的垂直距离必须很近（紧贴）
        vertical_gap = fig_top - cap_bottom
        # 标题应该紧贴图片，垂直间隙不超过100像素
        if vertical_gap > 100 or vertical_gap < -20:  # 允许轻微重叠
            continue
        
        # 约束3：标题应该相对居中，水平偏移不能太大
        horizontal_offset = abs(cap_center_x - fig_center_x)
        # 标题中心与图片中心的水平偏移不应超过图片宽度的40%
        if horizontal_offset > fig_width * 0.4:
            continue
        
        # 约束4：标题宽度不应该远大于图片宽度
        # 如果标题宽度超过图片宽度的1.5倍，可能是正文段落
        if cap_width > fig_width * 1.5:
            continue
        
        # 约束5：标题高度应该合理（不能太高，否则可能是多行正文）
        # 标准标题通常是1-2行，高度不超过80像素
        if cap_height > 80:
            continue
        
        distance = calculate_distance(figure_box, caption_box)
        
        if distance < min_distance and distance <= max_distance:
            min_distance = distance
            nearest_caption = caption.copy()
            nearest_caption['distance'] = distance
            nearest_caption['vertical_gap'] = vertical_gap
    
    return nearest_caption


def find_related_footnotes(figure_box, caption_box, footnotes, max_distance=100):
    """找到与图表相关的脚注（脚注必须在图表下方且紧贴）
    
    严格约束确保只包含真正的图表脚注（如数据来源），而不是其他内容
    
    Args:
        figure_box: 图片/表格的边界框 [x1, y1, x2, y2]
        caption_box: 标题的边界框 [x1, y1, x2, y2]
        footnotes: 脚注列表
        max_distance: 最大允许距离（默认100像素，比之前更严格）
        
    Returns:
        list: 相关的脚注列表（最多返回1个最近的）
    """
    if not footnotes:
        return []
    
    related_footnotes = []
    
    # 计算图表区域（包含标题）
    combined_box = [
        min(figure_box[0], caption_box[0]),
        min(figure_box[1], caption_box[1]),
        max(figure_box[2], caption_box[2]),
        max(figure_box[3], caption_box[3])
    ]
    
    combined_y_max = combined_box[3]  # 图表底部Y坐标
    combined_center_x = (combined_box[0] + combined_box[2]) / 2
    combined_width = combined_box[2] - combined_box[0]
    
    for footnote in footnotes:
        footnote_box = footnote['bbox']
        fn_x1, fn_y1, fn_x2, fn_y2 = footnote_box
        fn_center_x = (fn_x1 + fn_x2) / 2
        fn_width = fn_x2 - fn_x1
        fn_height = fn_y2 - fn_y1
        
        # 约束1：脚注必须在图表下方
        if fn_y1 < combined_y_max:
            continue
        
        # 约束2：脚注必须紧贴图表（垂直间隙很小）
        vertical_gap = fn_y1 - combined_y_max
        if vertical_gap > 30:  # 脚注必须非常接近图表
            continue
        
        # 约束3：脚注应该相对居中或左对齐
        horizontal_offset = abs(fn_center_x - combined_center_x)
        if horizontal_offset > combined_width * 0.5:
            continue
        
        # 约束4：脚注高度应该合理（通常是单行文本）
        if fn_height > 50:  # 脚注通常不超过50像素高
            continue
        
        distance = calculate_distance(combined_box, footnote_box)
        
        if distance <= max_distance:
            footnote_copy = footnote.copy()
            footnote_copy['distance'] = distance
            footnote_copy['vertical_gap'] = vertical_gap
            related_footnotes.append(footnote_copy)
    
    # 按距离排序，只返回最近的一个
    related_footnotes.sort(key=lambda x: x['distance'])
    return related_footnotes[:1]  # 最多返回1个脚注


def extract_figures_with_captions(pdf_path, layout_results, output_dir, max_distance=200, min_confidence=0.5, verbose=False, visualize=False):
    """提取带标题的图片和表格
    
    Args:
        pdf_path: PDF 文件路径
        layout_results: 布局检测结果（列表或字典）
        output_dir: 输出目录
        max_distance: 图片/表格与标题的最大距离
        min_confidence: 最小置信度阈值（0-1）
        verbose: 是否显示详细信息
        visualize: 是否可视化结果（在图片上标注边界框）
        
    Returns:
        dict: 提取结果统计
    """
    print(f"\n开始提取带标题的图片和表格...")
    print(f"最大标题距离: {max_distance} 像素")
    print(f"最小置信度: {min_confidence}")
    
    # 加载 PDF 页面
    pdf_images = load_pdf(pdf_path)
    
    # 创建输出目录
    figures_dir = os.path.join(output_dir, 'figures')
    tables_dir = os.path.join(output_dir, 'tables')
    if visualize:
        vis_dir = os.path.join(output_dir, 'visualizations')
        os.makedirs(vis_dir, exist_ok=True)
    os.makedirs(figures_dir, exist_ok=True)
    os.makedirs(tables_dir, exist_ok=True)
    
    stats = {
        'total_figures': 0,
        'total_tables': 0,
        'figures_with_caption': 0,
        'tables_with_caption': 0,
        'filtered_by_confidence': 0,
        'extracted_items': []
    }
    
    # 处理布局结果 - 可能是列表或字典
    if isinstance(layout_results, dict):
        # 如果是字典，转换为列表
        layout_list = [(page_id, page_result) for page_id, page_result in layout_results.items()]
    elif isinstance(layout_results, list):
        # 如果是列表，生成页面ID
        layout_list = [(f"page_{i+1:04d}", page_result) for i, page_result in enumerate(layout_results)]
    else:
        raise ValueError(f"不支持的布局结果类型: {type(layout_results)}")
    
    # 处理每一页
    for page_idx, (page_id, page_result) in enumerate(layout_list):
        if verbose:
            print(f"\n处理第 {page_idx + 1} 页: {page_id}")
        
        page_image = pdf_images[page_idx]
        img_width, img_height = page_image.size
        
        # 如果需要可视化，创建一个副本用于绘制
        if visualize:
            from PIL import ImageDraw, ImageFont
            vis_image = page_image.copy()
            draw = ImageDraw.Draw(vis_image)
        
        # 分类检测结果
        figures = []
        tables = []
        captions = []
        footnotes = []  # 添加脚注列表
        
        # 处理 YOLO Results 对象
        if hasattr(page_result, 'boxes'):
            # 这是 YOLO Results 对象
            boxes = page_result.boxes
            if verbose:
                print(f"  检测到 {len(boxes)} 个对象")
            
            for i in range(len(boxes)):
                # 获取边界框坐标 [x1, y1, x2, y2]
                bbox = boxes.xyxy[i].cpu().numpy().tolist()
                # 获取类别ID
                category_id = int(boxes.cls[i].cpu().numpy())
                # 获取置信度
                confidence = float(boxes.conf[i].cpu().numpy())
                
                # 获取类别名称（如果有）
                category_name = page_result.names.get(category_id, f"unknown_{category_id}") if hasattr(page_result, 'names') else str(category_id)
                
                if verbose and i < 5:  # 只显示前5个对象的详细信息
                    print(f"    对象 {i+1}: 类别={category_name}(ID:{category_id}), 置信度={confidence:.2f}, bbox={[int(x) for x in bbox]}")
                
                item = {
                    'bbox': bbox,
                    'category_id': category_id,
                    'category_name': category_name,
                    'confidence': confidence
                }
                
                # 根据实际的类别ID进行分类
                # figure: ID=3, table: ID=5, figure_caption: ID=4, table_caption: ID=6, table_footnote: ID=7
                if category_id == 3:  # figure
                    if confidence >= min_confidence:  # 置信度过滤
                        figures.append(item)
                        stats['total_figures'] += 1
                    else:
                        stats['filtered_by_confidence'] += 1
                elif category_id == 5:  # table (注意：是5不是4)
                    if confidence >= min_confidence:  # 置信度过滤
                        tables.append(item)
                        stats['total_tables'] += 1
                    else:
                        stats['filtered_by_confidence'] += 1
                elif category_id == 4 or category_id == 6:  # figure_caption(4) 或 table_caption(6)
                    captions.append(item)
                elif category_id == 7:  # table_footnote
                    footnotes.append(item)
                    
            if verbose:
                print(f"  类别统计: figure(ID:3)={len(figures)}, table(ID:5)={len(tables)}, caption(ID:4或6)={len(captions)}, footnote(ID:7)={len(footnotes)}")
                if len(boxes) > 0:
                    all_categories = {}
                    for i in range(len(boxes)):
                        cat_id = int(boxes.cls[i].cpu().numpy())
                        cat_name = page_result.names.get(cat_id, f"unknown_{cat_id}") if hasattr(page_result, 'names') else str(cat_id)
                        all_categories[cat_name] = all_categories.get(cat_name, 0) + 1
                    print(f"  所有类别: {all_categories}")
        else:
            # 这是字典格式的结果
            for item in page_result:
                category = item.get('category_id', item.get('category', ''))
                bbox = item['bbox']
                
                if category == 'figure' or category == 3:  # figure
                    figures.append(item)
                    stats['total_figures'] += 1
                elif category == 'table' or category == 5:  # table
                    tables.append(item)
                    stats['total_tables'] += 1
                elif category == 'figure_caption' or category == 4 or category == 6:  # caption
                    captions.append(item)
                elif category == 'table_footnote' or category == 7:  # footnote
                    footnotes.append(item)
        
        if verbose:
            print(f"  找到 {len(figures)} 个图片, {len(tables)} 个表格, {len(captions)} 个标题, {len(footnotes)} 个脚注")
        
        # 为了避免重复，记录已使用的标题
        used_captions = set()
        
        # 处理图片
        for fig_idx, figure in enumerate(figures):
            bbox = figure['bbox']
            
            # 查找未使用的标题
            available_captions = [cap for i, cap in enumerate(captions) if i not in used_captions]
            nearest_caption = find_nearest_caption(bbox, available_captions, max_distance)
            
            if verbose:
                print(f"\n  图片 {fig_idx+1}: bbox={[int(x) for x in bbox]}, 置信度={figure['confidence']:.2f}")
                if nearest_caption:
                    vertical_gap = nearest_caption.get('vertical_gap', 0)
                    print(f"    找到标题: 距离={nearest_caption.get('distance', 0):.1f}px, 垂直间隙={vertical_gap:.1f}px")
                    print(f"    标题bbox={[int(x) for x in nearest_caption['bbox']]}")
                else:
                    print(f"    未找到标题 (最大距离={max_distance}px)")
                    if available_captions:
                        distances = [calculate_distance(bbox, cap['bbox']) for cap in available_captions]
                        min_dist = min(distances) if distances else float('inf')
                        print(f"    最近标题距离: {min_dist:.1f}px")
            
            if nearest_caption:
                # 标记该标题已使用
                caption_idx = next(i for i, cap in enumerate(captions) if cap['bbox'] == nearest_caption['bbox'])
                used_captions.add(caption_idx)
                # 查找相关的脚注
                related_footnotes = find_related_footnotes(bbox, nearest_caption['bbox'], footnotes, max_distance=300)
                
                if verbose and related_footnotes:
                    print(f"    找到 {len(related_footnotes)} 个脚注")
                    for fn in related_footnotes:
                        print(f"      脚注距离={fn['distance']:.1f}px, bbox={[int(x) for x in fn['bbox']]}")
                
                # 只合并图片和标题，不包含其他内容
                # 策略：取标题和图片的最小包围框，而不是扩展到其他元素
                fig_x1, fig_y1, fig_x2, fig_y2 = bbox
                cap_x1, cap_y1, cap_x2, cap_y2 = nearest_caption['bbox']
                
                # 计算标题和图片的合并区域
                merged_x1 = min(fig_x1, cap_x1)
                merged_y1 = min(fig_y1, cap_y1)  # 从标题顶部开始
                merged_x2 = max(fig_x2, cap_x2)
                merged_y2 = max(fig_y2, cap_y2)  # 到图片底部结束
                
                # 如果有脚注，只包含最近的一个（通常是数据来源）
                footnote_bboxes = []
                if related_footnotes:
                    # 只取第一个（最近的）脚注
                    fn = related_footnotes[0]
                    fn_x1, fn_y1, fn_x2, fn_y2 = fn['bbox']
                    
                    # 检查脚注是否真的在图表正下方（垂直距离很近）
                    vertical_gap_to_footnote = fn_y1 - merged_y2
                    if vertical_gap_to_footnote < 30:  # 脚注必须非常紧贴图表
                        merged_x1 = min(merged_x1, fn_x1)
                        merged_y2 = max(merged_y2, fn_y2)
                        footnote_bboxes.append(fn['bbox'])
                        if verbose:
                            print(f"    包含脚注（垂直间隙={vertical_gap_to_footnote:.1f}px）")
                    elif verbose:
                        print(f"    跳过脚注（垂直间隙={vertical_gap_to_footnote:.1f}px 太远）")
                
                # 添加小边距
                padding = 5
                merged_x1 = max(0, int(merged_x1 - padding))
                merged_y1 = max(0, int(merged_y1 - padding))
                merged_x2 = min(img_width, int(merged_x2 + padding))
                merged_y2 = min(img_height, int(merged_y2 + padding))
                
                # 裁剪完整区域
                cropped_img = page_image.crop((merged_x1, merged_y1, merged_x2, merged_y2))
                
                # 生成文件名
                filename = f"page{page_idx+1:03d}_figure{fig_idx+1:02d}.png"
                filepath = os.path.join(figures_dir, filename)
                cropped_img.save(filepath)
                
                # 可视化
                if visualize:
                    # 绘制合并后的边界框（绿色粗线）
                    draw.rectangle([merged_x1, merged_y1, merged_x2, merged_y2], outline='green', width=4)
                    label = f'Figure {fig_idx+1}'
                    if related_footnotes:
                        label += f' (+{len(related_footnotes)} footnote{"s" if len(related_footnotes) > 1 else ""})'
                    draw.text((merged_x1, merged_y1-25), label, fill='green')
                    
                    # 绘制图片原始边界框（浅绿色）
                    draw.rectangle([int(fig_x1), int(fig_y1), int(fig_x2), int(fig_y2)], outline='lightgreen', width=2)
                    
                    # 绘制标题原始边界框（蓝色）
                    draw.rectangle([int(cap_x1), int(cap_y1), int(cap_x2), int(cap_y2)], outline='blue', width=2)
                    
                    # 绘制脚注边界框（紫色）
                    for fn_bbox in footnote_bboxes:
                        fn_x1, fn_y1, fn_x2, fn_y2 = fn_bbox
                        draw.rectangle([int(fn_x1), int(fn_y1), int(fn_x2), int(fn_y2)], outline='purple', width=2)
                
                # 保存元数据
                metadata = {
                    'type': 'figure',
                    'page': page_idx + 1,
                    'figure_bbox': bbox,
                    'caption_bbox': nearest_caption['bbox'],
                    'footnote_bboxes': footnote_bboxes,
                    'merged_bbox': [merged_x1, merged_y1, merged_x2, merged_y2],
                    'caption_distance': nearest_caption.get('distance', 0),
                    'confidence': figure['confidence'],
                    'has_footnotes': len(related_footnotes) > 0,
                    'filename': filename
                }
                
                stats['figures_with_caption'] += 1
                stats['extracted_items'].append(metadata)
                
                if verbose:
                    footnote_info = f" + {len(related_footnotes)} 脚注" if related_footnotes else ""
                    print(f"  ✓ 提取图片（含标题{footnote_info}）: {filename}")
                    print(f"    合并区域: {[merged_x1, merged_y1, merged_x2, merged_y2]}")
            else:
                if verbose:
                    print(f"  ✗ 跳过图片 {fig_idx+1}: 未找到附近的标题")
        
        # 处理表格
        for tab_idx, table in enumerate(tables):
            bbox = table['bbox']
            
            # 查找未使用的标题
            available_captions = [cap for i, cap in enumerate(captions) if i not in used_captions]
            nearest_caption = find_nearest_caption(bbox, available_captions, max_distance)
            
            if verbose:
                print(f"\n  表格 {tab_idx+1}: bbox={[int(x) for x in bbox]}, 置信度={table['confidence']:.2f}")
                if nearest_caption:
                    vertical_gap = nearest_caption.get('vertical_gap', 0)
                    print(f"    找到标题: 距离={nearest_caption.get('distance', 0):.1f}px, 垂直间隙={vertical_gap:.1f}px")
                    print(f"    标题bbox={[int(x) for x in nearest_caption['bbox']]}")
                else:
                    print(f"    未找到标题 (最大距离={max_distance}px)")
                    if available_captions:
                        distances = [calculate_distance(bbox, cap['bbox']) for cap in available_captions]
                        min_dist = min(distances) if distances else float('inf')
                        print(f"    最近标题距离: {min_dist:.1f}px")
            
            if nearest_caption:
                # 标记该标题已使用
                caption_idx = next(i for i, cap in enumerate(captions) if cap['bbox'] == nearest_caption['bbox'])
                used_captions.add(caption_idx)
                # 查找相关的脚注
                related_footnotes = find_related_footnotes(bbox, nearest_caption['bbox'], footnotes, max_distance=300)
                
                if verbose and related_footnotes:
                    print(f"    找到 {len(related_footnotes)} 个脚注")
                    for fn in related_footnotes:
                        print(f"      脚注距离={fn['distance']:.1f}px, bbox={[int(x) for x in fn['bbox']]}")
                
                # 只合并表格和标题，不包含其他内容
                tab_x1, tab_y1, tab_x2, tab_y2 = bbox
                cap_x1, cap_y1, cap_x2, cap_y2 = nearest_caption['bbox']
                
                # 计算标题和表格的合并区域
                merged_x1 = min(tab_x1, cap_x1)
                merged_y1 = min(tab_y1, cap_y1)  # 从标题顶部开始
                merged_x2 = max(tab_x2, cap_x2)
                merged_y2 = max(tab_y2, cap_y2)  # 到表格底部结束
                
                # 如果有脚注，只包含最近的一个（通常是数据来源）
                footnote_bboxes = []
                if related_footnotes:
                    # 只取第一个（最近的）脚注
                    fn = related_footnotes[0]
                    fn_x1, fn_y1, fn_x2, fn_y2 = fn['bbox']
                    
                    # 检查脚注是否真的在表格正下方（垂直距离很近）
                    vertical_gap_to_footnote = fn_y1 - merged_y2
                    if vertical_gap_to_footnote < 30:  # 脚注必须非常紧贴表格
                        merged_x1 = min(merged_x1, fn_x1)
                        merged_y2 = max(merged_y2, fn_y2)
                        footnote_bboxes.append(fn['bbox'])
                        if verbose:
                            print(f"    包含脚注（垂直间隙={vertical_gap_to_footnote:.1f}px）")
                    elif verbose:
                        print(f"    跳过脚注（垂直间隙={vertical_gap_to_footnote:.1f}px 太远）")
                
                # 添加小边距
                padding = 5
                merged_x1 = max(0, int(merged_x1 - padding))
                merged_y1 = max(0, int(merged_y1 - padding))
                merged_x2 = min(img_width, int(merged_x2 + padding))
                merged_y2 = min(img_height, int(merged_y2 + padding))
                
                # 裁剪完整区域
                cropped_img = page_image.crop((merged_x1, merged_y1, merged_x2, merged_y2))
                
                # 生成文件名
                filename = f"page{page_idx+1:03d}_table{tab_idx+1:02d}.png"
                filepath = os.path.join(tables_dir, filename)
                cropped_img.save(filepath)
                
                # 可视化
                if visualize:
                    # 绘制合并后的边界框（橙色粗线）
                    draw.rectangle([merged_x1, merged_y1, merged_x2, merged_y2], outline='orange', width=4)
                    label = f'Table {tab_idx+1}'
                    if related_footnotes:
                        label += f' (+{len(related_footnotes)} footnote{"s" if len(related_footnotes) > 1 else ""})'
                    draw.text((merged_x1, merged_y1-25), label, fill='orange')
                    
                    # 绘制表格原始边界框（浅橙色）
                    draw.rectangle([int(tab_x1), int(tab_y1), int(tab_x2), int(tab_y2)], outline='lightyellow', width=2)
                    
                    # 绘制标题原始边界框（蓝色）
                    draw.rectangle([int(cap_x1), int(cap_y1), int(cap_x2), int(cap_y2)], outline='blue', width=2)
                    
                    # 绘制脚注边界框（紫色）
                    for fn_bbox in footnote_bboxes:
                        fn_x1, fn_y1, fn_x2, fn_y2 = fn_bbox
                        draw.rectangle([int(fn_x1), int(fn_y1), int(fn_x2), int(fn_y2)], outline='purple', width=2)
                
                # 保存元数据
                metadata = {
                    'type': 'table',
                    'page': page_idx + 1,
                    'table_bbox': bbox,
                    'caption_bbox': nearest_caption['bbox'],
                    'footnote_bboxes': footnote_bboxes,
                    'merged_bbox': [merged_x1, merged_y1, merged_x2, merged_y2],
                    'caption_distance': nearest_caption.get('distance', 0),
                    'confidence': table['confidence'],
                    'has_footnotes': len(related_footnotes) > 0,
                    'filename': filename
                }
                
                stats['tables_with_caption'] += 1
                stats['extracted_items'].append(metadata)
                
                if verbose:
                    footnote_info = f" + {len(related_footnotes)} 脚注" if related_footnotes else ""
                    print(f"  ✓ 提取表格（含标题{footnote_info}）: {filename}")
                    print(f"    合并区域: {[merged_x1, merged_y1, merged_x2, merged_y2]}")
            else:
                if verbose:
                    print(f"  ✗ 跳过表格 {tab_idx+1}: 未找到附近的标题")
        
        # 保存可视化结果
        if visualize:
            vis_filename = f"page{page_idx+1:03d}_visualization.png"
            vis_filepath = os.path.join(vis_dir, vis_filename)
            vis_image.save(vis_filepath)
            if verbose:
                print(f"  可视化结果保存至: {vis_filename}")
    
    # 保存元数据到 JSON
    metadata_file = os.path.join(output_dir, 'extracted_metadata.json')
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    return stats


def run_extraction(config, verbose=False, extract_figures=False, caption_distance=200, min_confidence=0.5):
    """执行 PDF 提取任务"""
    print("=" * 60)
    print("开始 PDF 内容提取...")
    print("=" * 60)
    
    # 初始化任务和模型
    print("\n正在初始化任务和模型...")
    try:
        task_instances = initialize_tasks_and_models(config)
        print(f"✓ 成功初始化 {len(task_instances)} 个任务: {list(task_instances.keys())}")
        
        # 检查是否至少有一个任务被初始化
        if len(task_instances) == 0:
            print("\n错误: 没有任何任务被初始化！")
            print("配置内容:")
            print(json.dumps(config, indent=2, ensure_ascii=False))
            print("\n可能的原因:")
            print("1. 配置文件中没有定义任何任务")
            print("2. 模型文件不存在或路径不正确")
            print("3. 任务名称不匹配")
            raise ValueError("没有任何任务被初始化")
            
    except Exception as e:
        print(f"✗ 初始化任务失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    input_data = config.get('inputs')
    output_path = config.get('outputs', 'outputs/pdf_extract')
    visualize = config.get('visualize', False)
    
    # 创建输出目录
    os.makedirs(output_path, exist_ok=True)
    
    results = {}
    layout_results_dict = None
    total_tasks = len(task_instances)
    current_task = 0
    
    # 执行布局检测
    if 'layout_detection' in task_instances:
        current_task += 1
        print(f"\n[{current_task}/{total_tasks}] 执行布局检测...")
        try:
            layout_task = task_instances['layout_detection']
            layout_output = os.path.join(output_path, 'layout_detection')
            
            # 判断输入是 PDF 还是图片
            if os.path.isfile(input_data) and input_data.lower().endswith('.pdf'):
                if verbose:
                    print(f"   处理 PDF 文件: {input_data}")
                layout_results_dict = layout_task.predict_pdfs(input_data, layout_output)
                results['layout'] = layout_results_dict
            else:
                if verbose:
                    print(f"   处理图片文件/文件夹: {input_data}")
                results['layout'] = layout_task.predict_images(input_data, layout_output)
            
            print(f"   ✓ 布局检测完成，结果保存至: {layout_output}")
            
            # 检查输出文件
            if verbose and os.path.exists(layout_output):
                files = os.listdir(layout_output)
                print(f"   生成了 {len(files)} 个文件")
                
        except Exception as e:
            print(f"   ✗ 布局检测失败: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
    
    # 提取带标题的图片和表格
    if verbose:
        print(f"\n调试信息:")
        print(f"  extract_figures: {extract_figures}")
        print(f"  layout_results_dict is not None: {layout_results_dict is not None}")
        print(f"  input_data: {input_data}")
        print(f"  is PDF: {os.path.isfile(input_data) and input_data.lower().endswith('.pdf')}")
    
    if extract_figures and layout_results_dict and os.path.isfile(input_data) and input_data.lower().endswith('.pdf'):
        print(f"\n提取带标题的图片和表格...")
        try:
            extract_output = os.path.join(output_path, 'extracted_figures_tables')
            stats = extract_figures_with_captions(
                input_data, 
                layout_results_dict, 
                extract_output,
                max_distance=caption_distance,
                min_confidence=min_confidence,
                verbose=verbose,
                visualize=visualize  # 传递可视化参数
            )
            
            print(f"\n提取统计:")
            print(f"  总图片数: {stats['total_figures']}, 带标题: {stats['figures_with_caption']}")
            print(f"  总表格数: {stats['total_tables']}, 带标题: {stats['tables_with_caption']}")
            print(f"  置信度过滤: {stats['filtered_by_confidence']} 个")
            print(f"  结果保存至: {extract_output}")
            if visualize:
                print(f"  可视化结果保存至: {os.path.join(extract_output, 'visualizations')}")
            
            results['extracted_figures'] = stats
            
        except Exception as e:
            print(f"   ✗ 提取图片表格失败: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
    elif extract_figures:
        print(f"\n警告: 无法提取图片和表格")
        if not layout_results_dict:
            print("  原因: 布局检测结果为空")
        if not (os.path.isfile(input_data) and input_data.lower().endswith('.pdf')):
            print("  原因: 输入不是 PDF 文件")
    
    # 执行公式检测
    if 'formula_detection' in task_instances:
        current_task += 1
        print(f"\n[{current_task}/{total_tasks}] 执行公式检测...")
        try:
            formula_det_task = task_instances['formula_detection']
            formula_det_output = os.path.join(output_path, 'formula_detection')
            
            if os.path.isfile(input_data) and input_data.lower().endswith('.pdf'):
                results['formula_detection'] = formula_det_task.predict_pdfs(input_data, formula_det_output)
            else:
                results['formula_detection'] = formula_det_task.predict(input_data, formula_det_output)
                
            print(f"   ✓ 公式检测完成，结果保存至: {formula_det_output}")
            
            if verbose and os.path.exists(formula_det_output):
                files = os.listdir(formula_det_output)
                print(f"   生成了 {len(files)} 个文件")
                
        except Exception as e:
            print(f"   ✗ 公式检测失败: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
    
    # 执行公式识别
    if 'formula_recognition' in task_instances:
        current_task += 1
        print(f"\n[{current_task}/{total_tasks}] 执行公式识别...")
        try:
            formula_rec_task = task_instances['formula_recognition']
            formula_rec_output = os.path.join(output_path, 'formula_recognition')
            results['formula_recognition'] = formula_rec_task.predict(input_data, formula_rec_output)
            print(f"   ✓ 公式识别完成，结果保存至: {formula_rec_output}")
            
            if verbose and os.path.exists(formula_rec_output):
                files = os.listdir(formula_rec_output)
                print(f"   生成了 {len(files)} 个文件")
                
        except Exception as e:
            print(f"   ✗ 公式识别失败: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
    
    # 执行 OCR
    if 'ocr' in task_instances:
        current_task += 1
        print(f"\n[{current_task}/{total_tasks}] 执行 OCR 文字识别...")
        try:
            ocr_task = task_instances['ocr']
            ocr_output = os.path.join(output_path, 'ocr')
            
            if verbose:
                print(f"   输入文件: {input_data}")
                print(f"   输出目录: {ocr_output}")
                print(f"   可视化: {visualize}")
            
            results['ocr'] = ocr_task.process(input_data, save_dir=ocr_output, visualize=visualize)
            print(f"   ✓ OCR 识别完成，结果保存至: {ocr_output}")
            
            # 检查输出文件
            if os.path.exists(ocr_output):
                if os.path.isdir(ocr_output):
                    files = []
                    for root, dirs, filenames in os.walk(ocr_output):
                        files.extend(filenames)
                    print(f"   生成了 {len(files)} 个文件")
                    if verbose and files:
                        print(f"   文件列表: {files[:5]}{'...' if len(files) > 5 else ''}")
            else:
                print(f"   警告: 输出目录不存在")
                
        except Exception as e:
            print(f"   ✗ OCR 识别失败: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
    
    # 执行表格解析
    if 'table_parsing' in task_instances:
        current_task += 1
        print(f"\n[{current_task}/{total_tasks}] 执行表格解析...")
        try:
            table_task = task_instances['table_parsing']
            table_output = os.path.join(output_path, 'table_parsing')
            results['table'] = table_task.predict(input_data, table_output)
            print(f"   ✓ 表格解析完成，结果保存至: {table_output}")
            
            if verbose and os.path.exists(table_output):
                files = os.listdir(table_output)
                print(f"   生成了 {len(files)} 个文件")
                
        except Exception as e:
            print(f"   ✗ 表格解析失败: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
    
    return results, output_path


def main():
    args = parse_args()
    
    # 确定输入路径（支持 --pdf 和 --input 两种参数）
    input_path = args.pdf if args.pdf else args.input
    
    # 设置默认任务
    if args.tasks is None:
        if args.extract_figures:
            args.tasks = ['layout']  # 提取图片时只需要布局检测
            print("提示: 提取图片模式，只执行布局检测任务")
        else:
            args.tasks = ['ocr']  # 默认执行 OCR
    
    # 如果启用了提取图片功能，确保布局检测任务存在
    if args.extract_figures and 'layout' not in args.tasks:
        args.tasks.insert(0, 'layout')
        print("提示: 启用图片提取功能，自动添加布局检测任务")
    
    # 移除不需要的任务（提取图片时不需要 OCR）
    if args.extract_figures and 'ocr' in args.tasks:
        args.tasks.remove('ocr')
        print("提示: 提取图片模式，移除 OCR 任务")
    
    # 如果提供了配置文件，直接使用
    if args.config:
        print(f"使用配置文件: {args.config}")
        config = load_config(args.config)
    else:
        # 检查输入路径
        if not input_path:
            print("错误: 请提供 --pdf 或 --input 参数，或使用 --config 指定配置文件")
            print("使用 --help 查看帮助信息")
            sys.exit(1)
        
        if not os.path.exists(input_path):
            print(f"错误: 输入路径不存在: {input_path}")
            sys.exit(1)
        
        print(f"输入路径: {input_path}")
        print(f"输出路径: {args.output}")
        print(f"执行任务: {', '.join(args.tasks)}")
        if args.extract_figures:
            print(f"提取带标题的图片和表格: 是 (最大距离: {args.caption_distance} 像素)")
        print(f"可视化: {'是' if args.visualize else '否'}")
        
        if args.verbose:
            print(f"\n调试信息:")
            print(f"  - Python 版本: {sys.version}")
            print(f"  - 工作目录: {os.getcwd()}")
            print(f"  - 输入文件绝对路径: {os.path.abspath(input_path)}")
            if os.path.isfile(input_path):
                print(f"  - 输入文件大小: {os.path.getsize(input_path) / 1024 / 1024:.2f} MB")
        
        # 创建默认配置
        config = create_default_config(
            input_path, 
            args.output, 
            args.tasks, 
            args.visualize,
            extract_figures_mode=args.extract_figures  # 传递提取图片模式标志
        )
        
        if args.verbose:
            print(f"\n生成的配置:")
            print(json.dumps(config, indent=2, ensure_ascii=False))
    
    # 执行提取
    try:
        results, output_path = run_extraction(
            config, 
            verbose=args.verbose,
            extract_figures=args.extract_figures,
            caption_distance=args.caption_distance,
            min_confidence=args.min_confidence
        )
        
        print("\n" + "=" * 60)
        print("PDF 内容提取完成！")
        print("=" * 60)
        print(f"\n所有结果已保存至: {os.path.abspath(output_path)}")
        
        if results:
            print("\n提取的内容包括:")
            for task_name in results.keys():
                print(f"  - {task_name}")
        else:
            print("\n警告: 没有生成任何结果")
        
        return 0
        
    except Exception as e:
        print(f"\n错误: 提取过程中出现异常")
        print(f"详细信息: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
