#!/usr/bin/env python3
"""本機伺服器：強制不快取 + 多執行緒(可同時處理多個請求，瀏覽器不會卡住)。"""
import http.server

PORT = 8770


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, *args):
        pass  # 安靜一點


if __name__ == "__main__":
    # ThreadingHTTPServer：每個連線各自一條執行緒，避免單執行緒被 keep-alive 連線卡死
    server = http.server.ThreadingHTTPServer(("", PORT), NoCacheHandler)
    server.daemon_threads = True
    print(f"🥁 幼兒節奏遊戲(禁快取·多執行緒) http://localhost:{PORT}")
    server.serve_forever()
