# Pixiv人氣探索工具
## 想解決的問題
1. 自己的作品在pixiv上可以有多高的人氣？需要滿足哪些條件？

2. 依照我想要的標籤，最多可以有多少觀看數？作品製作方向為何？
## 基本想法
1. 輸入圖片 --> 轉換成向量 --> 搜索前五十張類似的圖片向量 --> 調出這些向量的相關資料 --> 進行統計，篩出結果 --> 輸出統計的觀看數(含標準差)、十大標籤、主題命名與描述。 (暫不執行)

2. 輸入標籤 --> 搜索相同或相似標籤的作品 --> 依觀看數排名 --> 將前五十多觀看數的作品調出，並統計觀看數 --> 輸出統計的觀看數(含標準差)與前十大人氣的作品。
## 流程
1. 爬資料  (ing)

   下載response.text，再從裡面抓數據。設定每6小時收集200筆，每收集一筆，間隔10-15秒。

3. 將資料以SQLite統計並儲存  (ing)

   儲存的資料包含work_ID、title、like、view、book mark、image url

4. 依照基本想法設計檢索邏輯  (O)

   輸入tag，從資料庫中搜尋有包含tag的tags，並依照其view排序，取前五十多觀看數的作品調出，同時計算前十多的tag，最後輸出10個tag、like、view、book mark的平均與標準差

6. 以jupyter notebook實作輸出  (O)

7. 以gradio進行圖形介面  (待)

8. 以git action達到自動化更新  (待)

## 擴展與優化

## 從中學到的東西
1. 不要太急著要資料，要注意短時間多次訪問可能會被鎖。

2. 學會用資料庫儲存資料，而不再是excel

## 中文版聲明
本專案的初衷是以開源形式提供一個工具，幫助創作者在 Pixiv 平台上更容易讓自己的作品獲得關注和曝光。所有從 Pixiv 上收集的資料均遵循其公開的數據範圍和使用條款，且我們強調本專案並不涉及任何侵犯版權或違法的行為。

本專案的數據收集行為僅限於技術研究和協助創作者分析其作品的表現，並無商業用途，也不會對第三方資料造成侵犯。本專案的開源目的是為了促進創作者社群的良性發展，而不是非法利用數據或違反平台規則。

我們聲明：

1. 所有收集的數據來自於公開資訊，並遵守 Pixiv 的使用政策。
2. 本專案不會使用這些數據進行任何形式的違法或不當操作，也不會用於商業化用途。
3. 若有任何版權或相關問題，請聯繫我們，我們會立即處理。

## 英文版聲明
This project is open source with the intention of providing a tool that helps creators gain more attention and exposure for their works on Pixiv. All data collected from Pixiv is within the publicly available scope and complies with the platform's terms of use. We emphasize that this project does not engage in any illegal activities or copyright infringement.

The data collected by this project is strictly for technical research and assisting creators in analyzing the performance of their works. It has no commercial intent, nor does it infringe upon third-party data. The goal of this open-source project is to foster a positive and supportive community for creators, not to misuse data or violate platform rules.

We declare:

1. All data collected is from publicly available information and adheres to Pixiv's terms of service.
2. This project will not use the data for any illegal or improper activities, nor for commercial purposes.
3. If any copyright or related concerns arise, please contact us, and we will address the issue immediately.

