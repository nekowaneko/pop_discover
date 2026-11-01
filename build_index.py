#把 web_info.db 轉成 GitHub Pages 前端用的小型 JSON 檔
#輸出到 site/data/：
#  meta.json        資料筆數、更新時間、整體概況
#  stats.json       每件作品的喜歡、收藏、觀看數（欄位式陣列，列號＝作品順序）
#  tags.json        所有標籤與出現次數，依次數排序；陣列位置就是標籤編號
#  post/{n}.json    標籤編號 → 含此標籤的作品列號（差分編碼），依「標籤編號 % 分片數」分檔
#  rows/{n}.json    每件作品的標籤編號，每 ROW_CHUNK 筆一檔，算「常一起出現的標籤」用
import os
import json
import shutil
import sqlite3
import statistics
from datetime import datetime, timezone
from collections import Counter, defaultdict

# 常數定義
DB_FILENAME = 'web_info.db'
OUT_DIR = os.path.join('site', 'data')
POST_SHARDS = 256  #標籤索引分片數
ROW_CHUNK = 5000  #每個作品標籤檔的筆數
OVERVIEW_TOP = 20  #概況頁列出幾個熱門標籤


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, separators=(',', ':'))


def split_tags(text):
    #逗號分隔的標籤字串 → 去重後的標籤清單（保留原順序）
    return list(dict.fromkeys(t.strip() for t in (text or '').split(',') if t.strip()))


def load_rows():
    conn = sqlite3.connect(DB_FILENAME)
    columns = [row[1] for row in conn.execute('PRAGMA table_info(web_info)')]
    date_column = 'create_date' if 'create_date' in columns else 'NULL'
    rows = conn.execute(f'''
        SELECT tags, like_count, bookmark_count, view_count, {date_column}
        FROM web_info
        ORDER BY CAST(work_ID AS INTEGER)''').fetchall()
    conn.close()
    return rows


def build_index():
    rows = load_rows()
    row_tags = [split_tags(row[0]) for row in rows]

    # 標籤字典：依出現次數排序，常見標籤編號小，檔案也比較小
    tag_count = Counter(tag for tags in row_tags for tag in tags)
    tag_names = [tag for tag, _ in tag_count.most_common()]
    tag_id = {tag: i for i, tag in enumerate(tag_names)}

    # 倒排索引：標籤編號 → 作品列號
    postings = defaultdict(list)
    for row_index, tags in enumerate(row_tags):
        for tag in tags:
            postings[tag_id[tag]].append(row_index)

    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)  #清掉舊檔，避免分片數改變時殘留

    write_json(os.path.join(OUT_DIR, 'stats.json'), {
        'like': [row[1] for row in rows],
        'bookmark': [row[2] for row in rows],
        'view': [row[3] for row in rows],
    })
    write_json(os.path.join(OUT_DIR, 'tags.json'), [[tag, tag_count[tag]] for tag in tag_names])

    shards = defaultdict(dict)
    for tid, row_list in postings.items():
        deltas = [row_list[0]] + [b - a for a, b in zip(row_list, row_list[1:])]  #差分編碼縮小檔案
        shards[tid % POST_SHARDS][tid] = deltas
    for shard in range(POST_SHARDS):
        write_json(os.path.join(OUT_DIR, 'post', f'{shard}.json'), shards.get(shard, {}))

    for start in range(0, len(rows), ROW_CHUNK):
        chunk = [[tag_id[tag] for tag in tags] for tags in row_tags[start:start + ROW_CHUNK]]
        write_json(os.path.join(OUT_DIR, 'rows', f'{start // ROW_CHUNK}.json'), chunk)

    # 概況：熱門標籤與其觀看數中位數
    views = [row[3] for row in rows]
    overview = []
    for tag in tag_names[:OVERVIEW_TOP]:
        tag_views = [views[i] for i in postings[tag_id[tag]]]
        overview.append({'tag': tag, 'count': tag_count[tag], 'median_view': statistics.median(tag_views)})
    dates = sorted(row[4] for row in rows if row[4])
    write_json(os.path.join(OUT_DIR, 'meta.json'), {
        'count': len(rows),
        'tag_count': len(tag_names),
        'post_shards': POST_SHARDS,
        'row_chunk': ROW_CHUNK,
        'built_at': datetime.now(timezone.utc).isoformat(timespec='minutes'),
        'dated_count': len(dates),
        'newest_create_date': dates[-1] if dates else None,
        'median_view': statistics.median(views) if views else 0,
        'overview': overview,
    })
    print(f'完成：{len(rows)} 件作品、{len(tag_names)} 個標籤 → {OUT_DIR}')


if __name__ == '__main__':
    build_index()
