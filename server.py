"""
Servidor web simples para o dashboard.
Roda na mesma instância do Railway junto com o bot.
"""
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

DASHBOARD_HTML = open(os.path.join(os.path.dirname(__file__), 'dashboard.html')).read()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'ok')
            return

        html = DASHBOARD_HTML\
            .replace('UPSTASH_REDIS_REST_URL_PLACEHOLDER', os.getenv('UPSTASH_REDIS_REST_URL',''))\
            .replace('UPSTASH_REDIS_REST_TOKEN_PLACEHOLDER', os.getenv('UPSTASH_REDIS_REST_TOKEN',''))

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, *args): pass

def start_server():
    port = int(os.getenv('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f'Dashboard rodando na porta {port}')
    server.serve_forever()

if __name__ == '__main__':
    start_server()
