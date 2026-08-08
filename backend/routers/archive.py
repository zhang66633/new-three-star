# -*- coding: utf-8 -*-
"""
/api/archive —— 世界观档案（静态展示页数据源）
================================================
9 个世界观档案 → 静态档案页（读 knowledge/frameworks/*.json）
"""
import json
import os
from fastapi import APIRouter, HTTPException

router = APIRouter()

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
FRAMEWORKS_DIR = os.path.join(KNOWLEDGE_DIR, "frameworks")


def _safe_framework_id(archive_id: str) -> str:
    """路径遍历防护：只允许纯文件名（无路径分隔符 / 反斜杠 / 点前缀）"""
    if not archive_id:
        raise HTTPException(400, "非法 id")
    name = os.path.basename(archive_id)
    if name != archive_id or name in (".", "..") or name.startswith("."):
        raise HTTPException(400, "非法 id")
    if "/" in name or "\\" in name:
        raise HTTPException(400, "非法 id")
    return name


@router.get("/archive/list")
async def archive_list():
    """所有世界观档案列表"""
    archives = []
    if os.path.exists(FRAMEWORKS_DIR):
        for fn in sorted(os.listdir(FRAMEWORKS_DIR)):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(FRAMEWORKS_DIR, fn), encoding="utf-8") as f:
                        data = json.load(f)
                    archives.append({
                        "id": data.get("id", fn[:-5]),
                        "name": data.get("name", fn[:-5]),
                        "tagline": data.get("tagline", ""),
                        "core_metaphor": data.get("core_metaphor", ""),
                    })
                except Exception:
                    continue
    return {"archives": archives}


@router.get("/archive/{archive_id}")
async def archive_detail(archive_id: str):
    """单个世界观档案详情"""
    archive_id = _safe_framework_id(archive_id)
    path = os.path.join(FRAMEWORKS_DIR, f"{archive_id}.json")
    if not os.path.exists(path):
        # 尝试按文件名匹配（id 可能是中文名）
        for fn in os.listdir(FRAMEWORKS_DIR):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(FRAMEWORKS_DIR, fn), encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("id") == archive_id or data.get("name") == archive_id:
                        return data
                except Exception:
                    continue
        raise HTTPException(404, f"档案不存在: {archive_id}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
