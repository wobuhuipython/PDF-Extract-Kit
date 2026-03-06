# OSS 集成功能总结

## 核心功能

### 1. 从 OSS 下载 PDF 进行处理
- 支持 `oss://` 前缀指定 OSS 文件
- 自动下载到本地临时目录
- 处理完成后自动清理本地临时文件
- **OSS 源文件始终保留，不会被删除**

### 2. 智能去重机制
- 处理前检查 NocoDB 数据库
- 如果文件已处理，直接跳过，不下载
- 节省带宽和处理时间

### 3. 并发安全
- 多个进程同时运行时自动协调
- 通过数据库检查避免重复处理
- 适合多端口并行处理场景

## 快速开始

```bash
# 处理单个 OSS 文件
python main.py --pdf oss://public/reports/file.pdf

# 批量处理 OSS 文件夹
python main.py --oss-folder public/reports/

# 查看处理状态
python batch_oss_monitor.py public/reports/
```

## 文件清理说明

| 文件类型 | 位置 | 处理方式 |
|---------|------|---------|
| PDF 源文件 | OSS | ✅ 永久保留 |
| 临时 PDF | 本地临时目录 | 🗑️ 自动删除 |
| 提取的图表 | OSS | ✅ 永久保存 |
| 分析记录 | NocoDB | ✅ 永久保存 |

## 工作流程

```
1. 检查数据库 → 2. 下载 PDF → 3. 提取图表 → 4. AI 分析 
   ↓                                              ↓
   已处理？跳过                              上传结果到 OSS/NocoDB
                                                  ↓
                                            清理本地临时 PDF
                                                  ↓
                                            OSS 源文件保留
```

## 并发处理示例

```bash
# 3 个进程同时处理同一个文件夹
python main.py --oss-folder public/reports/  # 进程 1
python main.py --oss-folder public/reports/  # 进程 2
python main.py --oss-folder public/reports/  # 进程 3

# 结果：每个文件只会被处理一次，其他进程自动跳过
```

## 详细文档

- `OSS_USAGE.md` - 完整使用说明
- `PROMPT_OPTIMIZATION.md` - 提示词优化说明
- `batch_oss_monitor.py` - 处理状态监控工具
- `test_concurrent_processing.py` - 并发测试工具
