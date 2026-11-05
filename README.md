# 🤖 AGV 智慧物流倉儲調度與路徑規劃模擬系統
# Smart Warehouse AGV Dispatching & Pathfinding Simulation

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-yellow.svg)](https://www.python.org/)
[![HTML5 Canvas](https://img.shields.io/badge/HTML5-Canvas-orange.svg)](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-v3-38bdf8.svg)](https://tailwindcss.com/)

一個輕量、現代且直覺的**無人搬運車 (AGV / AMR) 智慧倉儲調度與路徑規劃模擬系統**。
本專案透過物件導向架構 (OOP) 實作了多智慧體路徑規劃 (MAPF)、通道互斥鎖避死鎖、啟發式 A* 尋路與最佳化派工等經典演算法，並提供 60 FPS 流暢的深色科技風視覺化儀表板。

A lightweight, modern, and interactive **Automated Guided Vehicle (AGV) Smart Warehouse Dispatching & Simulation System**. It implements Multi-Agent Pathfinding (MAPF), corridor mutex deadlock prevention, A* heuristic navigation, and greedy task dispatching, rendered in a 60 FPS cyberpunk-style dashboard.

---

## 📌 適用情境 (Application Scenarios)

1. **演算法與資料結構課程作業 (Algorithm Course Homework)**：
   * 示範 A* 尋路（結合最小堆積 Min-Heap 與轉彎懲罰）、BFS 區域擴散掃描、曼哈頓啟發式函數及優先權佇列的實際應用。
2. **大學專題 / 高中科技專案展示 (Cap-Stone Project & Science Fair)**：
   * 具備完整動態視覺化效果、即時車隊監控表格、滾動事件日誌與 4 大演算法互動圖解彈窗，非常適合作為口頭報告與專案成果發表。
3. **自動化物流與機器人概念驗證 (Smart Logistics POC)**：
   * 模擬無人搬運車在工廠/倉庫單行道走廊中的避讓、互斥鎖申請、低電量自動返航回充、貨物裝卸排程等核心業務邏輯。

---

## 📂 專案檔案結構 (Project Structure)

| 檔案名稱 | 說明 |
| :--- | :--- |
| **`index.html`** | **主要視覺化儀表板**。純前端單檔即可執行（包含 60 FPS HTML5 Canvas 動畫、即時車隊狀態表、任務看板、事件日誌與演算法教學彈窗）。全代碼皆附有高中生易懂的台美雙語註解，無外部構建依賴。 |
| **`app.py`** | **Python 一鍵伺服器啟動器**。以 Python 內建 HTTP 伺服器啟動服務並自動開啟瀏覽器，方便跨平台一鍵演示。 |
| **`simulation.py`** | **純 Python 演算法實作核心**。包含完整物件導向設計（`WarehouseMap`, `AStarPlanner`, `CorridorMutex`, `TaskDispatcher`, `AGV`），適合用於演算法繳交或無介面的背景測試。 |
| **`requirements.txt`** | Python 套件依賴清單（純 Python 運行僅需標準庫；可選套件供進階資料分析）。 |
| **`README.md`** | 專案說明、教學與演算法技術文件。 |
| **`.gitignore`** | Git 忽略規則（自動過濾虛擬環境、暫存檔與原始草稿）。 |

---

## 🚀 快速上手教學 (Quick Start Guide)

本專案提供兩種執行方式，均可零設定直接啟動：

### 方法一：使用 Python 一鍵啟動 (推薦)
在終端機 (Terminal) 中切換至專案資料夾，執行：
```bash
python3 app.py
```
> 系統會自動在背景啟動本地伺服器，並於預設瀏覽器中開啟 `http://localhost:8080/index.html`。

### 方法二：直接點擊開啟
使用 Chrome、Edge 或 Safari 等現代瀏覽器，直接雙擊打開 **`index.html`** 檔案即可完整運作（完全離線可用，無需 Node.js 或 Webpack 打包環境）。

---

## 🎮 介面操作指南 (Interactive Controls)

* **模擬控制**：
  * **播放 / 暫停**：即時啟動或凍結模擬迴圈。
  * **模擬速度**：支援 0.5x、1.0x、2.0x、5.0x 多段平滑加速。
  * **自動產生任務**：開啟後系統每隔數秒隨機指派取送貨任務，模擬繁忙工廠環境。
* **場景編輯工具**：
  * **加站點 (Add Station)**：在地圖空地左鍵點擊，新增取送貨工作站（A、B、C...）。
  * **加充電樁 (Add Charger)**：左鍵點擊新增無線充電月台。
  * **畫禁區 (Draw Danger Zone)**：滑鼠拖曳框選一塊矩形，建立管制禁行區。
  * **移動/刪除**：左鍵拖曳站點即可重新擺放位置；右鍵點擊站點或充電樁可直接刪除。
  * **隨機地圖 (Random Map)**：隨機生成貨架佈局與通道結構。

---

## 🧠 核心演算法圖解與原理 (Core Algorithms Explained)

本專案將 5 大核心演算法以最直觀生活化的方式實現，程式碼內附完整 **「台灣繁體中文 + 美國英文」** 雙語深度註解：

### 1. Min-Heap 最小堆積 (`MinHeap`)
* **生活化比喻**：排隊時永遠讓「數字最小的人」站最前面。
* **演算法原理**：A* 尋路需要頻繁抓出成本最低的節點。若使用普通陣列搜尋需花費 $O(N)$；使用二元最小堆積僅需 **$O(\log N)$** 即可完成插入與極值取出。

### 2. A* 啟發式最短路徑演算法 (`PathFinder` / `AStarPlanner`)
* **核心公式**：
  $$\mathbf{f(n) = g(n) + h(n)}$$
  * $g(n)$：從起點走到目前格子的**實際步數成本**。
  * $h(n)$：使用**曼哈頓距離** $|x_1 - x_2| + |y_1 - y_2|$ 預估到目的地的直線距離。
  * **轉彎懲罰 (Turn Penalty)**：若轉彎方向與父節點不一致，額外追加 $0.5$ 代價，使 AGV 傾向走直行通道，大幅減少不必要的頻繁轉向。

### 3. BFS 狹窄通道自動識別 (`MapAnalyzer`)
* **生活化比喻**：像水流蔓延一樣掃描整張地圖。
* **演算法原理**：利用廣度優先搜尋 (BFS) 掃描空白格子。若格子「上下被貨架包夾」或「左右被貨架包夾」，系統即認定為單線狹窄走廊，並將相連格子標記為同一區域 ID，由互斥鎖列管。

### 4. 單線通道互斥鎖 (`MutexManager` / `CorridorMutex`)
* **生活化比喻**：單線鐵路橋上的信號號誌燈。
* **演算法原理**：狹窄通道寬度僅容一車。第一輛 AGV 進入時取得鎖 (`acquire`)，對向車輛必須在通道外停等（或進行避讓）；離開通道後釋放鎖 (`release`)，**徹底杜絕死鎖 (Deadlock) 與對撞**。

### 5. 最佳化貪婪派工系統 (`Dispatcher` / `TaskDispatcher`)
* **核心公式**：
  $$\text{Total Cost} = \text{Distance}(AGV, Pickup) + (100 - \text{Battery}) \times 2$$
* **演算法原理**：如同外送平台調度，綜合評估取貨距離與電池剩餘量，優先指派離工作站最近且電量最充足的車輛，達成全域最佳輸送效率。

---

## 📄 開源授權 (License)

本專案採用 [MIT License](LICENSE) 授權開放。歡迎自由下載、修改、用於課堂學習、學術研究或二次開發。
This project is open-sourced under the MIT License. Feel free to use, modify, and share for learning, academic research, or portfolio presentations!

