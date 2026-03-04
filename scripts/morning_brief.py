#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Generate Luke's Morning Briefing (HK) as a single Telegram-friendly message.

Design goals:
- Traditional Chinese (zh-Hant)
- One message
- No tables
- Focus: what to wear/umbrella + 3 news categories + reminders (today + overdue)
- Local-first: uses Open-Meteo + RSS + remindctl

Usage:
  python3 morning_brief.py
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen

TZ = ZoneInfo("Asia/Hong_Kong")
LAT = 22.28
LON = 114.15
LIST_NAME = "Openclaw"

# RSS sources (lightweight + usually accessible)
RSS_HK = "https://news.google.com/rss/search?q=%E9%A6%99%E6%B8%AF&hl=zh-HK&gl=HK&ceid=HK:zh-Hant"
RSS_WORLD = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
RSS_TECH = "https://hnrss.org/frontpage"

MAX_NEWS = 3
MAX_TODAY = 8
MAX_OVERDUE = 6


def sh(cmd: List[str], timeout: int = 30) -> str:
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout, text=True)


def fetch_bytes(url: str, timeout: int = 20) -> bytes:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def truncate(s: str, n: int = 90) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def parse_rss(data: bytes, n: int = 3) -> List[Tuple[str, str]]:
    root = ET.fromstring(data)
    items = root.findall("./channel/item")
    out: List[Tuple[str, str]] = []
    for it in items[:n]:
        title = (it.findtext("title") or "").strip()
        desc = (it.findtext("description") or "").strip()
        desc = truncate(strip_html(desc), 96)
        if title:
            out.append((title, desc))
    return out


def weekday_zh(d: dt.date) -> str:
    m = ["一", "二", "三", "四", "五", "六", "日"]
    return m[d.weekday()]


def wmo_to_text(code: Optional[int]) -> str:
    # Minimal mapping (enough for daily life)
    m = {
        0: "天晴",
        1: "大致天晴",
        2: "部分多雲",
        3: "多雲",
        45: "大霧",
        48: "霧凇",
        51: "毛毛雨",
        53: "毛毛雨",
        55: "毛毛雨",
        61: "細雨",
        63: "雨",
        65: "大雨",
        80: "驟雨",
        81: "驟雨",
        82: "猛烈驟雨",
        95: "雷暴",
    }
    return m.get(code, f"天氣代碼 {code}") if code is not None else "—"


@dataclass
class WeatherCard:
    now_temp: float
    min_temp: float
    max_temp: float
    now_text: str
    wind_kmh: float
    wear: str
    umbrella: str


def get_weather() -> WeatherCard:
    today = dt.datetime.now(TZ).date()
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&hourly=temperature_2m,precipitation,weathercode,windspeed_10m"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        "&timezone=Asia%2FHong_Kong"
        f"&start_date={today.isoformat()}&end_date={today.isoformat()}"
    )
    j = json.loads(fetch_bytes(url).decode("utf-8"))

    now = dt.datetime.now(TZ)
    h_times = [dt.datetime.fromisoformat(t).replace(tzinfo=TZ) for t in j["hourly"]["time"]]
    idx = max(i for i, t in enumerate(h_times) if t <= now)

    now_temp = float(j["hourly"]["temperature_2m"][idx])
    now_wc = int(j["hourly"]["weathercode"][idx])
    wind = float(j["hourly"]["windspeed_10m"][idx])

    dmax = float(j["daily"]["temperature_2m_max"][0])
    dmin = float(j["daily"]["temperature_2m_min"][0])
    dprec = float(j.get("daily", {}).get("precipitation_sum", [0.0])[0] or 0.0)

    # next ~12h precipitation peak
    prec = [float(x) for x in j["hourly"]["precipitation"]]
    next_prec = max(prec[idx : min(idx + 13, len(prec))]) if prec else 0.0

    # Wear heuristic (simple)
    if dmax >= 25:
        wear = "短袖"
    elif dmax >= 21:
        wear = "短袖 / 薄外套（早晚）"
    elif dmax >= 18:
        wear = "薄外套"
    else:
        wear = "外套"

    # Umbrella policy: stable but not paranoid
    if dprec >= 1.0 or next_prec >= 0.3:
        umbrella = "帶摺遮"
    elif next_prec >= 0.1 or dprec >= 0.2:
        umbrella = "建議帶摺遮（天氣唔穩）"
    else:
        umbrella = "可唔帶（想穩陣就帶摺遮）"

    return WeatherCard(
        now_temp=now_temp,
        min_temp=dmin,
        max_temp=dmax,
        now_text=wmo_to_text(now_wc),
        wind_kmh=wind,
        wear=wear,
        umbrella=umbrella,
    )


def parse_due(iso: str) -> dt.datetime:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)


def fmt_time(d: dt.datetime) -> str:
    # 10:00am style
    return d.strftime("%-I:%M%p").lower()


def fmt_day(d: dt.datetime) -> str:
    return d.strftime("%-d/%-m")


def get_reminders_today_overdue() -> Tuple[List[str], List[str]]:
    # Use `show all` to avoid remindctl's built-in filter timezone edge cases.
    raw = sh(["remindctl", "show", "all", "--list", LIST_NAME, "--json", "--no-input"], timeout=25)
    items = json.loads(raw)
    today = dt.datetime.now(TZ).date()

    rows_today: List[Tuple[dt.datetime, str]] = []
    rows_over: List[Tuple[dt.datetime, str]] = []

    for it in items:
        if it.get("isCompleted"):
            continue
        due = it.get("dueDate")
        if not due:
            continue
        try:
            due_dt = parse_due(due)
        except Exception:
            continue

        title = (it.get("title") or "").strip()
        if not title:
            continue

        pr = str(it.get("priority") or "none")
        warn = " ⚠️" if pr in ("high", "1") else ""

        if due_dt.date() == today:
            rows_today.append((due_dt, f"{title}（{fmt_time(due_dt)}）{warn}"))
        elif due_dt.date() < today:
            rows_over.append((due_dt, f"{title}（{fmt_day(due_dt)}）{warn}"))

    rows_today.sort(key=lambda x: x[0])
    rows_over.sort(key=lambda x: x[0])

    today_lines = [s for _, s in rows_today[:MAX_TODAY]]
    over_lines = [s for _, s in rows_over[:MAX_OVERDUE]]

    return today_lines, over_lines


def get_news() -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]], List[Tuple[str, str]]]:
    hk: List[Tuple[str, str]] = []
    world: List[Tuple[str, str]] = []
    tech: List[Tuple[str, str]] = []

    try:
        hk = parse_rss(fetch_bytes(RSS_HK), MAX_NEWS)
    except Exception:
        hk = []
    try:
        world = parse_rss(fetch_bytes(RSS_WORLD), MAX_NEWS)
    except Exception:
        world = []
    try:
        tech = parse_rss(fetch_bytes(RSS_TECH), MAX_NEWS)
    except Exception:
        tech = []

    return hk, world, tech


def build_message() -> str:
    now = dt.datetime.now(TZ)
    d = now.date()

    weather = get_weather()
    today_lines, over_lines = get_reminders_today_overdue()
    hk, world, tech = get_news()

    # Verses/quotes (keep stable, easy)
    bible = (
        "「求你使我們早早飽得你的慈愛，好叫我們一生一世歡呼喜樂。」— 詩篇 90:14"
    )
    quote = '“The only way to do great work is to love what you do.” — Steve Jobs'

    lines: List[str] = []
    lines.append(f"☀️ Morning Brief — {d.isoformat()}（{weekday_zh(d)}）")
    lines.append("")

    lines.append("🌤️ 出門卡（香港）")
    lines.append(f"- 着衫：{weather.wear}（約 {weather.min_temp:.1f}–{weather.max_temp:.1f}°C）")
    lines.append(f"- 遮：{weather.umbrella}")
    lines.append(
        f"- 而家：{weather.now_temp:.1f}°C，{weather.now_text}，風約 {weather.wind_kmh:.1f} km/h"
    )
    lines.append("")

    lines.append("📋 今日要做（到期）")
    if today_lines:
        for s in today_lines:
            lines.append(f"- {s}")
    else:
        lines.append("- （今日冇到期事項）")
    lines.append("")

    lines.append("⚠️ 過期未做")
    if over_lines:
        for s in over_lines:
            lines.append(f"- {s}")
    else:
        lines.append("- （冇過期事項）")
    lines.append("")

    lines.append("📰 新聞（每類 3 條）")

    lines.append("🇭🇰 香港")
    if hk:
        for i, (t, sub) in enumerate(hk, 1):
            lines.append(f"{i}) {t}")
            if sub:
                lines.append(f"   - {sub}")
    else:
        lines.append("- （暫時拉唔到香港新聞源）")
    lines.append("")

    lines.append("🌏 國際")
    if world:
        for i, (t, sub) in enumerate(world, 1):
            lines.append(f"{i}) {t}")
            if sub:
                lines.append(f"   - {sub}")
    else:
        lines.append("- （暫時拉唔到國際新聞源）")
    lines.append("")

    lines.append("🤖 科技")
    if tech:
        for i, (t, sub) in enumerate(tech, 1):
            lines.append(f"{i}) {t}")
            if sub:
                lines.append(f"   - {sub}")
    else:
        lines.append("- （暫時拉唔到科技新聞源）")
    lines.append("")

    lines.append("📖 聖經金句")
    lines.append(bible)
    lines.append("")

    lines.append("💬 名人金句")
    lines.append(quote)

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    try:
        sys.stdout.write(build_message())
        return 0
    except Exception as e:
        sys.stdout.write("ERROR: Morning brief generation failed\n" + str(e) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
