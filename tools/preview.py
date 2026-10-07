"""Serve the generated Pages build locally, including its project base path."""
import argparse
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--port',type=int,default=8794);a=p.parse_args()
    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self,path):
            if urlsplit(path).path.startswith('/starrail-quests/'):
                path=path[len('/starrail-quests'):]
            return super().translate_path(path)
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(a.root.resolve()),**kwargs)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
if __name__=='__main__':main()
