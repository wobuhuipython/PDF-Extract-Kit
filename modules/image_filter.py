"""
图片过滤模块 - 使用 OCR 检测图片是否包含有效内容
"""
import io
import re
import numpy as np
from PIL import Image
from typing import Tuple, Optional


class ImageFilter:
    """图片过滤器 - 过滤空白或无效图片"""
    
    def __init__(self, min_text_length: int = 5, min_number_count: int = 3, strict_mode: bool = True):
        """
        初始化过滤器
        
        Args:
            min_text_length: 最小文字长度阈值
            min_number_count: 最小数字数量（图表通常包含较多数字）
            strict_mode: 严格模式（宁可错杀，不可放过）
        """
        self.min_text_length = min_text_length
        self.min_number_count = min_number_count
        self.strict_mode = strict_mode
        self.ocr = None
        self._init_ocr()
    
    def _init_ocr(self):
        """初始化 OCR 引擎"""
        try:
            import os
            from paddleocr import PaddleOCR
            
            # 使用 CPU 模式（避免 cuDNN 加载问题）
            # OCR 过滤只是快速检测，CPU 速度已经足够
            self.ocr = PaddleOCR(
                use_angle_cls=False,  # 不使用方向分类
                lang='ch',  # 中英文
                show_log=False,  # 不显示日志
                use_gpu=False,  # 使用 CPU（避免 cuDNN 问题）
            )
            print("✅ OCR 引擎初始化成功（PaddleOCR - CPU 模式）")
        except ImportError:
            print("⚠️  PaddleOCR 未安装，图片过滤功能将被禁用")
            print("   安装命令: pip install paddleocr paddlepaddle")
            self.ocr = None
        except (RuntimeError, OSError, Exception) as e:
            error_msg = str(e)
            print(f"⚠️  OCR 引擎初始化失败: {e}")
            print(f"   图片过滤功能已禁用，所有图片将被保留")
            self.ocr = None
    
    def has_content(self, image_data: bytes) -> Tuple[bool, str, dict]:
        """
        检查图片是否包含有效内容（数据图表）
        
        Args:
            image_data: 图片二进制数据
        
        Returns:
            (是否有内容, 检测到的文字, 分析详情)
        """
        if self.ocr is None:
            # OCR 未启用，默认认为有内容
            return True, "OCR未启用", {}
        
        try:
            # 转换为 PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # 转换为 numpy 数组
            img_array = np.array(image)
            
            # OCR 识别
            result = self.ocr.ocr(img_array, cls=False)
            
            if not result or not result[0]:
                # 没有检测到文字
                return False, "", {'reason': '无文字'}
            
            # 提取所有文字
            texts = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0] if isinstance(line[1], tuple) else line[1]
                    texts.append(text)
            
            full_text = ''.join(texts)
            
            # 多维度判断是否是有效的数据图表
            analysis = self._analyze_chart_content(full_text)
            
            return analysis['is_valid'], full_text, analysis
            
        except Exception as e:
            print(f"   ⚠️  OCR 检测异常: {e}")
            # 异常时默认认为有内容（避免误删）
            return True, f"检测异常: {e}", {}
    
    def _analyze_chart_content(self, text: str) -> dict:
        """
        分析文字内容，判断是否是有效的数据图表
        
        判断标准：
        1. 文字长度 >= min_text_length
        2. 包含足够的数字（图表通常有数据）
        3. 不是纯 logo/装饰图
        4. 不是示意图/概念图（如"特许4S店"、"体验店"等标签图）
        5. 不是功能拆解图/流程图（如"Sale 整车销售"这种）
        6. 不是实物照片（通常只有图号标题，无数据）
        
        Args:
            text: OCR 识别的文字
        
        Returns:
            分析结果字典
        """
        # 1. 检查文字长度
        text_length = len(text)
        if text_length < self.min_text_length:
            return {
                "is_valid": False,
                "reason": f"文字太少({text_length}字)",
                "text_length": text_length,
                "number_count": 0,
            }

        # 2. 统计数字数量（包括百分号、小数点）
        numbers = re.findall(r"\d+\.?\d*%?", text)
        number_count = len(numbers)

        # 3. 检查是否包含数据相关的关键词
        data_keywords = [
            "数据",
            "统计",
            "分析",
            "比例",
            "占比",
            "增长",
            "下降",
            "趋势",
            "%",
            "亿",
            "万",
            "千",
            "百",
            "元",
            "美元",
            "人民币",
            "年",
            "月",
            "季度",
            "Q1",
            "Q2",
            "Q3",
            "Q4",
            "data",
            "statistics",
            "analysis",
            "growth",
            "rate",
        ]
        has_data_keyword = any(keyword in text for keyword in data_keywords)

        # 4. 检查是否是装饰性/示意性图片的特征
        # 这类图片通常只有简短的标签文字，没有数据
        decorative_patterns = [
            r"^[a-zA-Z]{1,15}$",  # 单个英文单词
            r"^[\u4e00-\u9fa5]{1,8}$",  # 1-8个汉字（如"体验店"）
            r"^[\u4e00-\u9fa5]{1,5}[a-zA-Z0-9]{1,5}[\u4e00-\u9fa5]{0,3}$",  # 如"特许4S店"
        ]
        is_decorative = any(re.match(pattern, text.strip()) for pattern in decorative_patterns)

        # 5. 检查是否是示意图/概念图的常见词汇
        # 这类图片通常是场景展示，不包含数据
        concept_keywords = [
            "店",
            "超市",
            "公园",
            "园区",
            "中心",
            "广场",
            "大厦",
            "商场",
            "体验",
            "展示",
            "示意",
            "模式",
            "场景",
            "网络",
            "store",
            "shop",
            "mall",
            "center",
            "park",
        ]
        has_concept_keyword = any(keyword in text for keyword in concept_keywords)

        # 6. 检查是否是功能拆解图/流程图
        # 特征：包含多个"功能名称 + 说明"的组合，如"Sale 整车销售"
        function_keywords = [
            "功能",
            "拆解",
            "流程",
            "步骤",
            "环节",
            "服务",
            "销售",
            "供应",
            "反馈",
            "装配",
            "打磨",
            "机器人",
            "机械臂",
            "设备",
            "产品",
            "材料",
            "复合",
            "表面",
            "提供",
            "应用",
            "技术",
            "系列",
            "Sale",
            "Service",
            "Supply",
            "Survey",
        ]
        has_function_keyword = any(keyword in text for keyword in function_keywords)

        # 检查是否有"英文单词 + 中文解释"的模式（如"Sale 整车销售"）
        has_word_explanation_pattern = bool(
            re.search(r"[A-Z][a-z]+\s*[\u4e00-\u9fa5]{2,6}", text)
        )

        # 7. 检查是否是实物照片的标题
        # 特征：以"图XX："开头，后面是简短描述，无数据
        is_photo_title = bool(re.match(r"^图\d+[:：]", text))

        # 8. 检查文字密度（示意图通常文字很少，分散在图片各处）
        # 如果文字很少但分散成多个短词，可能是标签图
        words = text.split()
        avg_word_length = len(text) / max(len(words), 1)
        is_sparse_text = len(words) > 2 and avg_word_length < 5

        # 综合判断（严格模式）
        is_valid = False
        reason = ""

        if self.strict_mode:
            # 严格模式：必须明确是数据图表才保留
            # 1. 必须有足够的数字
            if number_count < self.min_number_count:
                reason = f"数字不足({number_count}个，需要≥{self.min_number_count})"
            # 2. 排除所有装饰性/示意性图片
            elif is_decorative:
                reason = "装饰性图片/标签图"
            elif is_photo_title:
                reason = "实物照片标题（非数据图表）"
            elif has_word_explanation_pattern:
                reason = "功能说明图/概念图"
            elif has_function_keyword:
                reason = "流程图/功能图"
            elif has_concept_keyword:
                reason = "示意图/场景图"
            elif is_sparse_text:
                reason = "标签图（文字分散）"
            # 3. 必须有数据关键词或足够多的数字
            elif not has_data_keyword and number_count < self.min_number_count * 1.5:
                reason = f"无数据关键词且数字较少({number_count}个)"
            else:
                is_valid = True
                reason = "有效数据图表"
        else:
            # 宽松模式：只过滤明显无效的图片
            if is_decorative:
                reason = "装饰性图片/标签图"
            elif is_photo_title and number_count < 2:
                reason = "实物照片（无数据）"
            elif has_word_explanation_pattern and number_count < 3:
                reason = "功能拆解图/概念图"
            elif has_function_keyword and has_word_explanation_pattern:
                reason = "流程图/功能说明图"
            elif has_concept_keyword and number_count < 2:
                reason = "示意图/概念图（无数据）"
            elif is_sparse_text and number_count < 2:
                reason = "标签图（文字分散且无数据）"
            elif number_count < self.min_number_count and not has_data_keyword:
                reason = f"数字太少({number_count}个)且无数据关键词"
            else:
                is_valid = True
                reason = "有效数据图表"

        return {
            "is_valid": is_valid,
            "reason": reason,
            "text_length": text_length,
            "number_count": number_count,
            "has_data_keyword": has_data_keyword,
            "has_concept_keyword": has_concept_keyword,
            "has_function_keyword": has_function_keyword,
            "is_decorative": is_decorative,
            "is_sparse_text": is_sparse_text,
            "is_photo_title": is_photo_title,
        }
    
    def filter_charts(self, charts: list) -> Tuple[list, list]:
        """
        过滤图表列表，移除空白或无效图片
        
        Args:
            charts: 图表列表（每个元素包含 image_data 字段）
        
        Returns:
            (有效图表列表, 被过滤的图表列表)
        """
        if self.ocr is None:
            print("   ℹ️  OCR 未启用，跳过图片过滤")
            return charts, []
        
        valid_charts = []
        filtered_charts = []
        
        print(f"\n🔍 开始 OCR 过滤图片...")
        
        for idx, chart in enumerate(charts, 1):
            filename = chart.get('filename', f'chart_{idx}')
            has_content, detected_text, analysis = self.has_content(chart['image_data'])
            
            if has_content:
                valid_charts.append(chart)
                text_preview = detected_text[:30] + '...' if len(detected_text) > 30 else detected_text
                print(f"  ✓ [{idx}] {filename} - {analysis.get('reason', '有效')} (文字: {text_preview})")
            else:
                filtered_charts.append(chart)
                reason = analysis.get('reason', '未知')
                print(f"  ✗ [{idx}] {filename} - {reason} (已过滤)")
        
        print(f"\n📊 过滤结果:")
        print(f"   有效图片: {len(valid_charts)}")
        print(f"   过滤图片: {len(filtered_charts)}")
        
        return valid_charts, filtered_charts
