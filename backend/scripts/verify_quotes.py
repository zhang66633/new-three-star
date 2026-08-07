# -*- coding: utf-8 -*-
"""
验证 quotes.json 台词归属
==========================
方法：对每条台词取关键片段，在 40 章原著中全文检索。
- 找到：输出章节/页码/上下文，用就近归属信号推断实际说话人
- 找不到：标记「原著未找到」
输出: materials/script_ocr/台词/归属验证报告.md
"""
import re, json, os

BASE = 'materials/script_ocr/chapters'
QUOTES = 'backend/knowledge/quotes.json'
OUT = 'materials/script_ocr/台词/归属验证报告.md'

# 加载 40 章全文（拼接，记录每章字符偏移 → 章节/页码）
chapters = []
offset = 0
names = ["曹操献刀","诸侯聚义","三英战吕布","貂蝉除贼","三让徐州","辕门射戟","吕布命","青梅煮酒","斩颜良诛文丑","过五关斩六将","孔明出山","血战长坂坡","火烧赤壁","败走华容道","连取四郡","三气周瑜","假道灭虢","太宴铜雀台","割须去袍","议取西蜀","凤雏归西","益州易主","单刀赴会","虎女犬子","败走麦城","奸雄数终","曹丕废帝","刘备伐吴","蜀吴交兵","东吴拜将","火烧连营","白帝托孤","北伐中原","失街亭","出师表","张颌中计","仲达受辱","木牛流马","功亏一篑","天下统一"]
for i, name in enumerate(names, 1):
    fn = f'{BASE}/第{i:02d}章_{name}.txt'
    with open(fn, encoding='utf-8') as f:
        content = f.read()
    pm = re.match(r'# 第\d+章 .*?（原书页 (\d+)-(\d+)）', content)
    page_start, page_end = (int(pm.group(1)), int(pm.group(2))) if pm else (0, 0)
    # 去掉头部注释行
    body = content.split('\n\n', 1)[1] if '\n\n' in content else content
    chapters.append({
        'idx': i, 'name': name, 'body': body,
        'offset': offset, 'page_start': page_start, 'page_end': page_end,
    })
    offset += len(body)
FULL = ''.join(c['body'] for c in chapters)
# 建立偏移 → 章节映射
offsets = [c['offset'] for c in chapters] + [offset]

def locate(pos):
    """字符位置 → (章idx, 页码)"""
    import bisect
    k = bisect.bisect_right(offsets, pos) - 1
    c = chapters[k]
    ratio = (pos - c['offset']) / max(len(c['body']), 1)
    page = c['page_start'] + int(ratio * (c['page_end'] - c['page_start'] + 1))
    return c['idx'], c['name'], page

def find_speaker_near(text, pos):
    """在 pos 前 80 字符找说话人信号"""
    window = text[max(0, pos - 80):pos]
    # 找最后一个 X道/曰/问/答/笑...：模式
    pat = re.compile(r'([一-鿿·]{1,8}?)(?:哈哈|呵呵|冷笑|微微一|轻轻|沉声|低声|高声|厉声|朗声|失声|哑声|愤然|坦然|傲然|淡然|无奈|焦急|急忙|断然|沉吟|迟疑|犹豫|感慨|感叹|长叹|叹息|嘀咕|嘟囔|催促|提醒|安慰|反驳|坚持|央求|恳求|祈求|哀求|请示|回答|反问|大喝|长喝|高喝|低喝|大声|小声|轻声|颤声|放声|仰天|半晌|良久|正色|突然|忽然|连忙|赶紧|默默|静静|悄悄|转身|回头|走近|上前|站起|坐下|拱手|作揖|躬身|施礼|点头|摇头|摆手|挥手|抬头|低头|微微|不禁|得意|冷冷|笑后|晒然|欣然|惶然|黯然|戚然|骤然|莞尔|机密|谨慎|默然|恍然|凛然|肃然|恬然|怅然|帐然|凄然|惨然|泰然|释然|一怔|笑吟吟|冷然|慨然|喟然|动容|出神|失神|大|一|连|含笑|冷漠|淡淡|略一|略略|郑重|恭敬){0,3}(?:道|曰|问|答|笑|怒|叹|喝|叫|喊|说|言|讲|应|斥|嗔|嚷|云|语|呼)[：:，,。]?\s*[“「]?')
    matches = list(pat.finditer(window))
    if not matches:
        return ''
    last = matches[-1]
    return last.group(1).strip()

def main():
    with open(QUOTES, encoding='utf-8') as f:
        quotes = json.load(f)
    by_char = quotes['by_character']
    by_scene = quotes.get('by_scene', {})

    report = []
    report.append('# 台词归属验证报告\n')
    report.append('> 验证方法：每条台词取关键片段在《三国》原著（朱苏进）40 章中全文检索\n')
    report.append('> 验证时间: 2026-08-07\n')
    report.append('> ✅=找到且说话人匹配 | ⚠️=找到但说话人存疑 | ❌=原著未找到\n')

    stats = {'ok': 0, 'warn': 0, 'miss': 0, 'total': 0}
    miss_list = []

    for char, qs in by_char.items():
        report.append(f'\n## {char}（{len(qs)}条）\n')
        for q in qs:
            stats['total'] += 1
            q_clean = q.strip()
            if not q_clean:
                continue
            # 取关键片段：去标点后取 8-12 字（唯一性）
            key = re.sub(r'[，。！？、；：“”「」（）·…\s]', '', q_clean)
            frag = key[:10]
            # 检索
            pos = FULL.find(frag)
            if pos == -1:
                # 尝试后片段
                frag = key[-10:]
                pos = FULL.find(frag)
            if pos == -1:
                stats['miss'] += 1
                miss_list.append((char, q_clean))
                report.append(f'- ❌ **{char}**: {q_clean}\n')
                continue
            idx, name, page = locate(pos)
            # 取上下文（台词前后各 60 字）
            ctx_before = FULL[max(0, pos-60):pos].replace('\n', ' ')
            ctx_after = FULL[pos:pos+len(q_clean)+40].replace('\n', ' ')
            # 就近说话人
            sp = find_speaker_near(FULL, pos)
            status = '✅' if sp == char else '⚠️'
            if sp == char:
                stats['ok'] += 1
            else:
                stats['warn'] += 1
            report.append(f'- {status} **{char}**: {q_clean}\n')
            report.append(f'  - 出处: 第{idx}章《{name}》原书页{page} | 就近说话人信号: `{sp or "（无信号）"}`\n')
            report.append(f'  - 上下文: …{ctx_before}⟪{ctx_after}…\n')

    # 未分类"其他"也验证
    others = by_char.get('其他', [])
    if others:
        report.append(f'\n## 其他（未分类 {len(others)}条）\n')
        for q in others:
            stats['total'] += 1
            q_clean = q.strip()
            key = re.sub(r'[，。！？、；：“”「」（）·…\s]', '', q_clean)
            frag = key[:10]
            pos = FULL.find(frag)
            if pos == -1:
                frag = key[-10:]
                pos = FULL.find(frag)
            if pos == -1:
                stats['miss'] += 1
                miss_list.append(('其他', q_clean))
                report.append(f'- ❌ **其他**: {q_clean}\n')
                continue
            idx, name, page = locate(pos)
            sp = find_speaker_near(FULL, pos)
            report.append(f'- ⚠️ **其他**: {q_clean}\n')
            report.append(f'  - 出处: 第{idx}章《{name}》原书页{page} | 就近说话人信号: `{sp or "（无信号）"}`\n')

    report.append(f'\n## 汇总\n')
    report.append(f'- 总计: {stats["total"]} 条\n')
    report.append(f'- ✅ 匹配: {stats["ok"]}\n')
    report.append(f'- ⚠️ 存疑: {stats["warn"]}\n')
    report.append(f'- ❌ 未找到: {stats["miss"]}\n')
    if miss_list:
        report.append(f'\n### 未找到清单\n')
        for char, q in miss_list:
            report.append(f'- [{char}] {q}\n')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(''.join(report))
    print(f'报告已写入 {OUT}')
    print(f'总计 {stats["total"]} | ✅ {stats["ok"]} | ⚠️ {stats["warn"]} | ❌ {stats["miss"]}')


if __name__ == '__main__':
    main()
