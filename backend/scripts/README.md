# backend/scripts — 开发工具脚本

> 非引擎运行代码，均为开发期一次性/调试工具。引擎启动不依赖任何脚本。

## 分类

### 素材处理（一次性，服务 materials/ 源数据）
| 脚本 | 用途 | 输入 → 产出 |
|------|------|-------------|
| `parse_subtitles.py` | 解析字幕原始文件 | materials/字幕台词 → 结构化台词 |
| `extract_dialogues.py` | 从台词提取对话 | 字幕 → 对话 JSON |
| `index_subtitles.py` | 字幕索引 | 字幕 → 索引 |
| `verify_quotes.py` | 校验台词引用 | 台词 → 校验报告 |
| `generate_atmo.py` | 生成氛围图/映射 | 素材 → assets/atmo + atmo_map.json |

### 调试测试（SSE 连通性验证）
| 脚本 | 用途 |
|------|------|
| `test_sse.py` | Python SSE 流式验证（请求 /api/play/step，统计事件）|
| `test_sse_node.js` | Node 客户端 SSE 测试 |
| `test_fetch.mjs` | 浏览器同款 fetch SSE 测试（Node 18+）|

> ⚠️ 命名约定：调试脚本统一 `test_` 前缀；一次性数据脚本用动词命名。
> 临时脚本用完即删，不留 `_debug_`/无前缀裸文件。
