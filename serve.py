#!/usr/bin/env python3
"""本機伺服器：強制不快取 + 多執行緒 + IPv4/IPv6 雙棧。

雙棧很重要：Safari 連 localhost 會先試 IPv6(::1)，只聽 IPv4 的伺服器
會讓它轉圈直到逾時，看起來像「網頁開不起來」(2026-07-28 踩過)。"""
import http.server
import socket

PORT = 8770


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, *args):
        pass  # 安靜一點


class DualStackServer(http.server.ThreadingHTTPServer):
    """IPv6 socket + 關掉 V6ONLY → 同時接受 ::1 與 127.0.0.1。"""
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


if __name__ == "__main__":
    # ThreadingHTTPServer：每個連線各自一條執行緒，避免單執行緒被 keep-alive 連線卡死
    server = DualStackServer(("::", PORT), NoCacheHandler)
    server.daemon_threads = True
    print(f"🥁 幼兒節奏遊戲(禁快取·多執行緒·雙棧) http://localhost:{PORT}")
    server.serve_forever()
