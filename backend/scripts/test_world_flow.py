# -*- coding: utf-8 -*-
"""
自由大世界全链路回归冒烟（Step 7）
====================================
验证重构后引擎不崩 + 8 PHASE 不破坏 + 世界推进/角色档案/暗线/存档完整。
会话：开局 → 观察 → 休息跳时 → 赴洛阳 → 触发暗线 → 存档往返。

运行：cd backend && python scripts/test_world_flow.py
"""
import asyncio
import sys

sys.path.insert(0, ".")


async def main():
    from engine.graph import run_step
    from engine.state import from_dict, to_dict

    ok = []
    def check(name, cond, extra=""):
        ok.append((name, cond))
        print(f"  {'✓' if cond else '✗'} {name}{(' | ' + extra) if extra else ''}")

    # ── 1. 开局 ──
    print("=== 开局 ===")
    r = await run_step({}, "", 0)
    ps = (r.get("meta") or {}).get("plan_summary") or {}
    last = r.get("last_output") or {}
    check("scene_id=颍川（自由区，非骨架场景）", ps.get("scene_id") == "颍川", ps.get("scene_id"))
    check("chapter=P1 黄金风起", (r.get("era") or {}).get("chapter") == "P1 黄金风起")
    check("world_date=184-02", r.get("world_date", {}).get("month") == 2)
    check("有叙事", bool(last.get("narrative")))
    check("8 PHASE 通过", last.get("validated") is True)
    check("无信息泄漏", (last.get("phase_report") or {}).get("leak", {}).get("pass") is not False)

    # ── 2. 观察（互动）──
    print("=== 观察互动 ===")
    r2 = await run_step(r, "观察四周，看看颍川正在发生什么", 0)
    check("观察后 alive", (r2.get("player") or {}).get("alive") is True)
    check("观察有叙事", bool((r2.get("last_output") or {}).get("narrative")))

    # ── 3. 休息跳时（自然流逝）──
    print("=== 休息跳时 ===")
    gs3 = from_dict(r2)
    gs3["world_date"] = {"year": 184, "month": 9, "day": 1}
    gs3["era"]["year"] = 184
    r3 = await run_step(to_dict(gs3), "休息 30 天", 0)
    wd3 = r3.get("world_date") or {}
    check("跳时到 189（自然流逝）", wd3.get("year") == 189, f"{wd3.get('year')}-{wd3.get('month')}")
    check("阶段切 P2 洛阳暗夜", (r3.get("era") or {}).get("chapter") == "P2 洛阳暗夜")
    tl = [e for e in r3.get("world_events", []) if e.get("source") == "timeline"]
    check("时间线事件入队", len(tl) > 0, f"{len(tl)} 条")

    # ── 4. 赴洛阳（自主进 P2 + 在场亲历）──
    print("=== 赴洛阳 ===")
    r4 = await run_step(r3, "前往洛阳", 0)
    check("到达洛阳", (r4.get("player") or {}).get("location") == "洛阳")
    # 董卓进京已入 world_events（跳时到 189-08 时玩家在颍川 → weak 小报得知，符合"不在场小报"设计）
    check("董卓进京入队", any(e.get("event_id") == "e_189_08_dongzhuo_jinjing"
                              for e in r4.get("world_events", [])))
    # 玩家在洛阳 → 角色档案登记（在场亲历的董卓进京事件角色；因事件已 weak 记录，此处验证角色档案非空）
    cs4 = r4.get("character_states") or {}
    check("角色档案非空", len(cs4) > 0, str(list(cs4.keys())[:4]))

    # ── 5. 触发暗线（自由行动）──
    print("=== 触发暗线 ===")
    r5 = await run_step(r4, "我混进黄金军营地，打听信物的事", 0)
    flags5 = r5.get("flags") or []
    check("暗线_黄金 flag", "暗线_黄金" in flags5, str(flags5))
    # 信物资产可能在引擎（check_darkline_grants）或 LLM（state_updates.assets_add）任一添加；
    # flag 触发即证明暗线自由化生效（信物是否进 assets 由叙事/引擎具体结算，此处不强断言具体物品）
    has_asset_trace = any("信物" in str(a) for a in (r5.get("player") or {}).get("assets", [])) \
        or any("信物" in str(f) for f in (r5.get("foreshadowing") or []))
    check("暗线收益留痕（信物/伏笔）", has_asset_trace, str((r5.get("player") or {}).get("assets")))

    # ── 6. 存档往返 ──
    print("=== 存档往返 ===")
    d = to_dict(from_dict(r5))
    check("world_date 往返", d.get("world_date") == r5.get("world_date"))
    check("character_states 往返", d.get("character_states") == r5.get("character_states"))
    check("world_events 往返", len(d.get("world_events", [])) == len(r5.get("world_events", [])))

    # ── 7. 名场面自由参与（Step D：view_scene 接线 registry）──
    # 事件到点 + 玩家在场 → 锁定台词进 plan_summary（字幕锚定），见证者 flag 落 state.flags。
    print("=== 名场面自由参与 ===")
    # 7a. 洛阳 189-09 撞刺董（P2_s2_ci）
    g7 = from_dict(r5)
    g7["player"]["location"] = "洛阳"
    g7["era"]["location"] = "洛阳"
    g7["world_date"] = {"year": 189, "month": 9, "day": 1}
    g7["era"]["year"] = 189
    r6 = await run_step(to_dict(g7), "站在洛阳城门街口，看这场乱子", 0)
    ps6 = (r6.get("meta") or {}).get("plan_summary") or {}
    ll6 = [l.get("text", "") for l in ps6.get("locked_lines", [])]
    check("洛阳 189-09 名场面锁定台词（曹孟德）",
          any("曹孟德" in t for t in ll6), str(ll6[:1]))
    check("刺董见证者 flag", "见证者_刺董败露" in (r6.get("flags") or []),
          str(r6.get("flags")))
    # 7b. 陈留 190-02 撞三英（P3_s3_three，同月温酒/三英双事件取时间线靠后者）
    g8 = from_dict(r6)
    g8["player"]["location"] = "陈留"
    g8["era"]["location"] = "陈留"
    g8["world_date"] = {"year": 190, "month": 2, "day": 1}
    g8["era"]["year"] = 190
    r7 = await run_step(to_dict(g8), "挤到联军大营前，看这场热闹", 0)
    ps7 = (r7.get("meta") or {}).get("plan_summary") or {}
    ll7 = [l.get("text", "") for l in ps7.get("locked_lines", [])]
    check("陈留 190-02 名场面锁定台词（三姓家奴）",
          any("三姓家奴" in t for t in ll7), str(ll7[:1]))
    check("三英见证者 flag", "见证者_三英战吕布" in (r7.get("flags") or []),
          str(r7.get("flags")))
    # 7c. 事件已过 → 不再注入（世界面板回落到过程化合成）
    g9 = from_dict(r7)
    g9["world_date"] = {"year": 190, "month": 6, "day": 1}
    g9["era"]["year"] = 190
    r8 = await run_step(to_dict(g9), "在洛阳城里转转", 0)
    ps8 = (r8.get("meta") or {}).get("plan_summary") or {}
    check("事件已过不再注入名场面", not ps8.get("locked_lines"),
          str([l.get("text", "")[:16] for l in ps8.get("locked_lines", [])]))

    # ── 8. P4 名场面（Step P4：长安 192 凤仪亭/李傕郭汜）──
    print("=== P4 名场面自由参与 ===")
    # 8a. 长安 192-04 撞凤仪亭（P4_s1_fengyiting）
    g10 = from_dict(r8)
    g10["player"]["location"] = "长安"
    g10["era"]["location"] = "长安"
    g10["world_date"] = {"year": 192, "month": 4, "day": 1}
    g10["era"]["year"] = 192
    r9 = await run_step(to_dict(g10), "站在长安街口，看这场争貂蝉的热闹", 0)
    ps9 = (r9.get("meta") or {}).get("plan_summary") or {}
    ll9 = [l.get("text", "") for l in ps9.get("locked_lines", [])]
    check("长安 192-04 名场面锁定台词（咱家的爱姬）",
          any("咱家的爱姬" in t for t in ll9), str(ll9[:1]))
    check("董卓伏诛见证者 flag", "见证者_董卓伏诛" in (r9.get("flags") or []),
          str(r9.get("flags")))
    # 8b. 长安 192-06 撞李傕郭汜（P4_s2_lijueguosi）
    g11 = from_dict(r9)
    g11["world_date"] = {"year": 192, "month": 6, "day": 1}
    g11["era"]["year"] = 192
    r10 = await run_step(to_dict(g11), "挤上长安城头，看这场围城大戏", 0)
    ps10 = (r10.get("meta") or {}).get("plan_summary") or {}
    ll10 = [l.get("text", "") for l in ps10.get("locked_lines", [])]
    check("长安 192-06 名场面锁定台词（住手）",
          any("住手" in t for t in ll10), str(ll10[:1]))
    check("李傕郭汜见证者 flag", "见证者_李傕郭汜乱长安" in (r10.get("flags") or []),
          str(r10.get("flags")))
    # 8c. 董卓退场：长安 192-06 会话后董卓档案 alive=False（dies_on=192-04 生效）
    dz = (r10.get("character_states") or {}).get("董卓")
    check("董卓退场 alive=False", dz is None or dz.get("alive") is False,
          str(dz.get("alive") if dz else "未登记"))

    # ── 汇总 ──
    fails = [n for n, c in ok if not c]
    print(f"\n结果: {len(ok) - len(fails)}/{len(ok)} 通过")
    if fails:
        print("失败项:", fails)
        sys.exit(1)
    print("SMOKE OK")


if __name__ == "__main__":
    asyncio.run(main())
