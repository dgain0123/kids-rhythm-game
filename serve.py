#!/usr/bin/env python3
"""本機伺服器：強制不快取，改檔後普通重整就能看到最新版(不用清快取)。"""
import http.server
import socketserver

PORT = 8770


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), NoCacheHandler) as httpd:
        print(f"🥁 幼兒節奏遊戲(禁快取) http://localhost:{PORT}")
        httpd.serve_forever()
