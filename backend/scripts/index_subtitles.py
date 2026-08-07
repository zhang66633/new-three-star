# -*- coding: utf-8 -*-
"""
Phase 0b: 折棒字幕索引建立
==========================
输入: materials/电视剧吐槽/*.txt（285 期）
输出: materials/字幕台词/INDEX.md + INDEX.json

索引内容：期号 / 标题（梗点）/ 日期 / 剧情定位（"上回说到"回顾段 + 前10行）/
        核心梗关键词 / 文件路径
"""
import re
import os
import json

SUBTITLE_DIR = 'materials/电视剧吐槽'
OUT_DIR = 'materials/字幕台词'

# 文件名: 【吃蛋挞的折棒】—三国杀up锐评新三国{num}：{title}—【{date}】-中文.txt
# 注意标题中可能含"—"（如"十常侍之首了？—【"），用 "?—【" 做分隔
FILE_PAT = re.compile(
    r'锐评新三国(?P<num>re\d+|\d+)?[：:](?P<title>.*?)[—]?——?【(?P<date>\d{4}-\d{2}-\d{2})】'
)


def extract_recap(lines: list[str]) -> str:
    """从"上回说到"提取剧情定位；无则取前 8 行摘要"""
    for i, l in enumerate(lines):
        if '上回说到' in l or '上期' in l and '回顾' in l:
            seg = ' '.join(lines[i:i+8])
            return seg[:120]
    return ' '.join(lines[3:11])[:120]  # 跳过片头曲错字


def extract_keywords(lines: list[str]) -> list[str]:
    """提取核心梗关键词：标题 + 高频人名/概念"""
    text = ' '.join(lines)
    names = ['曹操', '刘备', '关羽', '张飞', '诸葛亮', '司马懿', '吕布', '董卓', '袁绍',
             '袁术', '孙权', '周瑜', '陈宫', '王允', '貂蝉', '赵云', '马超', '黄忠', '魏延',
             '庞统', '姜维', '鲁肃', '吕蒙', '陆逊', '张角', '华雄', '颜良', '文丑',
             '邢道荣', '许攸', '蔡瑁', '蒋干', '徐庶', '法正', '孙坚', '孙策',
             '黄巾', '天意', '星夜', '传送门', '骄兵', '酒', '蛐蛐', '盖饭', '关羽之歌',
             '七星刀', '赤兔', '四轮', '叉出去', '奏乐', '三姓家奴', '馒头', '厕所']
    found = [n for n in names if n in text]
    return found[:10]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    entries = []
    for fn in sorted(os.listdir(SUBTITLE_DIR)):
        if not fn.endswith('.txt'):
            continue
        path = os.path.join(SUBTITLE_DIR, fn)
        with open(path, encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]
        m = FILE_PAT.search(fn)
        num = m.group('num') if m else '?'
        title = m.group('title').strip() if m else fn[:40]
        date = m.group('date') if m else ''
        recap = extract_recap(lines)
        kws = extract_keywords(lines)
        entries.append({
            'episode': num, 'title': title, 'date': date,
            'recap': recap, 'keywords': kws, 'lines': len(lines), 'file': fn,
        })

    # 期号排序（数字在前，re 番外在后）
    def sort_key(e):
        m = re.match(r'(\d+)', str(e['episode']))
        return (0, int(m.group(1))) if m else (1, str(e['episode']))
    entries.sort(key=sort_key)

    with open(os.path.join(OUT_DIR, 'INDEX.json'), 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)

    with open(os.path.join(OUT_DIR, 'INDEX.md'), 'w', encoding='utf-8') as f:
        f.write('# 折棒锐评新三国 · 字幕索引\n\n')
        f.write(f'> 共 {len(entries)} 期 | 生成 2026-08-07\n\n')
        f.write('| 期 | 日期 | 标题（梗点） | 剧情定位 | 关键词 |\n')
        f.write('|---|------|------------|---------|--------|\n')
        for e in entries:
            kw = '、'.join(e['keywords'][:5]) or '-'
            recap = e['recap'].replace('|', '／')[:60]
            f.write(f"| {e['episode']} | {e['date']} | {e['title'][:28]} | {recap} | {kw} |\n")

    print(f'完成: {len(entries)} 期 → {OUT_DIR}/INDEX.md + INDEX.json')


if __name__ == '__main__':
    main()
