import http.server
import socketserver
import subprocess
import json
import os
import sys

PORT = 8000
DIRECTORY = "."

class VTSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/generate_report':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {}
            try:
                # Execute the tool script
                # Assuming python is in path
                print("Running generation tool...")
                result = subprocess.run(
                    [sys.executable, "tools/generate_ra12.py"], 
                    capture_output=True, 
                    text=True,
                    cwd=os.getcwd()
                )
                
                if result.returncode == 0:
                    response = {
                        "status": "success", 
                        "message": "Report generated successfully.",
                        "file_url": "../data/output/RA_12_Compliance_Report.csv" # Relative to UI path if UI is at /ui/
                        # Note: If accessing from /ui/index.html, path to data needs to be correct.
                        # SimpleHTTPRequestHandler serves from DIRECTORY.
                        # If index.html is loaded from /ui/index.html, then ../data/ is correct relative to UI?
                        # Wait, URL resolution in browser: 
                        # Page: http://localhost:8000/ui/index.html
                        # Link: ../data/output/... -> http://localhost:8000/data/output/...
                        # This works if data is in root/data.
                    }
                else:
                    response = {
                        "status": "error", 
                        "message": f"Script execution failed: {result.stderr}"
                    }
            except Exception as e:
                response = {"status": "error", "message": str(e)}
            
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_error(404, "API endpoint not found")

if __name__ == "__main__":
    # Ensure tool exists
    if not os.path.exists("tools/generate_ra12.py"):
        print("Warning: tools/generate_ra12.py not found.")

    with socketserver.TCPServer(("", PORT), VTSRequestHandler) as httpd:
        print(f"Serving VTS at http://localhost:{PORT}/ui/index.html")
        httpd.serve_forever()
