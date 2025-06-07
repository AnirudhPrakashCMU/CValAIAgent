import http.server
import socketserver
import threading
import webbrowser
import matplotlib.pyplot as plt

PORT = 8000

def serve():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("localhost", PORT), handler) as httpd:
        httpd.serve_forever()

thread = threading.Thread(target=serve, daemon=True)
thread.start()
webbrowser.open(f"http://localhost:{PORT}/examples/index.html")

plt.bar(["A","B","C","D"], [12,19,3,5])
plt.title("Example Data")
plt.show()
