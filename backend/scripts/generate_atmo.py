# -*- coding: utf-8 -*-
"""
Seedream-4.5 水墨抽象氛围图批量生成
====================================
调用火山引擎 ARK API，生成 12 张三国叙事水墨抽象背景。
存至 frontend/src/assets/atmo/ 目录。

用法：python backend/scripts/generate_atmo.py
"""

import json
import os
import sys
import time
import requests

# ── 配置 ──
# 密钥从环境变量读取（勿硬编码提交）：ARK_API_KEY 由火山引擎控制台签发
API_KEY = os.environ.get("ARK_API_KEY", "")
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
MODEL = "doubao-seedream-4-5-251128"
SIZE = "2560x1440"  # ARK Seedream 最小 3686400px (2560x1440=3686400)


if not API_KEY:
    raise SystemExit(
        "未设置 ARK_API_KEY 环境变量。请先在火山引擎控制台创建密钥，"
        "然后以 ARK_API_KEY=xxx python backend/scripts/generate_atmo.py 运行。"
    )

# 输出目录（脚本在 backend/scripts/，资源目录在 frontend/src/assets/atmo/）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)  # backend/
OUTPUT_DIR = os.path.join(os.path.dirname(PROJECT_DIR), "frontend", "src", "assets", "atmo")

# ── 12 张氛围图定义 ──
ATMOS = [
    {
        "id": "rain_night",
        "label": "雨夜沉静",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "冷蓝紫色调，深蓝灰底色上晕染着淡淡的紫色和靛蓝墨痕，"
            "像夜色中细雨落在宣纸上的痕迹。"
            "笔触柔和，大面积留白，墨色由深到浅自然过渡。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
    {
        "id": "wilderness",
        "label": "荒野苍茫",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "暗褐金色调，深棕色底上晕染着赭石和黄褐色墨痕，"
            "像风化的黄土高原，苍茫荒凉。"
            "笔触干枯有力，飞白效果，墨色浓淡相间。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
    {
        "id": "war_fire",
        "label": "战火远方",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "暗红铜色调，深黑色底上晕染着暗红和赭色墨痕，"
            "像远处战火映红的夜空，焦土般的纹理。"
            "笔触粗犷有力，墨色浓重，下部暗上部略有暗红微光。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
    {
        "id": "luoyang_alley",
        "label": "洛阳暗巷",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "深靛青色调，极深的蓝黑底上晕染着靛蓝和墨青色墨痕，"
            "像月夜下狭窄巷道里的阴影，沉稳而神秘。"
            "笔触细腻紧致，墨色层次丰富，有纵深感。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
    {
        "id": "ink_mountains",
        "label": "水墨山岚",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "墨绿灰色调，深灰绿底上晕染着淡淡的水绿色和灰白色墨痕，"
            "像远山在晨雾中若隐若现，云雾缭绕。"
            "笔触柔和疏散，大面积淡墨晕染，留白多。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
    {
        "id": "dawn_march",
        "label": "破晓行军",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "淡金灰色调，深灰底色上晕染着淡金色和暖灰色墨痕，"
            "像黎明时分天色将亮未亮，地平线微光初现。"
            "笔触柔和，上部淡金微光，下部深灰沉稳，渐变自然。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
    {
        "id": "bamboo_grove",
        "label": "竹林清幽",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "青玉色调，深绿底上晕染着青绿和淡翠色墨痕，"
            "像阳光透过竹林洒下的斑驳光影，清幽宁静。"
            "笔触清瘦挺拔，竖向笔势为主，墨色青翠欲滴。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
    {
        "id": "yellow_river",
        "label": "黄河怒涛",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "泥金琥珀色调，深褐色底上晕染着琥珀色和暗金色墨痕，"
            "像黄河浊浪翻滚，泥沙俱下，气势磅礴。"
            "笔触粗犷奔放，横向笔势为主，墨色浓烈厚重。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
    {
        "id": "tent_warmth",
        "label": "帐中暖光",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "暖琥珀色调，深棕底上晕染着暖橙色和琥珀色墨痕，"
            "像帐中篝火的暖光映在粗布帐幕上，温暖而有限。"
            "笔触柔和，中央偏暖色光晕，四周深暗，明暗对比温和。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
    {
        "id": "snow_city",
        "label": "雪夜孤城",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "苍白蓝色调，极淡的蓝灰底上晕染着白色和淡蓝色墨痕，"
            "像大雪覆盖一切后的寂静，天地一色。"
            "笔触极淡极疏，大面积留白，墨色清淡如烟。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
    {
        "id": "starry_plains",
        "label": "星空原野",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "深藏青色调，极深的蓝黑底上点缀着极淡的银色和白色微点墨痕，"
            "像深夜原野上空浩瀚的银河，深邃无垠。"
            "笔触极疏，上部有极淡的银白散点，下部纯黑，对比强烈。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
    {
        "id": "blood_sunset",
        "label": "血色残阳",
        "prompt": (
            "中国传统水墨画风格，抽象纹理，无具体形象。"
            "赤金色调，深黑底上晕染着赤红和暗金色墨痕，"
            "像战场上的残阳如血，余晖染红天际。"
            "笔触浓烈，上部赤红渐变到下部纯黑，视觉冲击力强但不刺目。"
            "高级感，极简，适合做游戏背景。"
            "画面干净，不要文字，不要人物，不要建筑。"
        ),
    },
]


def generate_image(prompt: str, output_path: str) -> bool:
    """调用 Seedream-4.5 生成单张图，下载保存"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "size": SIZE,
        "n": 1,
        "response_format": "url",
    }

    print(f"  generating...", end=" ", flush=True)

    try:
        resp = requests.post(
            f"{BASE_URL}/images/generations",
            headers=headers,
            json=payload,
            timeout=120,
        )
    except requests.RequestException as e:
        print(f"request failed: {e}")
        return False

    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return False

    data = resp.json()
    image_url = None
    if "data" in data and len(data["data"]) > 0:
        image_url = data["data"][0].get("url")

    if not image_url:
        print(f"no image url in response")
        return False

    print(f"downloading...", end=" ", flush=True)
    try:
        img_resp = requests.get(image_url, timeout=60)
        if img_resp.status_code != 200:
            print(f"download HTTP {img_resp.status_code}")
            return False
    except requests.RequestException as e:
        print(f"download error: {e}")
        return False

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(img_resp.content)

    file_size_kb = len(img_resp.content) / 1024
    print(f"OK ({file_size_kb:.0f}KB)")
    return True


def main():
    print("=" * 60)
    print("水墨抽象氛围图批量生成 (Seedream-4.5)")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"共计: {len(ATMOS)} 张")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 生成 atmo_map.json
    atmo_map = {}

    success = 0
    for i, atmo in enumerate(ATMOS, 1):
        print(f"\n[{i}/{len(ATMOS)}] {atmo['label']} ({atmo['id']})")
        output_path = os.path.join(OUTPUT_DIR, f"{atmo['id']}.png")

        if os.path.exists(output_path):
            print(f"  已存在，跳过")
            atmo_map[atmo["label"]] = atmo["id"]
            success += 1
            continue

        ok = generate_image(atmo["prompt"], output_path)
        if ok:
            atmo_map[atmo["label"]] = atmo["id"]
            success += 1
        else:
            print(f"  FAIL")

        # 避免请求过快
        if i < len(ATMOS):
            time.sleep(1)

    # 写 atmo_map.json
    map_path = os.path.join(OUTPUT_DIR, "atmo_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(atmo_map, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"完成: {success}/{len(ATMOS)} 张生成成功")
    print(f"索引: {map_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
