#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公开数据层：把卡片写进 data/cards.jsonl，图片按内容哈希落盘。

用法：
  python scripts/publish_data.py migrate
  python scripts/publish_data.py add --source <gallery.json> --run-id 2026-11-08
  python scripts/publish_data.py add --source <cards.jsonl> --run-id 2026-11-08 --git
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
CARDS = os.path.join(DATA, "cards.jsonl")
IMAGES = os.path.join(DATA, "images")
MANIFEST = os.path.join(DATA, "manifest.json")
SCHEMA = os.path.join(DATA, "schema", "card.schema.json")
DB = os.path.join(BASE, "team", "team.db")
FONT = r"C:\Windows\Fonts\msyh.ttc"

CLASS = {
    "github": "A5 GitHub", "huggingface": "A5b Hugging Face",
    "arxiv": "A3 学术", "openalex": "A3 学术", "devpost": "A1 黑客松",
    "itunes": "B2 应用商店", "hn": "A2 独立开发者", "ph": "A2 独立开发者",
    "9to5mac": "B3 外媒一手", "android_authority": "B3 外媒一手",
    "gsmarena": "B3 外媒一手", "the_verge": "B3 外媒一手",
    "youtube": "C2 海外创作者",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def cover(item):
    w, h = 960, 600
    im = Image.new("RGB", (w, h), (15, 23, 42))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=(int(15 + 12 * t), int(23 + 18 * t), int(42 + 28 * t)))
    d.rectangle([60, 58, 72, 542], fill=(56, 189, 248))
    f1 = ImageFont.truetype(FONT, 24)
    f2 = ImageFont.truetype(FONT, 40)
    d.text((102, 70), "洞察雷达 · 卡片封面", font=f1, fill=(148, 163, 184))
    y = 150
    for line in re.findall(r".{1,24}", clean(item.get("title")) or "未命名")[:4]:
        d.text((102, y), line, font=f2, fill=(241, 245, 249))
        y += 58
    buf = __import__("io").BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue(), ".png"


def image_bytes(item):
    old = item.get("image") or ""
    path = os.path.join(BASE, "insights", old.replace("/", os.sep)) if old else ""
    if path and os.path.exists(path):
        raw = open(path, "rb").read()
        ext = os.path.splitext(path)[1].lower()
        if ext == ".svg":
            return raw, ".svg"
        try:
            im = Image.open(path)
            im.seek(0)
            im = im.convert("RGBA" if "A" in im.mode else "RGB")
            im.thumbnail((800, 800))
            buf = __import__("io").BytesIO()
            im.save(buf, format="WEBP", quality=82, method=6)
            return buf.getvalue(), ".webp"
        except Exception:
            pass
    return cover(item)


def normalize(item):
    c = dict(item)
    raw, ext = image_bytes(c)
    h = sha(raw)
    folder = os.path.join(IMAGES, h[:2])
    os.makedirs(folder, exist_ok=True)
    name = h + ext
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        open(path, "wb").write(raw)
    c["image"] = f"images/{h[:2]}/{name}"
    c["image_status"] = "screenshot"
    c["image_note"] = "公开数据 · 内容哈希图片"
    c["content_hash"] = sha(
        ((c.get("url") or "") + "\n" + (c.get("title") or "") + "\n" + (c.get("summary") or "")).encode("utf-8")
    )
    return c


def load_items(path):
    if path.endswith(".jsonl"):
        return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    obj = json.load(open(path, encoding="utf-8"))
    return obj["items"] if isinstance(obj, dict) else obj


def read_cards():
    if not os.path.exists(CARDS):
        return []
    return [json.loads(line) for line in open(CARDS, encoding="utf-8") if line.strip()]


def upsert_cards(old, new):
    by_id = {c.get("id"): c for c in old}
    url_ids = {c.get("url"): c.get("id") for c in old if c.get("url")}
    for c in new:
        if c.get("url") in url_ids:
            by_id.pop(url_ids[c["url"]], None)
        by_id[c["id"]] = c
    return list(by_id.values())


def write_cards(items, run_id=""):
    os.makedirs(DATA, exist_ok=True)
    items = sorted(items, key=lambda x: int(x.get("id", 0)))
    lines = [json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for x in items]
    body = ("\n".join(lines) + "\n").encode("utf-8")
    open(CARDS, "wb").write(body)
    manifest = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "file": "cards.jsonl",
        "total": len(items),
        "sha256": sha(body),
        "bytes": len(body),
        "last_run": run_id,
    }
    json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return manifest


def sync_db(items):
    if not os.path.exists(DB):
        print("db not found, skip sync")
        return
    conn = sqlite3.connect(DB)
    for c in items:
        d = dict(c)
        sid = (d.get("source") or {}).get("id", "")
        cls = CLASS.get(sid, "E 二手加工")
        d["source"] = {**(d.get("source") or {}), "class": cls}
        conn.execute(
            "INSERT OR REPLACE INTO cards(id,json,source_id,source_class,product_line,quality_tier) VALUES(?,?,?,?,?,?)",
            (d["id"], json.dumps(d, ensure_ascii=False), sid, cls, d.get("product_line", ""), d.get("quality_tier", "C")),
        )
    conn.commit()
    conn.close()


def maybe_git():
    if not os.path.isdir(os.path.join(BASE, ".git")):
        print("not a git repository; data written locally only")
        return
    subprocess.run(["git", "add", "data"], cwd=BASE, check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=BASE).returncode
    if diff == 0:
        print("no data changes")
        return
    subprocess.run(["git", "commit", "-m", "data: publish insight run"], cwd=BASE, check=True)
    subprocess.run(["git", "push"], cwd=BASE, check=True)


def migrate():
    legacy_runs = os.path.join(DATA, "runs")
    if os.path.isdir(legacy_runs):
        items = []
        for name in sorted(os.listdir(legacy_runs)):
            if name.endswith(".jsonl"):
                items.extend(load_items(os.path.join(legacy_runs, name)))
        shutil.rmtree(legacy_runs)
    else:
        items = [normalize(c) for c in load_items(os.path.join(BASE, "insights", "gallery.json"))]
    manifest = write_cards(items, "migrate")
    sync_db(items)
    print("cards", manifest["total"], "->", CARDS)


def add_run(source, run_id):
    new = [normalize(c) for c in load_items(source)]
    merged = upsert_cards(read_cards(), new)
    manifest = write_cards(merged, run_id)
    sync_db(merged)
    print(run_id, "added", len(new), "total", manifest["total"])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    p = sub.add_parser("add")
    p.add_argument("--source", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--git", action="store_true")
    args = ap.parse_args()
    if args.cmd == "migrate":
        migrate()
    else:
        add_run(args.source, args.run_id)
        if args.git:
            maybe_git()


if __name__ == "__main__":
    main()
