# Insight Radar Data

公开洞察数据仓库：卡片数据、图片、schema 和发布脚本。

## 结构

```text
data/
  cards.jsonl              全部卡片，一行一张
  manifest.json            总数、sha256、最近一次 run
  images/                  按内容哈希存放的 WebP / SVG
  schema/card.schema.json  卡片字段约束
sources.json               结构化信源表
scripts/publish_data.py    发布与图片归一化脚本
```

## 构建网站

只需要读取 `data/cards.jsonl` 和 `data/images/`：

```python
import json

cards = [json.loads(line) for line in open("data/cards.jsonl", encoding="utf-8")]
print(len(cards))
```

卡片里的 `image` 是相对 `data/` 的路径，例如 `images/ab/<sha256>.webp`。

## 更新

```bat
python scripts/publish_data.py add --source <本轮 cards.jsonl> --run-id 2026-11-08
```

图片会转 WebP，按内容哈希去重，并更新 `manifest.json`。
