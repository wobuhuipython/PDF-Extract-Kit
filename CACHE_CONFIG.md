# 缓存目录配置说明

## 配置方法

在 `.env` 文件中设置 `OSS_CACHE_DIR` 变量来指定缓存目录：

```env
# OSS 下载缓存配置
OSS_CACHE_DIR=E:/langextract/PDF-Extract-Kit/cache
```

## 配置选项

### 选项 1: 使用系统临时目录（默认）

如果不设置或留空 `OSS_CACHE_DIR`，将使用系统临时目录：

```env
# 留空或注释掉
# OSS_CACHE_DIR=
```

**特点**：
- Windows: `C:\Users\[用户名]\AppData\Local\Temp\`
- 系统会自动管理临时文件
- 不占用项目空间

### 选项 2: 使用自定义目录

设置具体的目录路径：

```env
# Windows 路径示例
OSS_CACHE_DIR=E:/langextract/PDF-Extract-Kit/cache

# 或使用相对路径
OSS_CACHE_DIR=./cache

# 或使用绝对路径
OSS_CACHE_DIR=D:/temp/pdf_cache
```

**特点**：
- 可以自己管理缓存位置
- 方便调试和查看下载的文件
- 需要确保有足够的磁盘空间

## 缓存文件管理

### 自动清理

程序会在处理完成后自动删除缓存的 PDF 文件：

```python
# 处理流程
下载 PDF → 提取图表 → AI 分析 → 上传结果 → 删除缓存 PDF
```

### 手动清理

如果需要手动清理缓存目录：

```bash
# Windows
rmdir /s /q cache

# 或者在 Python 中
python -c "import shutil; shutil.rmtree('cache', ignore_errors=True)"
```

## 磁盘空间建议

根据你的使用场景预留足够的空间：

| 场景 | 建议空间 |
|------|---------|
| 单个文件处理 | 100 MB |
| 小批量（10-50 个文件） | 1 GB |
| 大批量（100+ 个文件） | 5 GB |
| 并发处理 | 10 GB+ |

## 配置示例

### 示例 1: 开发环境（使用项目缓存目录）

```env
OSS_CACHE_DIR=./cache
```

**优点**：方便查看和调试
**缺点**：需要手动清理

### 示例 2: 生产环境（使用系统临时目录）

```env
# OSS_CACHE_DIR=
```

**优点**：自动管理，不占用项目空间
**缺点**：不方便查看临时文件

### 示例 3: 大批量处理（使用独立磁盘）

```env
OSS_CACHE_DIR=D:/pdf_cache
```

**优点**：不影响系统盘，空间充足
**缺点**：需要确保路径存在且有权限

## 注意事项

1. **路径格式**：
   - Windows 使用 `/` 或 `\\`（推荐使用 `/`）
   - 相对路径相对于项目根目录
   - 绝对路径直接指定完整路径

2. **权限要求**：
   - 确保程序有读写权限
   - 如果目录不存在，程序会自动创建

3. **空间管理**：
   - 定期检查磁盘空间
   - 大文件处理需要预留足够空间
   - 程序会自动清理处理完的文件

4. **并发处理**：
   - 多个进程可以共享同一个缓存目录
   - 文件名使用临时文件名，不会冲突
   - 每个进程处理完会清理自己的临时文件

## 查看当前配置

运行程序时会显示缓存目录配置：

```bash
python main.py --pdf oss://test.pdf
```

输出：
```
✅ OSS 下载器初始化成功
   Bucket: web-pdf001
   缓存目录: E:/langextract/PDF-Extract-Kit/cache
```
