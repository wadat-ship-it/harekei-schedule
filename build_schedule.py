#!/usr/bin/env python3
"""系列4店舗の出勤情報（シティヘブン）を取得し、1枚のHTMLにまとめる。

使い方:  python3 build_schedule.py          → schedule.html と share/index.html を生成
         python3 build_schedule.py --pages  → _site/index.html のみ生成（GitHub Pages 用）
依存ライブラリなし（Python 3 標準ライブラリのみ）
"""
import base64
import html
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://www.cityheaven.net"
SHOPS = [
    ("maid_infukuoka", "メイドin福岡", "#e85d8a"),
    ("harenchi_jogaku", "放課後クラブ", "#3d7be0"),
    ("matdemilk", "福岡DEまっとる。＆ひよこ治療院", "#e0a03d"),
    ("suteki_sister", "大人女子のちょっとHな専門店", "#2fa37a"),
]
AREA = "/fukuoka/A4001/A400102"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
OUT = Path(__file__).with_name("schedule.html")
SHARE_OUT = Path(__file__).with_name("share") / "index.html"  # 共有リンク（claude.ai）用


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
    time.sleep(1)  # 相手サーバーへの負荷を抑える
    return body


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("　", " ").strip()


def crawl(first_url):
    """ページングを辿って全ページのHTMLを返す"""
    pages, url = [], first_url
    while url and len(pages) < 10:
        body = fetch(url)
        pages.append(body)
        m = re.search(r'<link rel="next" href="([^"]+)"', body)
        url = m.group(1) if m else None
    return pages


def parse_weekly(body, shop):
    """週間出勤表（div#shukkin_list のテーブル）を解析"""
    girls = []
    for block in body.split('<div id="shukkin_list">')[1:]:
        block = block.split("</table>")[0]
        m = re.search(r'girlid-(\d+)/"[^>]*>\s*(.*?)</a>&nbsp;〔(\d+)歳〕', block, re.S)
        if not m:
            continue
        gid, name, age = m.group(1), text(m.group(2)), m.group(3)
        days = [re.sub(r"\s+", "", text(d)) for d in re.findall(r'<th class="week">(.*?)</th>', block, re.S)]
        img = re.search(r'src="(//img[^"]+)"', block)
        rows = block.split("</tr>")
        cells = re.findall(r"<td width=\"110\"[^>]*>(.*?)</td>", rows[1] if len(rows) > 1 else "", re.S)
        sched = {}
        for day, cell in zip(days, cells):
            if 'class="holiday"' in cell:
                continue
            t = re.findall(r"(\d{1,2}:\d{2})", cell)
            note = text(re.sub(r"\d{1,2}:\d{2}|<br\s*/?>|-", " ", cell))
            if t or note:
                sched[day] = {"start": t[0] if t else "", "end": t[1] if len(t) > 1 else "", "note": note}
        girls.append({
            "id": gid, "shop": shop, "name": name, "age": int(age),
            "img": ("https:" + img.group(1)).replace("/sn_grpb", "/grpb") if img else "",
            "url": f"{BASE}{AREA}/{shop}/girlid-{gid}/", "sched": sched,
        })
    return girls, days


def parse_today(body):
    """本日の出勤一覧から 待機状況 / スリーサイズ を取得"""
    info = {}
    for block in body.split('<div class="sugunavi_wrapper">')[1:]:
        m = re.search(r"girlid-(\d+)/", block)
        if not m:
            continue
        nav = re.search(r'<div class="sugunavibox">(.*?)</a>', block, re.S)
        status = re.sub(r"\s+", "", text(re.split(r'<div class="text"><p class="marquee"|<a ', nav.group(1))[0])) if nav else ""
        status = status.replace("～", " ～", 1) if re.match(r"\d", status) else status
        bust = re.search(r'class="bust_font_size shadow">(.*?)</p>', block, re.S)
        # 同じ子がページ内に複数回出るので、空の値で上書きしない
        cur = info.setdefault(m.group(1), {"status": "", "size": ""})
        cur["status"] = cur["status"] or status
        cur["size"] = cur["size"] or (text(bust.group(1)) if bust else "")
    return info


def main():
    all_girls, days, errors = [], [], []
    for shop, label, _ in SHOPS:
        try:
            print(f"取得中: {label}", file=sys.stderr)
            for body in crawl(f"{BASE}{AREA}/{shop}/attend/weekly/"):
                g, d = parse_weekly(body, shop)
                all_girls += g
                days = days or d
            today = {}
            for body in crawl(f"{BASE}{AREA}/{shop}/attend/"):
                today.update(parse_today(body))
            for g in all_girls:
                if g["shop"] == shop and g["id"] in today:
                    g.update(today[g["id"]])
        except Exception as e:  # 1店舗失敗しても他は出す
            errors.append(f"{label}: {e}")
            print(f"  失敗: {e}", file=sys.stderr)

    data = {
        "updated": datetime.now(timezone(timedelta(hours=9))).strftime("%Y/%m/%d %H:%M"),  # 日本時間
        "days": days,
        "shops": [{"id": s, "name": n, "color": c, "url": f"{BASE}{AREA}/{s}/attend/"} for s, n, c in SHOPS],
        "girls": all_girls,
        "errors": errors,
    }
    tpl = Path(__file__).with_name("template.html").read_text(encoding="utf-8")
    out = Path(__file__).with_name("_site") / "index.html" if "--pages" in sys.argv else OUT
    out.parent.mkdir(exist_ok=True)
    out.write_text(tpl.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False)), encoding="utf-8")
    print(f"生成しました: {out}  ({len(all_girls)}名)", file=sys.stderr)
    if "--pages" not in sys.argv:
        build_share(tpl, data)
    if errors and len(errors) == len(SHOPS):
        sys.exit(1)  # 全店舗失敗したら異常終了（Pages を空のページで上書きしない）


def build_share(tpl, data):
    """共有ページ用: 外部画像が使えないので写真を埋め込み、出勤予定のある子だけに絞る"""
    girls = [dict(g) for g in data["girls"] if g["sched"]]
    for g in girls:
        if not g["img"]:
            continue
        try:
            req = urllib.request.Request(g["img"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
                g["img"] = f"data:{mime};base64," + base64.b64encode(r.read()).decode()
        except Exception as e:
            print(f"  画像取得失敗: {g['name']}: {e}", file=sys.stderr)
            g["img"] = ""
    share = dict(data, girls=girls, share=True)
    page = tpl.replace("/*DATA*/null", json.dumps(share, ensure_ascii=False))
    # 公開時に doctype/head/body は自動で付くので外す
    page = re.sub(r"<!doctype html>|</?html[^>]*>|</?head>|</?body>|<meta (charset|name=\"viewport\")[^>]*>\n?", "", page)
    SHARE_OUT.parent.mkdir(exist_ok=True)
    SHARE_OUT.write_text(page.strip() + "\n", encoding="utf-8")
    print(f"共有用を生成しました: {SHARE_OUT}  ({len(girls)}名, {len(page) // 1024}KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
