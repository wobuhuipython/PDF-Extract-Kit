# OSS 下载功能使用说明

## 功能说明

PDF-Extract-Kit 现在支持从阿里云 OSS 下载 PDF 文件进行处理，无需手动下载到本地。

**核心特性**：
- 智能去重：在下载前自动检查数据库，避免重复处理
- 并发安全：多进程同时运行时自动协调，不会重复处理同一文件
- 自动清理：处理完成后自动删除本地临时文件
- OSS 保留：OSS 上的源文件始终保留，不会被删除

## 使用方法

### 1. 处理单个 OSS 文件

使用 `oss://` 前缀指定 OSS 文件路径：

```bash
python main.py --pdf oss://path/to/your/file.pdf
```

示例：
```bash
python main.py --pdf oss://public/reports/2024/report.pdf
```

### 2. 批量处理 OSS 文件夹

使用 `--oss-folder` 参数指定 OSS 文件夹路径：

```bash
python main.py --oss-folder path/to/folder/
```

示例：
```bash
python main.py --oss-folder public/reports/2024/
```

### 3. 处理本地文件（原有功能）

本地文件处理方式保持不变：

```bash
# 单个文件
python main.py --pdf local/path/to/file.pdf

# 批量处理文件夹
python main.py --folder local/path/to/folder/
```

## 参数说明

- `--pdf`: 单个 PDF 文件路径（支持本地路径或 `oss://` 前缀的 OSS 路径）
- `--folder`: 本地文件夹路径（批量处理）
- `--oss-folder`: OSS 文件夹路径（批量处理 OSS 文件）
- `--no-skip`: 不跳过已处理的文件（默认会检查数据库并跳过）
- `--no-recursive`: 不递归子文件夹（仅对本地文件夹有效）

## 智能去重机制

### 工作原理

1. **获取处理锁**: 在开始处理前，先尝试获取该文件的处理锁
2. **下载前检查**: 查询 NocoDB 数据库，判断该 PDF 是否已处理或正在处理
3. **文件名匹配**: 根据 `source_file` 字段判断该 PDF 的状态
4. **自动跳过**: 如果数据库中已存在该文件的记录，直接跳过，不下载
5. **并发安全**: 多个进程同时运行时，只有一个进程会处理该文件
6. **节省资源**: 避免重复下载大文件，节省带宽和处理时间

### 防止并发重复处理

当多个端口同时运行时，系统会自动协调：

```bash
# 端口 1
python main.py --oss-folder public/reports/

# 端口 2（同时运行）
python main.py --oss-folder public/reports/
```

两个进程会通过数据库检查自动避免重复处理同一文件。

### 强制重新处理

如果需要重新处理已处理过的文件，使用 `--no-skip` 参数：

```bash
# 强制重新处理单个文件
python main.py --pdf oss://path/to/file.pdf --no-skip

# 强制重新处理整个文件夹
python main.py --oss-folder path/to/folder/ --no-skip
```

## 环境变量配置

确保 `.env` 文件中配置了 OSS 和 NocoDB 相关参数：

```env
# OSS 配置
OSS_ACCESS_KEY_ID=your_access_key_id
OSS_ACCESS_KEY_SECRET=your_access_key_secret
OSS_BUCKET_NAME=your_bucket_name
OSS_ENDPOINT=https://oss-cn-shenzhen.aliyuncs.com

# NocoDB 配置（用于去重检查）
NOCODB_API_URL=https://your-nocodb-url/
NOCODB_API_TOKEN=your_api_token
NOCODB_TABLE_ID=your_table_id
NOCODB_BASE_ID=your_base_id
```

## 工作流程

1. **获取处理锁**: 尝试获取文件处理锁（防止并发）
2. **检查数据库**: 查询 NocoDB 判断 PDF 是否已处理
3. **下载文件**: 如果未处理，从 OSS 下载 PDF 到本地临时目录
4. **提取分析**: 提取图表并进行 AI 分析
5. **上传结果**: 上传结果到 OSS 和 NocoDB
6. **清理临时**: 自动删除本地临时 PDF 文件
7. **保留源文件**: OSS 上的源文件始终保留

## 使用场景

### 场景 1: 多端口并行处理（推荐）

在不同端口或服务器上同时运行，自动避免重复：

```bash
# 服务器 1 - 端口 8001
python main.py --oss-folder public/reports/batch1/

# 服务器 2 - 端口 8002（同时运行）
python main.py --oss-folder public/reports/batch2/

# 服务器 3 - 端口 8003（同时运行）
python main.py --oss-folder public/reports/batch3/
```

即使不同批次有重复文件，也只会处理一次。

### 场景 2: 增量处理

定期处理新上传的 PDF，自动跳过已处理的：

```bash
# 每天运行，只处理新文件
python main.py --oss-folder public/reports/
```

### 场景 3: 断点续传

如果处理中断，重新运行会自动跳过已完成的文件：

```bash
# 重新运行，从中断处继续
python main.py --oss-folder public/reports/large-batch/
```

### 场景 4: 监控处理进度

查看哪些文件已处理，哪些待处理：

```bash
# 查看处理状态
python batch_oss_monitor.py public/reports/
```

## 文件清理说明

### 自动清理的文件

✅ **本地临时 PDF 文件**：从 OSS 下载的 PDF 会保存到系统临时目录，处理完成后自动删除

### 保留的文件

✅ **OSS 源文件**：OSS 上的 PDF 源文件始终保留，不会被删除
✅ **提取的图表**：上传到 OSS 的图表文件会永久保存
✅ **数据库记录**：NocoDB 中的分析记录会永久保存

### 清理时机

- 处理成功：立即清理本地临时文件
- 处理失败：也会清理本地临时文件
- 程序异常：finally 块确保临时文件被清理

## 注意事项

- OSS 下载的文件会自动保存到系统临时目录
- 处理完成后会自动清理本地临时文件
- OSS 上的源文件不会被删除，始终保留
- 确保有足够的磁盘空间用于临时文件
- 大文件下载可能需要较长时间
- 数据库检查需要 NocoDB 配置正确
- 如果 NocoDB 未配置，将无法进行去重检查

## 监控和调试

### 查看处理状态

```bash
# 查看 OSS 文件夹的处理状态
python batch_oss_monitor.py public/reports/
```

输出示例：
```
📊 处理状态统计
================================================================================
  总文件数: 100
  已处理: 75 (75.0%)
  待处理: 25 (25.0%)
================================================================================
```

### 日志输出

程序会输出详细的处理日志：

```
🔍 检查数据库: example.pdf
✓ 数据库中未找到该文件（可以处理）
📥 从 OSS 下载: public/reports/example.pdf
✅ 下载成功: C:\Users\...\Temp\tmp123.pdf (1,234,567 bytes)
📄 临时文件: C:\Users\...\Temp\tmp123.pdf
...
🎉 处理完成！
🗑️  已清理本地临时文件: C:\Users\...\Temp\tmp123.pdf
```
