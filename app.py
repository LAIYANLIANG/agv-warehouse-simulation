"""
=============================================================================
AGV 智慧物流倉儲調度模擬系統 - Python 伺服器啟動器
AGV Smart Warehouse Simulation - Python Local Server Launcher
=============================================================================
【繁體中文說明】：
此腳本使用 Python 標準函式庫中的 HTTP 伺服器，自動在本地端啟動服務並開啟瀏覽器，
以完整的 60 FPS Canvas 動畫、即時車隊儀表板與日誌呈現 AGV 模擬成果。
可透過終端機執行：python3 app.py

[US English Description]:
This script uses Python's built-in HTTP server to host the full interactive
smart warehouse simulation dashboard (60 FPS Canvas, real-time fleet table & event log).
Run from terminal: python3 app.py
=============================================================================
"""

import http.server
import socketserver
import webbrowser
import threading
import time
import os
import socket


def find_free_port(default_port: int = 8080) -> int:
    """
    【繁體中文】尋找可用的網路連接埠 (Port)。
    [US English] Finds an available network port.
    """
    for port in range(default_port, default_port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    return default_port


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    port = find_free_port(8080)
    handler = http.server.SimpleHTTPRequestHandler

    # 抑制一般靜態檔案的存取 log，保持終端機乾淨
    # Suppress routine static asset access logs to keep terminal output clean
    handler.log_message = lambda self, format, *args: None

    print("=" * 70)
    print("🚀 【AGV 智慧物流演示系統】正在啟動...")
    print("🚀 [AGV Smart Warehouse Simulation] Starting local server...")
    print(f"👉 本地網址 (Local URL): http://localhost:{port}/index.html")
    print("=" * 70)

    httpd = socketserver.TCPServer(("", port), handler)

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    time.sleep(0.5)
    url = f"http://localhost:{port}/index.html"
    print(f"🌐 自動開啟瀏覽器中：{url}")
    print("💡 按下 Ctrl + C 可隨時停止伺服器 (Press Ctrl+C to stop).")
    webbrowser.open(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 伺服器已安全停止 (Server stopped successfully).")
        httpd.shutdown()


if __name__ == "__main__":
    main()

