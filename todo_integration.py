# -*- coding: utf-8 -*-
"""Microsoft To Do 集成模块 — 烧制结束时间提醒"""

import os
import json
import logging
from datetime import datetime

import msal
import requests as http_requests

import config

logger = logging.getLogger(__name__)

# ============================================================
# MSAL Token Cache (持久化到文件)
# ============================================================

_token_cache = msal.SerializableTokenCache()


def _load_cache():
    """从文件加载 token cache"""
    if os.path.exists(config.MS_TOKEN_CACHE_PATH):
        try:
            with open(config.MS_TOKEN_CACHE_PATH, "r", encoding="utf-8") as f:
                _token_cache.deserialize(f.read())
        except Exception as e:
            logger.warning(f"读取 MS token cache 失败: {e}")


def _save_cache():
    """将 token cache 保存到文件"""
    if _token_cache.has_state_changed:
        try:
            with open(config.MS_TOKEN_CACHE_PATH, "w", encoding="utf-8") as f:
                f.write(_token_cache.serialize())
        except Exception as e:
            logger.warning(f"保存 MS token cache 失败: {e}")


def _get_msal_app():
    """创建 MSAL ConfidentialClientApplication"""
    _load_cache()
    return msal.ConfidentialClientApplication(
        client_id=config.MS_CLIENT_ID,
        client_credential=config.MS_CLIENT_SECRET,
        authority=config.MS_AUTHORITY,
        token_cache=_token_cache,
    )


# ============================================================
# OAuth2 Flow
# ============================================================

def is_configured():
    """检查是否已配置 MS Client ID 和 Secret"""
    return bool(config.MS_CLIENT_ID and config.MS_CLIENT_SECRET)


def get_auth_url(state=None):
    """生成 Microsoft 登录 URL"""
    app = _get_msal_app()
    result = app.get_authorization_request_url(
        scopes=config.MS_SCOPES,
        redirect_uri=config.MS_REDIRECT_URI,
        state=state,
    )
    return result


def acquire_token_by_code(code):
    """用授权码换取 access token"""
    app = _get_msal_app()
    result = app.acquire_token_by_authorization_code(
        code,
        scopes=config.MS_SCOPES,
        redirect_uri=config.MS_REDIRECT_URI,
    )
    _save_cache()
    if "access_token" in result:
        logger.info("Microsoft To Do 授权成功")
        return True, None
    else:
        err = result.get("error_description", result.get("error", "未知错误"))
        logger.error(f"Microsoft To Do 授权失败: {err}")
        return False, err


def get_access_token():
    """获取有效的 access token（自动刷新）"""
    app = _get_msal_app()
    accounts = app.get_accounts()
    if not accounts:
        return None

    # 使用第一个已缓存的账户
    result = app.acquire_token_silent(
        scopes=config.MS_SCOPES,
        account=accounts[0],
    )
    _save_cache()

    if result and "access_token" in result:
        return result["access_token"]

    logger.warning("无法刷新 Microsoft access token，需要重新授权")
    return None


def is_connected():
    """检查是否已通过 Microsoft 授权（有缓存的账户）"""
    if not is_configured():
        return False
    app = _get_msal_app()
    accounts = app.get_accounts()
    return len(accounts) > 0


def disconnect():
    """断开 Microsoft 连接（清除 token cache）"""
    global _token_cache
    _token_cache = msal.SerializableTokenCache()
    if os.path.exists(config.MS_TOKEN_CACHE_PATH):
        try:
            os.remove(config.MS_TOKEN_CACHE_PATH)
        except Exception as e:
            logger.warning(f"删除 MS token cache 文件失败: {e}")
    logger.info("已断开 Microsoft To Do 连接")


# ============================================================
# Microsoft Graph API — To Do Tasks
# ============================================================

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _get_default_task_list_id(token):
    """获取默认的 To Do 任务列表 ID"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = http_requests.get(f"{GRAPH_BASE}/me/todo/lists", headers=headers, timeout=15)
    resp.raise_for_status()
    lists = resp.json().get("value", [])
    if not lists:
        return None
    # 查找 wellknownListName == "defaultList"，否则用第一个
    for lst in lists:
        if lst.get("wellknownListName") == "defaultList":
            return lst["id"]
    return lists[0]["id"]


def create_todo_task(token, list_id, sample_id, sintering_end):
    """创建一个 To Do 任务并设置提醒

    Args:
        token: access token
        list_id: 任务列表 ID
        sample_id: 样品编号
        sintering_end: 烧制结束时间字符串 (如 "2026-04-18 14:30  周六")

    Returns:
        task_id: 创建的任务 ID
    """
    reminder_dt = _parse_sintering_end(sintering_end)
    if not reminder_dt:
        logger.warning(f"无法解析烧制结束时间: {sintering_end}")
        return None

    task_body = {
        "title": f"🔥 样品 {sample_id} 烧制完成",
        "body": {
            "content": f"样品 {sample_id} 的烧制预计在此时间完成，请及时处理。",
            "contentType": "text",
        },
        "isReminderOn": True,
        "reminderDateTime": {
            "dateTime": reminder_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "China Standard Time",
        },
        "dueDateTime": {
            "dateTime": reminder_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "China Standard Time",
        },
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = http_requests.post(
        f"{GRAPH_BASE}/me/todo/lists/{list_id}/tasks",
        headers=headers,
        json=task_body,
        timeout=15,
    )
    resp.raise_for_status()
    task = resp.json()
    logger.info(f"已创建 To Do 任务: {task['id']} (样品 {sample_id})")
    return task["id"]


def update_todo_task(token, list_id, task_id, sample_id, sintering_end):
    """更新已有的 To Do 任务的提醒时间

    Returns:
        True if successful
    """
    reminder_dt = _parse_sintering_end(sintering_end)
    if not reminder_dt:
        logger.warning(f"无法解析烧制结束时间: {sintering_end}")
        return False

    patch_body = {
        "title": f"🔥 样品 {sample_id} 烧制完成",
        "isReminderOn": True,
        "reminderDateTime": {
            "dateTime": reminder_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "China Standard Time",
        },
        "dueDateTime": {
            "dateTime": reminder_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "China Standard Time",
        },
        # 更新时确保任务未完成，否则提醒不会触发
        "status": "notStarted",
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = http_requests.patch(
        f"{GRAPH_BASE}/me/todo/lists/{list_id}/tasks/{task_id}",
        headers=headers,
        json=patch_body,
        timeout=15,
    )
    resp.raise_for_status()
    logger.info(f"已更新 To Do 任务: {task_id} (样品 {sample_id})")
    return True


def delete_todo_task(token, list_id, task_id):
    """删除一个 To Do 任务"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = http_requests.delete(
        f"{GRAPH_BASE}/me/todo/lists/{list_id}/tasks/{task_id}",
        headers=headers,
        timeout=15,
    )
    # 404 is fine (task may have been manually deleted)
    if resp.status_code == 404:
        return True
    resp.raise_for_status()
    return True


# ============================================================
# 高级接口: 创建或更新 To Do 任务
# ============================================================

def create_or_update_todo(sample_id, sintering_end, db_module):
    """根据烧制结束时间创建或更新 Microsoft To Do 任务

    Args:
        sample_id: 样品编号
        sintering_end: 烧制结束时间字符串
        db_module: models 模块引用（用于读写 todo_tasks 表）

    Returns:
        (success: bool, message: str)
    """
    if not is_connected():
        return False, "未连接 Microsoft To Do"

    token = get_access_token()
    if not token:
        return False, "Microsoft token 已过期，请重新授权"

    try:
        list_id = _get_default_task_list_id(token)
        if not list_id:
            return False, "未找到 To Do 任务列表"

        # 查询是否已有关联的 todo task
        existing = db_module.get_todo_task(sample_id)

        if existing:
            # 更新已有任务
            try:
                update_todo_task(token, list_id, existing["task_id"], sample_id, sintering_end)
            except http_requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    # 任务已被手动删除，重新创建
                    task_id = create_todo_task(token, list_id, sample_id, sintering_end)
                    if task_id:
                        db_module.upsert_todo_task(sample_id, task_id, sintering_end)
                else:
                    raise
            else:
                db_module.upsert_todo_task(sample_id, existing["task_id"], sintering_end)
        else:
            # 创建新任务
            task_id = create_todo_task(token, list_id, sample_id, sintering_end)
            if task_id:
                db_module.upsert_todo_task(sample_id, task_id, sintering_end)

        return True, "已同步到 Microsoft To Do"

    except Exception as e:
        logger.error(f"同步 To Do 失败: {e}")
        return False, f"同步失败: {str(e)}"


# ============================================================
# 工具函数
# ============================================================

def _parse_sintering_end(sintering_end_str):
    """解析烧制结束时间字符串为 datetime 对象

    支持格式:
    - "2026-04-18 14:30  周六"
    - "2026-04-18T14:30"
    - "2026-04-18 14:30"
    """
    if not sintering_end_str:
        return None

    s = sintering_end_str.strip()
    # 移除末尾可能的星期信息（如 "  周六"）
    for weekday in ["周一", "周二", "周三", "周四", "周五", "周六", "周日",
                     "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        if weekday in s:
            s = s[:s.index(weekday)].strip()

    # 尝试多种格式解析
    for fmt in ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    return None
