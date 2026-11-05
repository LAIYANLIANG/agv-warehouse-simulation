"""
=============================================================================
智慧物流 AGV 倉儲調度與路徑規劃模擬系統 (Python + Plotly 版)
Smart Warehouse AGV Dispatching & Pathfinding Simulation (Python + Plotly)
=============================================================================
【專題說明 / Project Overview】:
本程式以物件導向架構 (OOP) 實作智慧倉儲無人搬運車 (AGV) 的核心演算法：
1. A* 啟發式最短路徑演算法 (結合最小堆積 Min-Heap 與轉彎懲罰)
2. BFS (廣度優先搜尋) 狹窄通道自動識別
3. 單線通道互斥鎖 (Mutex Lock)，防止走道死鎖與對撞
4. 綜合距離與電量懲罰的最佳化貪婪派工系統 (Greedy Dispatcher)
5. 智慧避讓機制 (Yielding & Replanning)
最終將整體模擬歷程輸出為 Plotly 互動式 HTML 動畫，附帶時間軸滑桿與播放控制。

This program implements the core algorithms of an Automated Guided Vehicle (AGV)
smart warehouse system using Object-Oriented Programming (OOP):
1. A* Heuristic Shortest Path Algorithm (with Min-Heap & turn penalty)
2. BFS (Breadth-First Search) automatic narrow aisle detection
3. Corridor Mutex Lock to prevent head-on collision and deadlocks
4. Optimized Greedy Dispatcher balancing transport distance and battery level
5. Smart Yielding and Dynamic Replanning mechanism
Finally, it exports the entire discrete-event simulation into an interactive Plotly HTML.
=============================================================================
"""

import heapq
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import plotly.graph_objects as go


# =============================================================================
# 1. 基礎狀態與資料結構 (States and Data Structures)
# =============================================================================

class AGVState(Enum):
    """
    【繁體中文】AGV 狀態機列舉：
    記錄車輛目前正在做什麼，就像紅綠燈有不同的燈號狀態一樣。

    [US English] AGV State Machine Enumeration:
    Represents what the vehicle is currently doing, similar to traffic light states.
    """
    IDLE = "閒置 (Idle)"
    MOVING_TO_PICKUP = "前往取貨 (To Pickup)"
    LOADING = "裝貨中 (Loading)"
    MOVING_TO_DELIVERY = "前往送貨 (To Delivery)"
    UNLOADING = "卸貨中 (Unloading)"
    MOVING_TO_CHARGE = "前往充電 (To Charger)"
    CHARGING = "充電中 (Charging)"
    YIELDING = "避讓等待 (Yielding)"


@dataclass
class Task:
    """
    【繁體中文】搬運任務資料類別：
    記錄一個訂單從哪裡取貨 (pickup)、送到哪裡 (delivery)。

    [US English] Transport Task Data Class:
    Records an order containing its pickup station and delivery station.
    """
    task_id: int
    pickup: str
    delivery: str
    status: str = "WAITING"  # WAITING -> IN_PROGRESS -> COMPLETED


# =============================================================================
# 2. 倉儲地圖環境 (Warehouse Map Environment)
# =============================================================================

class WarehouseMap:
    """
    【繁體中文】倉儲地圖類別：
    負責管理整個地圖的尺寸、貨架障礙物、工作站位置與走道識別。
    想像這是一張 2D 方格棋盤，0 代表平坦走道，1 代表放貨物的貨架（不能走）。

    [US English] Warehouse Map Class:
    Manages the grid dimensions, shelf obstacles, station coordinates, and aisles.
    Think of this as a 2D grid board where 0 represents walkable floor and 1 represents shelves (blocked).
    """

    def __init__(self, width: int = 24, height: int = 16):
        """
        【繁體中文】初始化地圖尺寸與各站點位置。
        [US English] Initializes map dimensions and station positions.
        """
        self.width = width
        self.height = height
        # 0: 可行走平地 (Walkable floor), 1: 貨架障礙 (Shelf obstacle)
        self.grid: List[List[int]] = [[0 for _ in range(width)] for _ in range(height)]
        
        # 走道區域 ID 對應表：0 表示開闊區，>0 表示該狹窄走道的編號
        # Aisle ID map: 0 = open area, >0 = unique ID of the narrow corridor
        self.aisle_map: List[List[int]] = [[0 for _ in range(width)] for _ in range(height)]

        # 定義工作站 (Stations) 座標
        # Define Workstation coordinates
        self.stations: Dict[str, Tuple[int, int]] = {
            "A": (2, 13),
            "B": (21, 13),
            "C": (2, 2),
            "D": (21, 2),
        }

        # 定義充電站 (Charging Station) 座標
        # Define Charging Station coordinate
        self.charger: Tuple[int, int] = (11, 0)

        # 建造貨架與識別走道
        # Build shelves and detect aisles
        self._build_warehouse_shelves()
        self.aisle_count = self._detect_narrow_aisles()

    def _build_warehouse_shelves(self) -> None:
        """
        【繁體中文】佈置倉儲貨架：
        在中間區域放置數座長條形貨架，中間自然形成單向走道與十字路口。
        外圍四周保留至少 1~2 格的環狀幹道，確保車輛可以繞行外圍。

        [US English] Builds warehouse shelves:
        Places rectangular shelf blocks in the central area, creating narrow corridors
        and crossroads between them. Leaves outer perimeter open for circular traffic flow.
        """
        # 左上與右上貨架區塊 (Top-left & Top-right shelf blocks)
        for y in range(8, 12):
            for x in range(4, 10):
                self.grid[y][x] = 1
            for x in range(14, 20):
                self.grid[y][x] = 1

        # 左下與右下貨架區塊 (Bottom-left & Bottom-right shelf blocks)
        for y in range(4, 7):
            for x in range(4, 10):
                self.grid[y][x] = 1
            for x in range(14, 20):
                self.grid[y][x] = 1

    def _detect_narrow_aisles(self) -> int:
        """
        【繁體中文】BFS 走道自動識別演算法：
        利用「廣度優先搜尋 (BFS)」掃描整張地圖。當發現某個格子「上下都是貨架」
        或「左右都是貨架」時，就代表這是一條狹窄走道！
        演算法會將連續相連的走道格子染上相同的區域 ID，未來用來做互斥鎖管理。

        [US English] BFS Aisle Detection Algorithm:
        Uses Breadth-First Search (BFS) to scan the grid. If a cell is sandwiched
        between shelves vertically or horizontally, it indicates a narrow corridor.
        The algorithm groups connected corridor cells into a shared Aisle ID for mutex management.
        """
        aisle_id = 1
        visited: Set[Tuple[int, int]] = set()

        for y in range(1, self.height - 1):
            for x in range(1, self.width - 1):
                if self.grid[y][x] != 0 or (x, y) in visited:
                    continue

                # 判斷是否被貨架夾在中間 (Check if flanked by shelves)
                is_h_aisle = (self.grid[y - 1][x] == 1 and self.grid[y + 1][x] == 1)
                is_v_aisle = (self.grid[y][x - 1] == 1 and self.grid[y][x + 1] == 1)

                if is_h_aisle or is_v_aisle:
                    # 使用 BFS 擴散整條走道 (Grow region using BFS)
                    queue = deque([(x, y)])
                    visited.add((x, y))
                    corridor_cells = []

                    while queue:
                        cx, cy = queue.popleft()
                        corridor_cells.append((cx, cy))
                        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < self.width and 0 <= ny < self.height:
                                if (nx, ny) not in visited and self.grid[ny][nx] == 0:
                                    # 保持同方向的夾角特徵 (Preserve same corridor orientation)
                                    h_flank = (self.grid[ny - 1][nx] == 1 and self.grid[ny + 1][nx] == 1) if 0 < ny < self.height - 1 else False
                                    v_flank = (self.grid[ny][nx - 1] == 1 and self.grid[ny][nx + 1] == 1) if 0 < nx < self.width - 1 else False
                                    if (is_h_aisle and h_flank) or (is_v_aisle and v_flank):
                                        visited.add((nx, ny))
                                        queue.append((nx, ny))

                    # 只有長度大於等於 2 格才視為需管制的通道
                    # Only register corridors with length >= 2
                    if len(corridor_cells) >= 2:
                        for cell_x, cell_y in corridor_cells:
                            self.aisle_map[cell_y][cell_x] = aisle_id
                        aisle_id += 1

        return aisle_id - 1

    def is_walkable(self, x: int, y: int) -> bool:
        """
        【繁體中文】檢查某個座標是否在地圖範圍內且不是貨架障礙物。
        [US English] Checks if a coordinate is within bounds and not a shelf obstacle.
        """
        return 0 <= x < self.width and 0 <= y < self.height and self.grid[y][x] == 0


# =============================================================================
# 3. 通道互斥鎖管理器 (Corridor Mutex Lock Manager)
# =============================================================================

class CorridorMutex:
    """
    【繁體中文】通道互斥鎖 (Mutex Manager)：
    如同單線鐵路橋樑上的紅綠燈，同一時間只允許「一輛 AGV」進入該通道。
    當第一輛車進入時拿到鎖 (acquire)，離開通道時釋放鎖 (release)。
    這能徹底防止兩台車在狹窄單行道上面對面卡死 (Deadlock)。

    [US English] Corridor Mutex Manager:
    Acts like a traffic signal for a single-track bridge, allowing only one AGV to enter
    a corridor at any time. The first vehicle acquires the lock upon entry and releases it
    upon exiting. This guarantees deadlock and collision prevention in narrow pathways.
    """

    def __init__(self):
        """
        【繁體中文】初始化鎖定狀態字典，Key 為走道 ID，Value 為目前持有的 AGV ID。
        [US English] Initializes lock dictionary: Key = Aisle ID, Value = Owner AGV ID.
        """
        self.locks: Dict[int, Optional[int]] = {}

    def is_locked_by_other(self, aisle_id: int, my_agv_id: int) -> bool:
        """
        【繁體中文】檢查此通道是否已被「其他車輛」鎖定。
        [US English] Checks if the corridor is locked by another AGV.
        """
        owner = self.locks.get(aisle_id)
        return owner is not None and owner != my_agv_id

    def acquire(self, aisle_id: int, my_agv_id: int) -> bool:
        """
        【繁體中文】嘗試取得通道鎖。若通道沒人使用或本來就是自己持有的，回傳 True；否則回傳 False。
        [US English] Attempts to acquire the lock. Returns True if free or already owned by caller.
        """
        owner = self.locks.get(aisle_id)
        if owner is None or owner == my_agv_id:
            self.locks[aisle_id] = my_agv_id
            return True
        return False

    def release(self, aisle_id: int, my_agv_id: int) -> None:
        """
        【繁體中文】釋放通道鎖，讓下一輛等待的車輛可以通行。
        [US English] Releases the corridor lock so waiting vehicles can enter.
        """
        if self.locks.get(aisle_id) == my_agv_id:
            self.locks[aisle_id] = None


# =============================================================================
# 4. A* 啟發式最短路徑演算法 (A* Shortest Path Planner)
# =============================================================================

class AStarPlanner:
    """
    【繁體中文】A* 尋路規劃器：
    A* 演算法的核心公式是：f(n) = g(n) + h(n)
    - g(n)：從起點走到目前格子已經花費的實際距離 (代價)。
    - h(n)：從目前格子到終點的「曼哈頓距離」預估值 (|x1 - x2| + |y1 - y2|)。
    - f(n)：總評估成本。每次從最小堆積 (Min-Heap) 挑出 f(n) 最小的格子擴展。
    本實作額外加入「轉彎懲罰 (Turn Penalty = 0.5)」，讓 AGV 傾向走直線，減少過度轉彎。

    [US English] A* Path Planner:
    The core formula of A* is: f(n) = g(n) + h(n)
    - g(n): Actual cost traveled from the start to the current cell.
    - h(n): Manhattan distance heuristic (|x1 - x2| + |y1 - y2|) to destination.
    - f(n): Total estimated cost. Always expands the lowest f(n) node via Min-Heap.
    This implementation adds a 'Turn Penalty (0.5)' to encourage straight lines over unnecessary turns.
    """

    @staticmethod
    def manhattan(p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        """
        【繁體中文】計算兩點之間的曼哈頓距離（只能沿著十字網格走的最短距離）。
        [US English] Computes Manhattan distance between two points on a grid.
        """
        return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

    @classmethod
    def find_path(
        cls,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        warehouse_map: WarehouseMap,
        dynamic_obstacles: Optional[Set[Tuple[int, int]]] = None
    ) -> List[Tuple[int, int]]:
        """
        【繁體中文】尋找從起點 (start) 到終點 (goal) 的最佳路徑。
        支援傳入動態障礙物 (例如其他停在路邊的車輛)，避免互相碰撞。

        [US English] Finds the optimal path from start to goal.
        Supports dynamic obstacles (e.g., stationary AGVs) to prevent collisions.
        """
        if start == goal:
            return [start]

        if dynamic_obstacles is None:
            dynamic_obstacles = set()

        # 優先佇列 (Min-Heap): 儲存項目 (f_score, counter, current_pos, direction, g_score)
        # Priority Queue (Min-Heap): stores (f_score, tie-breaker, current_pos, direction, g_score)
        counter = 0
        open_heap: List[Tuple[float, int, Tuple[int, int], Tuple[int, int], float]] = []
        heapq.heappush(open_heap, (cls.manhattan(start, goal), counter, start, (0, 0), 0.0))

        # 記錄走到每個格子的最低 g_score 與父節點 (用來回溯整條路徑)
        # Tracks lowest g_score and parent pointers to reconstruct final path
        g_scores: Dict[Tuple[int, int], float] = {start: 0.0}
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        visited: Set[Tuple[int, int]] = set()

        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # 下、上、右、左

        while open_heap:
            _, _, current, curr_dir, curr_g = heapq.heappop(open_heap)

            if current == goal:
                # 回溯重建路徑 (Reconstruct path from goal to start)
                path = [goal]
                curr_node = goal
                while curr_node in came_from:
                    curr_node = came_from[curr_node]
                    path.append(curr_node)
                path.reverse()
                return path

            if current in visited:
                continue
            visited.add(current)

            for dx, dy in directions:
                neighbor = (current[0] + dx, current[1] + dy)
                new_dir = (dx, dy)

                # 檢查是否可走或撞到障礙物 (Check walkable and obstacle clearance)
                if not warehouse_map.is_walkable(neighbor[0], neighbor[1]):
                    continue
                if neighbor in dynamic_obstacles and neighbor != goal:
                    continue

                # 基本移動代價 1.0；若轉向則增加 0.5 懲罰分 (Step cost 1.0 + Turn penalty 0.5)
                turn_cost = 0.5 if (curr_dir != (0, 0) and curr_dir != new_dir) else 0.0
                tentative_g = curr_g + 1.0 + turn_cost

                if neighbor not in g_scores or tentative_g < g_scores[neighbor]:
                    g_scores[neighbor] = tentative_g
                    f_score = tentative_g + cls.manhattan(neighbor, goal)
                    came_from[neighbor] = current
                    counter += 1
                    heapq.heappush(open_heap, (f_score, counter, neighbor, new_dir, tentative_g))

        # 若無路可走則回傳空列表 (Return empty list if unreachable)
        return []


# =============================================================================
# 5. 最佳化任務派工器 (Task Dispatcher)
# =============================================================================

class TaskDispatcher:
    """
    【繁體中文】任務派工器：
    當倉庫有新的搬運任務時，系統需要決定「派哪一台 AGV 去做」最有效率。
    評估公式為貪婪成本矩陣 (Greedy Cost Function)：
      總成本 = 距離成本 + 電量懲罰 ( (100 - 電量) * 2 )
    挑選總成本最小的閒置車輛前往，這樣既能保證就近接單，又不會讓快沒電的車累死。

    [US English] Task Dispatcher:
    When a new task arrives, the system selects the most cost-effective AGV.
    Evaluation Formula (Greedy Cost Function):
      Total Cost = Distance to Pickup + Battery Penalty ((100 - Battery) * 2)
    Assigns the task to the idle vehicle with the lowest cost, balancing proximity and energy reserves.
    """

    @staticmethod
    def assign_tasks(
        waiting_tasks: List[Task],
        agvs: List['AGV'],
        warehouse_map: WarehouseMap
    ) -> None:
        """
        【繁體中文】掃描等待中任務並配對給最適當的閒置車輛。
        [US English] Scans waiting tasks and pairs them with the best available idle AGVs.
        """
        for task in waiting_tasks:
            if task.status != "WAITING":
                continue

            pickup_pos = warehouse_map.stations[task.pickup]
            best_agv: Optional['AGV'] = None
            min_cost = float('inf')

            for agv in agvs:
                # 只有處於 IDLE (閒置) 的車輛才能接單
                # Only idle vehicles are eligible for new dispatches
                if agv.state != AGVState.IDLE:
                    continue

                # 預估取貨距離與電量代價 (Estimate distance and battery penalty)
                dist = AStarPlanner.manhattan((agv.x, agv.y), pickup_pos)
                battery_penalty = (100.0 - agv.battery) * 2.0
                total_cost = dist + battery_penalty

                if total_cost < min_cost:
                    min_cost = total_cost
                    best_agv = agv

            # 若找到合適車輛，指派任務 (Assign task if vehicle is found)
            if best_agv is not None:
                task.status = "IN_PROGRESS"
                best_agv.assign_task(task, warehouse_map)


# =============================================================================
# 6. AGV 無人搬運車主體 (AGV Entity)
# =============================================================================

class AGV:
    """
    【繁體中文】AGV 自走車類別：
    包含車輛的座標、電池電量、當前任務、路徑追蹤與狀態切換邏輯。
    具備「通道互斥判斷」與「智慧避讓 (Yielding)」機制。

    [US English] AGV Vehicle Class:
    Encapsulates vehicle position, battery level, current task, route tracking, and state transitions.
    Includes corridor mutex handling and intelligent yielding mechanisms.
    """

    def __init__(self, agv_id: int, start_x: int, start_y: int, color: str):
        """
        【繁體中文】初始化 AGV 的基本屬性與外觀顏色。
        [US English] Initializes basic AGV attributes and visual display color.
        """
        self.id = agv_id
        self.x = start_x
        self.y = start_y
        self.color = color
        self.battery = 100.0
        self.state = AGVState.IDLE
        self.current_task: Optional[Task] = None
        self.path: List[Tuple[int, int]] = []
        self.path_index = 0
        self.wait_counter = 0

    def assign_task(self, task: Task, warehouse_map: WarehouseMap) -> None:
        """
        【繁體中文】接收新任務，並使用 A* 規劃前往「取貨站」的第一段路徑。
        [US English] Receives a new task and plans the first route to the pickup station using A*.
        """
        self.current_task = task
        self.state = AGVState.MOVING_TO_PICKUP
        pickup_pos = warehouse_map.stations[task.pickup]
        self.path = AStarPlanner.find_path((self.x, self.y), pickup_pos, warehouse_map)
        self.path_index = 0

    def step(
        self,
        warehouse_map: WarehouseMap,
        mutex: CorridorMutex,
        all_agvs: List['AGV']
    ) -> None:
        """
        【繁體中文】單一時間步 (Time-Step) 狀態機推進邏輯：
        處理充電、裝卸貨等待、通道互斥防撞、避讓與路徑移動。

        [US English] Single time-step state machine transition:
        Handles charging, loading/unloading delays, corridor mutex safety, yielding, and path movement.
        """
        # 1. 充電狀態處理 (Charging State Handling)
        if self.state == AGVState.CHARGING:
            self.battery = min(100.0, self.battery + 10.0)
            if self.battery >= 100.0:
                self.state = AGVState.IDLE
            return

        # 2. 裝卸貨狀態模擬 (Loading / Unloading Delay Handling)
        if self.state == AGVState.LOADING:
            self.state = AGVState.MOVING_TO_DELIVERY
            delivery_pos = warehouse_map.stations[self.current_task.delivery]
            self.path = AStarPlanner.find_path((self.x, self.y), delivery_pos, warehouse_map)
            self.path_index = 0
            return

        if self.state == AGVState.UNLOADING:
            self.current_task.status = "COMPLETED"
            self.current_task = None
            self.state = AGVState.IDLE
            # 檢查低電量回充 (Check if low battery requires returning to charger)
            if self.battery < 30.0:
                self.state = AGVState.MOVING_TO_CHARGE
                self.path = AStarPlanner.find_path((self.x, self.y), warehouse_map.charger, warehouse_map)
                self.path_index = 0
            return

        # 3. 閒置狀態 (Idle State)
        if self.state == AGVState.IDLE or not self.path:
            return

        # 4. 到達路徑終點檢查 (Check Arrival at Path End)
        if self.path_index >= len(self.path) - 1:
            curr_aisle = warehouse_map.aisle_map[self.y][self.x]
            if curr_aisle > 0:
                mutex.release(curr_aisle, self.id)

            if self.state == AGVState.MOVING_TO_PICKUP:
                self.state = AGVState.LOADING
            elif self.state == AGVState.MOVING_TO_DELIVERY:
                self.state = AGVState.UNLOADING
            elif self.state == AGVState.MOVING_TO_CHARGE:
                self.state = AGVState.CHARGING
            elif self.state == AGVState.YIELDING:
                self.state = AGVState.IDLE
            return

        # 5. 移動至下一個格子 (Move to Next Step)
        next_pos = self.path[self.path_index + 1]
        next_aisle = warehouse_map.aisle_map[next_pos[1]][next_pos[0]]
        curr_aisle = warehouse_map.aisle_map[self.y][self.x]

        # 5a. 通道鎖定檢查：準備進入新通道時，嘗試獲取互斥鎖
        # 5a. Corridor Mutex Check: Try acquiring lock before entering a new aisle
        if next_aisle > 0 and next_aisle != curr_aisle:
            if not mutex.acquire(next_aisle, self.id):
                # 通道被其他車佔用，進行智慧避讓等待 (Corridor occupied: yield and wait)
                self.wait_counter += 1
                if self.wait_counter > 2:
                    # 重新規劃避讓路徑 (Dynamic replanning to bypass)
                    other_positions = {(a.x, a.y) for a in all_agvs if a.id != self.id}
                    goal = self.path[-1]
                    new_path = AStarPlanner.find_path((self.x, self.y), goal, warehouse_map, other_positions)
                    if new_path:
                        self.path = new_path
                        self.path_index = 0
                        self.wait_counter = 0
                return

        # 5b. 防撞檢查：避免撞上同一格的其他車輛
        # 5b. Collision Check: Avoid occupying the same cell as another vehicle
        is_blocked = any(a.id != self.id and a.x == next_pos[0] and a.y == next_pos[1] for a in all_agvs)
        if is_blocked:
            self.wait_counter += 1
            if self.wait_counter > 2:
                # 重新規劃繞道 (Replanning detour)
                other_positions = {(a.x, a.y) for a in all_agvs if a.id != self.id}
                goal = self.path[-1]
                new_path = AStarPlanner.find_path((self.x, self.y), goal, warehouse_map, other_positions)
                if new_path:
                    self.path = new_path
                    self.path_index = 0
                    self.wait_counter = 0
            return

        # 順利前進一格 (Step forward successfully)
        self.wait_counter = 0
        if curr_aisle > 0 and next_aisle != curr_aisle:
            mutex.release(curr_aisle, self.id)

        self.path_index += 1
        self.x, self.y = next_pos
        self.battery = max(0.0, self.battery - 0.2)


# =============================================================================
# 7. 離線模擬器 (Warehouse Discrete-Event Simulation Engine)
# =============================================================================

class WarehouseSimulation:
    """
    【繁體中文】離線模擬核心引擎：
    負責按照時間步 (Step = 0, 1, 2, ..., T) 依序推進整個倉儲系統。
    在每一個時間步中：
    1. 產生/發布新搬運任務
    2. 任務調度派工
    3. 各台 AGV 狀態更新與移動
    4. 記錄完整的歷史快照 (Snapshot)，以供 Plotly 生成逐幀動畫。

    [US English] Warehouse Offline Simulation Engine:
    Advances the entire warehouse system discrete step-by-step (Step = 0, 1, ..., T).
    In each time step:
    1. Generates / queues new transport tasks
    2. Dispatches tasks to available AGVs
    3. Updates individual AGV states and coordinates
    4. Records comprehensive snapshots for Plotly frame-by-frame animation.
    """

    def __init__(self, total_steps: int = 80):
        """
        【繁體中文】初始化模擬器，建立地圖、車隊與任務佇列。
        [US English] Initializes simulator: creates map, AGV fleet, and task queue.
        """
        self.total_steps = total_steps
        self.map = WarehouseMap(width=24, height=16)
        self.mutex = CorridorMutex()

        # 建立 3 台初始 AGV (Create 3 initial AGVs)
        self.agvs: List[AGV] = [
            AGV(agv_id=1, start_x=1, start_y=1, color="#38bdf8"),   # 亮天藍 (Sky Blue)
            AGV(agv_id=2, start_x=11, start_y=1, color="#34d399"),  # 薄荷綠 (Emerald Green)
            AGV(agv_id=3, start_x=22, start_y=1, color="#fbbf24"),  # 亮金黃 (Amber Yellow)
        ]

        # 任務佇列 (Task Queue)
        self.tasks: List[Task] = [
            Task(task_id=1, pickup="A", delivery="D"),
            Task(task_id=2, pickup="B", delivery="C"),
            Task(task_id=3, pickup="C", delivery="B"),
            Task(task_id=4, pickup="D", delivery="A"),
            Task(task_id=5, pickup="A", delivery="C"),
            Task(task_id=6, pickup="B", delivery="D"),
        ]

        # 歷史記錄快照 (History records per step)
        self.history: List[Dict] = []

    def run(self) -> None:
        """
        【繁體中文】執行整場離線模擬，步進記錄每時刻狀態。
        [US English] Runs the offline simulation and logs step-by-step records.
        """
        for step in range(self.total_steps):
            # 派工 (Task Dispatching)
            TaskDispatcher.assign_tasks(self.tasks, self.agvs, self.map)

            # 各車執行一步 (Step each AGV)
            for agv in self.agvs:
                agv.step(self.map, self.mutex, self.agvs)

            # 記錄此時間步快照 (Record snapshot of current step)
            snapshot = {
                "step": step,
                "completed_tasks": sum(1 for t in self.tasks if t.status == "COMPLETED"),
                "agv_data": [
                    {
                        "id": agv.id,
                        "x": agv.x,
                        "y": agv.y,
                        "color": agv.color,
                        "state": agv.state.value,
                        "battery": round(agv.battery, 1),
                        "task_info": f"{agv.current_task.pickup} ➔ {agv.current_task.delivery}" if agv.current_task else "無任務 (None)",
                        "path": list(agv.path[agv.path_index:]) if agv.path else []
                    }
                    for agv in self.agvs
                ]
            }
            self.history.append(snapshot)


# =============================================================================
# 8. Plotly 互動式動畫圖表生成器 (Plotly Visualizer)
# =============================================================================

def build_plotly_figure(sim: WarehouseSimulation, output_html: str = "agv_simulation.html") -> None:
    """
    【繁體中文】使用 Plotly 建立互動式倉儲動畫圖表：
    1. 繪製棋盤地圖、貨架障礙物、工作站與充電站圖示。
    2. 將每個模擬時間步包裝為 Plotly 動畫幀 (Frames)。
    3. 配置「播放 / 暫停按鈕」與「時間軸滑桿 (Slider)」，方便逐幀檢視演算法決策。
    4. 輸出成乾淨簡潔的獨立 HTML 檔案。

    [US English] Builds an interactive Plotly warehouse animation:
    1. Renders grid board, shelf obstacles, workstations, and charging station icons.
    2. Packages each simulation time step into Plotly animation frames.
    3. Configures 'Play / Pause buttons' and an interactive 'Time Slider' for inspecting decisions.
    4. Exports to a standalone, portable HTML file.
    """
    w_map = sim.map
    fig = go.Figure()

    # --- 1. 繪製貨架障礙物 (Draw Shelf Obstacles as Rectangular Shapes) ---
    shapes = []
    # 網格邊界 (Grid Border)
    shapes.append(dict(
        type="rect", x0=-0.5, y0=-0.5, x1=w_map.width - 0.5, y1=w_map.height - 0.5,
        line=dict(color="#475569", width=2), fillcolor="#0f172a"  # 深藍黑背景
    ))

    # 貨架矩形 (Shelves)
    for y in range(w_map.height):
        for x in range(w_map.width):
            if w_map.grid[y][x] == 1:
                shapes.append(dict(
                    type="rect",
                    x0=x - 0.45, y0=y - 0.45, x1=x + 0.45, y1=y + 0.45,
                    line=dict(color="#334155", width=1),
                    fillcolor="#1e293b"  # 貨架深灰色
                ))
            elif w_map.aisle_map[y][x] > 0:
                # 走道微光效果 (Subtle glow for narrow corridors)
                shapes.append(dict(
                    type="rect",
                    x0=x - 0.48, y0=y - 0.48, x1=x + 0.48, y1=y + 0.48,
                    line=dict(color="rgba(168, 85, 247, 0.2)", width=1),
                    fillcolor="rgba(168, 85, 247, 0.08)"
                ))

    # --- 2. 固定圖層：工作站與充電樁 (Static Layer: Stations and Charger) ---
    station_x = [pos[0] for pos in w_map.stations.values()]
    station_y = [pos[1] for pos in w_map.stations.values()]
    station_names = [f"站點 {k}<br>Station {k}" for k in w_map.stations.keys()]

    fig.add_trace(go.Scatter(
        x=station_x, y=station_y,
        mode="markers+text",
        marker=dict(size=24, color="#f59e0b", symbol="square", line=dict(color="#ffffff", width=2)),
        text=[f"<b>{k}</b>" for k in w_map.stations.keys()],
        textposition="middle center",
        textfont=dict(color="#000000", size=12, family="Arial Black"),
        hovertext=station_names,
        hoverinfo="text",
        name="工作站 (Stations)"
    ))

    fig.add_trace(go.Scatter(
        x=[w_map.charger[0]], y=[w_map.charger[1]],
        mode="markers+text",
        marker=dict(size=26, color="#10b981", symbol="diamond", line=dict(color="#ffffff", width=2)),
        text=["⚡"],
        textposition="middle center",
        textfont=dict(color="#ffffff", size=14),
        hovertext=["充電站 (Charging Station)"],
        hoverinfo="text",
        name="充電站 (Charger)"
    ))

    # --- 3. 初始幀的 AGV 軌跡與位置 (Initial AGV Traces for Step 0) ---
    step_0 = sim.history[0]
    for agv in step_0["agv_data"]:
        # 規劃路徑虛線 (Planned Path line)
        px = [p[0] for p in agv["path"]]
        py = [p[1] for p in agv["path"]]
        fig.add_trace(go.Scatter(
            x=px, y=py,
            mode="lines",
            line=dict(color=agv["color"], width=2, dash="dot"),
            opacity=0.6,
            name=f"AGV #{agv['id']} 預定路徑 (Route)",
            hoverinfo="skip"
        ))

        # AGV 車輛本體 (Vehicle Marker)
        hover_str = (
            f"<b>AGV #{agv['id']}</b><br>"
            f"座標 (Coord): ({agv['x']}, {agv['y']})<br>"
            f"狀態 (State): {agv['state']}<br>"
            f"電量 (Battery): {agv['battery']}%<br>"
            f"任務 (Task): {agv['task_info']}"
        )
        fig.add_trace(go.Scatter(
            x=[agv["x"]], y=[agv["y"]],
            mode="markers+text",
            marker=dict(size=22, color=agv["color"], line=dict(color="#ffffff", width=2)),
            text=[f"#{agv['id']}"],
            textposition="middle center",
            textfont=dict(color="#000000", size=10, family="Arial Black"),
            hovertext=[hover_str],
            hoverinfo="text",
            name=f"AGV #{agv['id']}"
        ))

    # --- 4. 建立動畫幀 (Build Animation Frames) ---
    frames = []
    for snapshot in sim.history:
        step_idx = snapshot["step"]
        frame_traces = []

        for agv in snapshot["agv_data"]:
            # 更新規劃路徑 (Update Planned Path)
            px = [p[0] for p in agv["path"]]
            py = [p[1] for p in agv["path"]]
            frame_traces.append(go.Scatter(
                x=px, y=py,
                mode="lines",
                line=dict(color=agv["color"], width=2, dash="dot"),
                opacity=0.6
            ))

            # 更新 AGV 座標與 Hover 資訊 (Update AGV Pos & Tooltip)
            hover_str = (
                f"<b>AGV #{agv['id']}</b><br>"
                f"座標 (Coord): ({agv['x']}, {agv['y']})<br>"
                f"狀態 (State): {agv['state']}<br>"
                f"電量 (Battery): {agv['battery']}%<br>"
                f"任務 (Task): {agv['task_info']}"
            )
            frame_traces.append(go.Scatter(
                x=[agv["x"]], y=[agv["y"]],
                mode="markers+text",
                marker=dict(size=22, color=agv["color"], line=dict(color="#ffffff", width=2)),
                text=[f"#{agv['id']}"],
                textposition="middle center",
                textfont=dict(color="#000000", size=10, family="Arial Black"),
                hovertext=[hover_str]
            ))

        frame = go.Frame(
            data=frame_traces,
            name=f"step_{step_idx}",
            # 只有後續 traces 需要更新 (從 index 2 開始是 AGV 圖層)
            traces=list(range(2, 2 + len(snapshot["agv_data"]) * 2)),
            layout=go.Layout(
                annotations=[
                    dict(
                        x=0.02, y=1.06, xref="paper", yref="paper",
                        text=f"<b>時間步 (Step):</b> {step_idx}/{sim.total_steps - 1} | "
                             f"<b>已完成任務 (Completed Tasks):</b> {snapshot['completed_tasks']}",
                        showarrow=False,
                        font=dict(color="#e2e8f0", size=14)
                    )
                ]
            )
        )
        frames.append(frame)

    fig.frames = frames

    # --- 5. 播放按鈕與滑桿控制項 (Play/Pause Buttons & Timeline Slider) ---
    slider_steps = []
    for step_idx in range(len(sim.history)):
        slider_steps.append({
            "args": [[f"step_{step_idx}"], {
                "frame": {"duration": 180, "redraw": True},
                "mode": "immediate",
                "transition": {"duration": 0}
            }],
            "label": str(step_idx),
            "method": "animate"
        })

    updatemenus = [dict(
        type="buttons",
        showactive=False,
        x=0.02, y=-0.12, xanchor="left", yanchor="top",
        pad={"r": 10, "t": 10},
        buttons=[
            dict(
                label="▶ 播放 (Play)",
                method="animate",
                args=[None, {
                    "frame": {"duration": 180, "redraw": True},
                    "fromcurrent": True,
                    "transition": {"duration": 0}
                }]
            ),
            dict(
                label="⏸ 暫停 (Pause)",
                method="animate",
                args=[[None], {
                    "frame": {"duration": 0, "redraw": False},
                    "mode": "immediate",
                    "transition": {"duration": 0}
                }]
            )
        ]
    )]

    sliders = [dict(
        active=0,
        yanchor="top", xanchor="left",
        currentvalue={
            "font": {"size": 13, "color": "#94a3b8"},
            "prefix": "時間進度 (Time Step): ",
            "visible": True,
            "xanchor": "right"
        },
        transition={"duration": 0},
        pad={"b": 10, "t": 40},
        len=0.88, x=0.10, y=-0.10,
        steps=slider_steps
    )]

    # --- 6. 整體版面樣式 (Layout and Styling) ---
    fig.update_layout(
        title={
            "text": "<b>AGV 智慧物流倉儲調度模擬 (AGV Smart Warehouse Simulation)</b><br>"
                    "<sup>演算法展示：A* 最短路徑尋路 · BFS 走道辨識 · 通道互斥鎖避死鎖 · 貪婪最佳化派工</sup>",
            "x": 0.5, "xanchor": "center",
            "font": {"color": "#f8fafc", "size": 18}
        },
        paper_bgcolor="#0b0f19",
        plot_bgcolor="#0f172a",
        shapes=shapes,
        xaxis=dict(
            range=[-1, w_map.width],
            showgrid=True, gridcolor="#1e293b",
            zeroline=False, dtick=1,
            tickfont=dict(color="#64748b", size=10),
            scaleanchor="y", scaleratio=1
        ),
        yaxis=dict(
            range=[-1, w_map.height],
            showgrid=True, gridcolor="#1e293b",
            zeroline=False, dtick=1,
            tickfont=dict(color="#64748b", size=10)
        ),
        updatemenus=updatemenus,
        sliders=sliders,
        legend=dict(
            font=dict(color="#cbd5e1", size=11),
            bgcolor="rgba(15, 23, 42, 0.8)",
            bordercolor="#334155", borderwidth=1,
            x=1.02, y=1, xanchor="left", yanchor="top"
        ),
        margin=dict(l=40, r=40, t=80, b=100),
        annotations=[
            dict(
                x=0.02, y=1.06, xref="paper", yref="paper",
                text="<b>時間步 (Step):</b> 0/79 | <b>已完成任務 (Completed Tasks):</b> 0",
                showarrow=False,
                font=dict(color="#e2e8f0", size=14)
            )
        ],
        width=1100,
        height=750
    )

    # 輸出獨立 HTML 檔案 (Export to Standalone HTML)
    fig.write_html(output_html)
    print(f"✅ 模擬完成！互動式 HTML 已成功輸出至：{output_html}")


# =============================================================================
# 9. 主程式進入點 (Main Entry Point)
# =============================================================================

if __name__ == "__main__":
    print("🚀 開始執行 AGV 倉儲離線模擬 (Running AGV Warehouse Offline Simulation)...")
    sim = WarehouseSimulation(total_steps=80)
    sim.run()
    build_plotly_figure(sim, output_html="agv_simulation.html")

