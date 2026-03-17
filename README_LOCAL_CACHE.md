# PDF Extract Kit - 本地缓存模式

## 功能说明

`main_local_cache.py` 是一个修改版本，具有以下特点：

- ✅ 图片保存到本地文件夹（不上传到 OSS）
- ✅ 数据仍然上传到 NocoDB 数据库
- ✅ 生成 JSON 格式的分析结果文件
- ✅ 支持单文件和批量处理

## 使用方法

### 1. 处理单个 PDF

```bash
python main_local_cache.py --pdf "path/to/your.pdf"
```

### 2. 批量处理文件夹

```bash
python main_local_cache.py --folder "path/to/pdf/folder"
```

### 3. 自定义缓存目录

```bash
python main_local_cache.py --pdf "your.pdf" --cache-dir "my_images"
```

### 4. 不递归子文件夹

```bash
python main_local_cache.py --folder "pdf_folder" --no-recursive
```

## 输出结构

```
pdf_cache/                          # 默认缓存目录
├── PDF文件名1/                     # 每个 PDF 独立文件夹
│   ├── page_1_chart_1.png         # 图片文件
│   ├── page_2_chart_2.png
│   ├── page_3_chart_3.png
│   └── analysis_result.json       # 分析结果（JSON 格式）
└── PDF文件名2/
    ├── page_1_chart_1.png
    └── analysis_result.json
```

## 分析结果 JSON 格式

`analysis_result.json` 包含以下信息：

```json
{
  "pdf_name": "示例.pdf",
  "pdf_industry": "金融",
  "analysis_time": "20240316_143022",
  "total_charts": 3,
  "charts": [
    {
      "source_file": "示例.pdf",
      "page_num": 1,
      "image_index": 1,
      "chart_title": "图表标题",
      "analysis": "详细分析内容...",
      "chart_industry": "金融",
      "content_category": "趋势分析",
      "keywords": "关键词1, 关键词2",
      "local_cache_path": "pdf_cache/示例/page_1_chart_1.png",
      "image_width": 800,
      "image_height": 600
    }
  ]
}
```

## 与原版 main.py 的区别

| 功能 | main.py | main_local_cache.py |
|------|---------|---------------------|
| 图片上传到 OSS | ✅ | ❌ |
| 图片保存到本地 | ❌ | ✅ |
| 数据上传到 NocoDB | ✅ | ✅ |
| 生成 JSON 结果 | ❌ | ✅ |
| 支持 OSS 下载 | ✅ | ❌ |

## 注意事项

1. 确保 `.env` 文件中配置了 NocoDB 相关参数
2. 本地缓存目录会自动创建
3. 图片文件名格式：`page_{页码}_chart_{索引}.png`
4. 不支持从 OSS 下载 PDF（仅支持本地文件）
