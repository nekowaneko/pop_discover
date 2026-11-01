import sqlite3
import gradio as gr
import numpy as np
import threading
import webbrowser
from collections import Counter
import random

# 查找匹配 tags 的 work_ID 函數，並按照 view_count 排序，返回前 50 個結果
def find_top_50_by_tag(tags):
    db_filename='web_info.db'
    # 连接到 SQLite 数据库
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    # 构造 SQL 查询
    if tags == '':
        # 情况 1：没有输入 tag，搜索整个数据库
        query = '''
            SELECT like_count, bookmark_count, view_count, tags
            FROM web_info
            ORDER BY view_count DESC
        '''
        cursor.execute(query)
    else:
        # 情况 2 和 3：输入一个或多个 tag
        # 构造 WHERE 子句，确保每个 tag 都包含在 tags 字段中
        tag_conditions = ' AND '.join([f'tags LIKE ?' for _ in tags])
        query = f'''
            SELECT like_count, bookmark_count, view_count, tags
            FROM web_info
            WHERE {tag_conditions}
            ORDER BY view_count DESC
        '''
        # 为每个 tag 添加百分号前后匹配
        like_params = ['%' + tag + '%' for tag in tags]
        cursor.execute(query, like_params)

    # 获取查询结果
    results = cursor.fetchall()

    # 关闭数据库连接
    conn.close()

    # 返回匹配的 work_IDs 和对应的 view_count
    return [result[0] for result in results],[result[1] for result in results],[result[2] for result in results],[result[3] for result in results]


# 標準化標籤函數：去除前後空格，並將全角空格替換為半角
def normalize_tag(tag):
    return tag.strip()

# 找出前 10 個標籤的函數
def find_top_10_tags(matching_tags):
    all_tags = [normalize_tag(tag) for tag in ','.join(matching_tags).split(',')]
    tag_count = Counter(all_tags)
    most_common = tag_count.most_common()
    
    # 獲取前 10 個頻率最高的標籤
    top_10 = []
    current_rank = 1
    i = 0
    
    while current_rank <= 10 and i < len(most_common):
        freq = most_common[i][1]  
        same_freq_tags = [tag for tag, count in most_common if count == freq]
        selected_tags = random.sample(same_freq_tags, min(10 - len(top_10), len(same_freq_tags)))
        top_10.extend(selected_tags)
        i += len(same_freq_tags)
        current_rank += len(selected_tags)
    
    return top_10[:10]

# 處理標籤的函數
def process_tags(tag):
    #tag_list = tag.split(',')
    matching_like, matching_bookmark, matching_view, matching_tags = find_top_50_by_tag(tag)
    top_10_tags = find_top_10_tags(matching_tags)
    
    mean_like = np.round(np.array(matching_like).mean(), 0)
    std_like = np.round(np.array(matching_like).std(), 0)

    mean_bookmark = np.round(np.array(matching_bookmark).mean(), 0)
    std_bookmark = np.round(np.array(matching_bookmark).std(), 0)

    mean_view = np.round(np.array(matching_view).mean(), 0)
    std_view = np.round(np.array(matching_view).std(), 0)

    like_str = f"匹配 {tag} 的 like : {mean_like} ± {std_like}"
    bookmark_str = f"匹配 {tag} 的 bookmark : {mean_bookmark} ± {std_bookmark}"
    view_str = f"匹配 {tag} 的 view : {mean_view} ± {std_view}"
    
    return ','.join(top_10_tags), like_str, bookmark_str, view_str




iface = gr.Interface(
        fn=process_tags,  # 處理標籤的主函數
        inputs=gr.Textbox(label="輸入標籤 (,分隔)"),  # 輸入的標籤
        outputs=[
            gr.Textbox(label="前十大標籤"),  # 前 10 大標籤
            gr.Textbox(label="統計的喜歡數"),  # 喜歡數統計
            gr.Textbox(label="統計的標籤數"),  # 標籤數統計
            gr.Textbox(label="統計的閱覽數")  # 閱覽數統計
        ],
        title="Pixiv人氣探索工具",  # 介面的標題
        description="輸入標籤（用逗號分隔）來分析相關的數據統計"  # 描述
)

def launch_app():
    iface.launch()

if __name__ == "__main__":
    # 使用 threading 模組來在新線程中啟動 Gradio
    threading.Thread(target=launch_app).start()
    
    # 自動打開瀏覽器
    webbrowser.open("http://127.0.0.1:7860")