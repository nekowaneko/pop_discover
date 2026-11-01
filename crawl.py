#Pixiv 作品資料爬蟲（取代 legacy/discover.ipynb）
#做法：每次執行時，找出「LAG_DAYS 天前」那 WINDOW_HOURS 小時內發布的作品 ID 範圍，
#      在範圍內隨機抽樣，用 Pixiv 的 JSON 介面抓數據寫進 SQLite。
#這樣每筆資料記錄時都約發布滿 LAG_DAYS 天，觀看數比較有可比性，也能持續反映最新趨勢。
import os
import sys
import time
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from collections import Counter

import requests

# 常數定義
DB_FILENAME = 'web_info.db'
API_URL = 'https://www.pixiv.net/ajax/illust/{}'
LAG_DAYS = 7  #抓「發布滿幾天」的作品，設 0 就是抓最新作品
WINDOW_HOURS = 6  #每次抽樣的時間窗，與排程間隔相同
SAVE_TARGET = int(os.environ.get('SAVE_TARGET', 200))  #每次執行要存幾筆，可用環境變數覆寫（測試時用小一點）
MAX_ATTEMPTS = 600  #每次最多嘗試幾個 ID（刪除、私人、R-18 未登入都會失敗）
DELAY_RANGE = (3, 6)  #每次請求間隔秒數
PROBE_SPAN = 8  #探測某個 ID 時，往後最多找幾個 ID 直到遇到存在的作品
FALLBACK_LOW_ID = 121416180  #舊資料最後一筆，作為搜尋起點

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36',
    'Referer': 'https://www.pixiv.net/',
    'Accept': 'application/json',
    'Accept-Language': 'ja,en;q=0.8',
}

session = requests.Session()
session.headers.update(HEADERS)
if os.environ.get('PIXIV_PHPSESSID'):  #選用：設定登入 cookie 後才抓得到 R-18 作品
    session.cookies.set('PHPSESSID', os.environ['PIXIV_PHPSESSID'], domain='.pixiv.net')

stats = Counter()  #記錄每種結果的次數，最後印出摘要


class Blocked(Exception):
    #被 Pixiv 擋下（403／429）時拋出，整次執行直接停止
    pass


# 資料庫
def init_db():
    conn = sqlite3.connect(DB_FILENAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS web_info (
            work_ID TEXT PRIMARY KEY,
            title TEXT,
            tags TEXT,
            like_count INTEGER,
            bookmark_count INTEGER,
            view_count INTEGER,
            image_url TEXT
        )''')
    columns = [row[1] for row in conn.execute('PRAGMA table_info(web_info)')]
    if 'create_date' not in columns:  #舊資料庫沒有發布時間欄位，補上（舊資料會是空值）
        conn.execute('ALTER TABLE web_info ADD COLUMN create_date TEXT')
    conn.commit()
    return conn


def save_work(conn, work):
    conn.execute('''INSERT OR REPLACE INTO web_info
            (work_ID, title, tags, like_count, bookmark_count, view_count, image_url, create_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (work['work_ID'], work['title'], work['tags'], work['like_count'],
         work['bookmark_count'], work['view_count'], work['image_url'], work['create_date']))
    conn.commit()


# Pixiv 介面
def fetch_work(work_id):
    #回傳作品資料 dict；作品不存在或看不到時回傳 None
    try:
        response = session.get(API_URL.format(work_id), timeout=20)
    except requests.RequestException as error:
        stats['網路錯誤'] += 1
        print(f'[網路錯誤] {work_id} {error}')
        return None
    if response.status_code in (403, 429):
        raise Blocked(f'HTTP {response.status_code}，可能被 Pixiv 限制存取')
    if response.status_code == 404:
        stats['不存在'] += 1
        return None
    try:
        data = response.json()
    except ValueError:
        stats['非 JSON 回應'] += 1
        print(f'[非 JSON 回應] {work_id} HTTP {response.status_code} {response.text[:120]!r}')
        return None
    if data.get('error') or not data.get('body'):
        stats['看不到'] += 1  #刪除、私人或 R-18 未登入
        return None
    body = data['body']
    return {
        'work_ID': str(body['illustId']),
        'title': body.get('illustTitle', ''),
        'tags': ', '.join(t['tag'] for t in body.get('tags', {}).get('tags', [])),
        'like_count': int(body.get('likeCount', 0)),
        'bookmark_count': int(body.get('bookmarkCount', 0)),
        'view_count': int(body.get('viewCount', 0)),
        'image_url': (body.get('urls') or {}).get('regular') or '',
        'create_date': body.get('createDate', ''),
    }


def parse_date(text):
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def probe(work_id):
    #從 work_id 往後找第一個存在的作品，回傳 (ID, 發布時間, 作品資料)；都找不到回傳 None
    for offset in range(PROBE_SPAN):
        work = fetch_work(work_id + offset)
        time.sleep(1)
        if work and work['create_date']:
            return work_id + offset, parse_date(work['create_date']), work
    return None


def find_id_at(target_time, low_id):
    #找出「發布時間約等於 target_time」的作品 ID
    #先以倍增步長往上跳，越過目標後再二分搜尋
    step = 1_000_000
    high_id = low_id + step
    while True:
        found = probe(high_id)
        if found is None or found[1] >= target_time:  #None 代表已超過最新作品
            break
        low_id = found[0]
        step *= 2
        high_id = low_id + step
    while high_id - low_id > 50:
        middle = (low_id + high_id) // 2
        found = probe(middle)
        if found is None or found[1] >= target_time:
            high_id = middle
        else:
            low_id = found[0]
    return high_id


def get_search_floor(conn):
    #找搜尋下限：資料庫裡最新的作品 ID（數字比較，不用文字比較）
    row = conn.execute('SELECT MAX(CAST(work_ID AS INTEGER)) FROM web_info').fetchone()
    return row[0] or FALLBACK_LOW_ID


# 主流程
def crawl():
    conn = init_db()
    now = datetime.now(timezone.utc)
    window_end = now - timedelta(days=LAG_DAYS)
    window_start = window_end - timedelta(hours=WINDOW_HOURS)

    floor_id = min(get_search_floor(conn), FALLBACK_LOW_ID)  #下限要確定早於目標時間
    print(f'抽樣時間窗（UTC）：{window_start:%Y-%m-%d %H:%M} ~ {window_end:%Y-%m-%d %H:%M}')
    start_id = find_id_at(window_start, floor_id)
    end_id = find_id_at(window_end, start_id)
    print(f'對應作品 ID 範圍：{start_id} ~ {end_id}（共 {end_id - start_id} 個 ID）')
    if end_id <= start_id:
        raise RuntimeError('找不到有效的作品 ID 範圍')

    candidates = random.sample(range(start_id, end_id), min(MAX_ATTEMPTS, end_id - start_id))
    saved = 0
    for attempt, work_id in enumerate(candidates, 1):
        work = fetch_work(work_id)
        if work:
            save_work(conn, work)
            saved += 1
            stats['已儲存'] += 1
            if saved % 20 == 0:
                print(f'已儲存 {saved}/{SAVE_TARGET}（嘗試 {attempt} 個 ID）')
            if saved >= SAVE_TARGET:
                break
        time.sleep(random.uniform(*DELAY_RANGE))

    total = conn.execute('SELECT COUNT(*) FROM web_info').fetchone()[0]
    conn.close()
    return saved, total


if __name__ == '__main__':
    try:
        saved, total = crawl()
    except Blocked as error:
        print(f'[停止] {error}')
        print('結果摘要：', dict(stats))
        sys.exit(1)
    print('結果摘要：', dict(stats))
    print(f'本次儲存 {saved} 筆，資料庫共 {total} 筆')
    if saved == 0:  #一筆都沒存到就讓 Actions 顯示失敗，不再默默空轉
        sys.exit(1)
