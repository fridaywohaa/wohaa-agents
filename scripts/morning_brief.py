#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Generate and optionally send Luke's Morning Briefing (HK).

Design goals:
- Traditional Chinese (zh-Hant)
- One message
- No tables
- Focus: what to wear/umbrella + 3 news categories + reminders (today + overdue)
- Local-first: uses Open-Meteo + RSS + remindctl

Usage:
  # Print only
  python3 morning_brief.py

  # Send to Telegram via OpenClaw CLI (recommended for cron reliability)
  python3 morning_brief.py --send --target 1626602099
"""

from __future__ import annotations

import argparse
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
# 目標：全部輸出繁體中文，所以世界/科技都用 Google News zh-Hant feeds。
RSS_HK = "https://news.google.com/rss/search?q=%E9%A6%99%E6%B8%AF&hl=zh-HK&gl=HK&ceid=HK:zh-Hant"
RSS_WORLD = "https://news.google.com/rss/search?q=%E5%9C%8B%E9%9A%9B&hl=zh-HK&gl=HK&ceid=HK:zh-Hant"
RSS_TECH = "https://news.google.com/rss/search?q=%E7%A7%91%E6%8A%80%20OR%20AI&hl=zh-HK&gl=HK&ceid=HK:zh-Hant"

MAX_NEWS = 3
MAX_TODAY = 8
MAX_OVERDUE = 6

DEFAULT_TELEGRAM_TARGET = "1626602099"
LAST_BRIEF_PATH = os.path.expanduser("~/.openclaw/workspace/memory/morning-brief-last.txt")


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


def clean_subtitle(s: str) -> str:
    """Turn feed description into a single plain summary line.

    Requirements:
    - No URLs
    - No "Article URL:" / "Comments URL:" noise
    - Keep it short
    """

    s = strip_html(s or "")
    s = re.sub(r"\b(Article URL:|Comments URL:)\s*", "", s, flags=re.I)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -–—\t\r\n")
    return truncate(s, 80)


def clean_title(title: str) -> str:
    """Remove noisy source suffix like ' - Yahoo' / domains from titles."""
    t = (title or "").strip()
    if " - " in t:
        head, tail = t.rsplit(" - ", 1)
        tail_l = tail.lower()
        likely_source = (
            len(tail) <= 40
            and (
                "." in tail
                or any(
                    k in tail_l
                    for k in [
                        "yahoo",
                        "bbc",
                        "cnn",
                        "bloomberg",
                        "reuters",
                        "nytimes",
                        "the new york times",
                        "washington post",
                        "cnbc",
                        "hk01",
                        "香港01",
                        "orangenews",
                        "hket",
                        "信報",
                        "香港電台",
                        "文匯",
                        "東網",
                        "明報",
                        "蘋果",
                        "新聞網",
                        "網站",
                        "財經",
                        "limited",
                        "media",
                    ]
                )
            )
        )
        if likely_source and head.strip():
            t = head.strip()

    # Also trim trailing ' - SOURCE' where SOURCE may include multiple dashes.
    t = re.sub(r"\s+-\s+(LOOOP\s+MEDIA\s+LIMITED|LOOOP|MEDIA\s+LIMITED)\s*$", "", t, flags=re.I)
    return t


def norm_text(s: str) -> str:
    s = (s or "").lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", s)


def is_subtitle_redundant(title: str, subtitle: str) -> bool:
    from difflib import SequenceMatcher

    a = norm_text(title)
    b = norm_text(subtitle)
    if not a or not b:
        return True
    if b in a or a in b:
        return True
    # similarity (robust to minor punctuation changes)
    return SequenceMatcher(None, a, b).ratio() >= 0.78


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
        raw_title = (it.findtext("title") or "").strip()
        if not raw_title:
            continue
        title = clean_title(raw_title)

        desc = (it.findtext("description") or "").strip()
        sub = clean_subtitle(desc)
        if is_subtitle_redundant(title, sub):
            sub = ""

        out.append((title, sub))
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
    now_temp: Optional[float]
    min_temp: Optional[float]
    max_temp: Optional[float]
    now_text: str
    wind_kmh: Optional[float]
    rain_prob_max: Optional[int]  # 0-100 (max in next hours)
    wear: str
    umbrella: str


def get_weather() -> WeatherCard:
    """Fetch HK weather. Never throw; returns best-effort card."""

    today = dt.datetime.now(TZ).date()
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&hourly=temperature_2m,precipitation_probability,weathercode,windspeed_10m"
        "&daily=temperature_2m_max,temperature_2m_min"
        "&timezone=Asia%2FHong_Kong"
        f"&start_date={today.isoformat()}&end_date={today.isoformat()}"
    )

    try:
        j = json.loads(fetch_bytes(url).decode("utf-8"))

        now = dt.datetime.now(TZ)
        h_times = [dt.datetime.fromisoformat(t).replace(tzinfo=TZ) for t in j["hourly"]["time"]]
        idx = max(i for i, t in enumerate(h_times) if t <= now)

        now_temp = float(j["hourly"]["temperature_2m"][idx])
        now_wc = int(j["hourly"]["weathercode"][idx])
        wind = float(j["hourly"]["windspeed_10m"][idx])

        dmax = float(j["daily"]["temperature_2m_max"][0])
        dmin = float(j["daily"]["temperature_2m_min"][0])

        probs = j["hourly"].get("precipitation_probability") or []
        # Use next ~12h max probability
        rain_prob_max: Optional[int] = None
        if probs:
            sl = probs[idx : min(idx + 13, len(probs))]
            try:
                rain_prob_max = int(max(float(x) for x in sl))
            except Exception:
                rain_prob_max = None

        # Wear heuristic (simple)
        if dmax >= 25:
            wear = "短袖"
        elif dmax >= 21:
            wear = "短袖 / 薄外套（早晚）"
        elif dmax >= 18:
            wear = "薄外套"
        else:
            wear = "外套"

        # Umbrella policy (Luke): based on rain probability
        umbrella: str
        if rain_prob_max is None:
            umbrella = "未能取得降雨機會：穩陣帶摺遮"
        elif rain_prob_max >= 60:
            umbrella = f"要拎遮（降雨機會 {rain_prob_max}%）"
        elif rain_prob_max >= 30:
            umbrella = f"建議帶摺遮（降雨機會 {rain_prob_max}%）"
        else:
            umbrella = f"唔駛拎遮（降雨機會 {rain_prob_max}%）"

        return WeatherCard(
            now_temp=now_temp,
            min_temp=dmin,
            max_temp=dmax,
            now_text=wmo_to_text(now_wc),
            wind_kmh=wind,
            rain_prob_max=rain_prob_max,
            wear=wear,
            umbrella=umbrella,
        )

    except Exception:
        # Fail-soft: still produce a usable suggestion
        return WeatherCard(
            now_temp=None,
            min_temp=None,
            max_temp=None,
            now_text="（暫時拉唔到天氣）",
            wind_kmh=None,
            rain_prob_max=None,
            wear="薄外套",
            umbrella="未能取得降雨機會：穩陣帶摺遮",
        )


def parse_due(iso: str) -> dt.datetime:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)


def fmt_time(d: dt.datetime) -> str:
    # 10:00am style
    return d.strftime("%-I:%M%p").lower()


def fmt_day(d: dt.datetime) -> str:
    return d.strftime("%-d/%-m")


def get_reminders_today_overdue() -> Tuple[List[str], List[str], Optional[str]]:
    # Use `show all` to avoid remindctl's built-in filter timezone edge cases.
    raw = sh(["remindctl", "show", "all", "--list", LIST_NAME, "--json", "--no-input"], timeout=25)
    items = json.loads(raw)
    today = dt.datetime.now(TZ).date()

    # Sort policy: high priority first, then time/date.
    rows_today: List[Tuple[int, dt.datetime, str]] = []
    rows_over: List[Tuple[int, dt.datetime, str]] = []

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
        is_high = 1 if pr in ("high", "1") else 0
        warn = " ⚠️" if is_high else ""

        if due_dt.date() == today:
            rows_today.append((is_high, due_dt, f"{title}（{fmt_time(due_dt)}）{warn}"))
        elif due_dt.date() < today:
            rows_over.append((is_high, due_dt, f"{title}（{fmt_day(due_dt)}）{warn}"))

    rows_today.sort(key=lambda x: (-x[0], x[1]))
    rows_over.sort(key=lambda x: (-x[0], x[1]))

    today_lines = [s for _, _, s in rows_today[:MAX_TODAY]]
    over_lines = [s for _, _, s in rows_over[:MAX_OVERDUE]]

    urgent: Optional[str] = None
    # Prefer overdue high priority, then today's high priority
    for is_high, _, s in rows_over:
        if is_high:
            urgent = s
            break
    if urgent is None:
        for is_high, _, s in rows_today:
            if is_high:
                urgent = s
                break

    return today_lines, over_lines, urgent


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
    today_lines, over_lines, urgent = get_reminders_today_overdue()
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
    if weather.min_temp is not None and weather.max_temp is not None:
        lines.append(f"- 着衫：{weather.wear}（約 {weather.min_temp:.1f}–{weather.max_temp:.1f}°C）")
    else:
        lines.append(f"- 着衫：{weather.wear}")

    lines.append(f"- 遮：{weather.umbrella}")

    if weather.now_temp is not None and weather.wind_kmh is not None:
        lines.append(
            f"- 而家：{weather.now_temp:.1f}°C，{weather.now_text}，風約 {weather.wind_kmh:.1f} km/h"
        )
    else:
        lines.append(f"- 而家：{weather.now_text}")

    if urgent:
        lines.append(f"🔔 優先提醒：{urgent}")
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


def persist_last_brief(msg: str) -> None:
    try:
        os.makedirs(os.path.dirname(LAST_BRIEF_PATH), exist_ok=True)
        with open(LAST_BRIEF_PATH, "w", encoding="utf-8") as f:
            f.write(msg)
    except Exception:
        pass


def send_to_telegram(msg: str, target: str) -> None:
    # Avoid shell quoting issues by using argv list.
    subprocess.check_call(
        [
            "openclaw",
            "message",
            "send",
            "--channel",
            "telegram",
            "--target",
            str(target),
            "--message",
            msg,
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="Send via OpenClaw to Telegram")
    ap.add_argument("--target", default=DEFAULT_TELEGRAM_TARGET, help="Telegram chat id")
    ap.add_argument("--force-target", action="store_true", help="Allow sending to a non-default target")
    args = ap.parse_args()

    # Safety: prevent accidental mis-delivery.
    if args.send and (str(args.target) != str(DEFAULT_TELEGRAM_TARGET)) and not args.force_target:
        raise SystemExit(
            f"Refusing to send: target must be {DEFAULT_TELEGRAM_TARGET}. "
            "(Use --force-target to override.)"
        )

    try:
        msg = build_message()
        persist_last_brief(msg)

        if args.send:
            send_to_telegram(msg, args.target)
            sys.stdout.write("SENT_OK\n")
        else:
            sys.stdout.write(msg)

        return 0

    except Exception as e:
        sys.stdout.write("ERROR: Morning brief failed\n" + str(e) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
