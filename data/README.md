# 公开洞察数据

这个目录是可以直接上传 GitHub、给别人建站使用的公开数据。

## 结构

```text
data/
  manifest.json
  cards.jsonl
  images/
    ab/<sha256>.webp
  schema/card.schema.json
```

- `cards.jsonl`：全部卡片，一行一张，按 `id` 稳定排序。
- `manifest.json`：总数、文件 sha256、最近一次 run。
- `images/`：按内容哈希命名的图片。
- `schema/card.schema.json`：卡片字段约束。

## 读取示例

```python
import json

cards = {}
for line in open("data/cards.jsonl", encoding="utf-8"):
    card = json.loads(line)
    cards[card["id"]] = card

print(len(cards))
```

## 发布

```bat
python scripts/publish_data.py add --source <本轮 gallery.json 或 cards.jsonl> --run-id 2026-11-08
```

图片会自动转 WebP（SVG 保留），按内容哈希去重；`manifest.json` 会自动更新。
