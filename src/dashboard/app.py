"""Servidor local: python -m src.dashboard.app [--port 8501]."""
import argparse
from datetime import date,datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import logging
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import duckdb
from .consultas import analisar,opcoes

STATIC=Path(__file__).parent/'static'


def serializar(valor):
    if isinstance(valor,Decimal):
        return float(valor)
    if isinstance(valor,(date,datetime)):
        return valor.isoformat()
    raise TypeError(type(valor).__name__)


class Handler(BaseHTTPRequestHandler):
    def responder(self,status,conteudo,tipo):
        self.send_response(status)
        self.send_header('Content-Type',tipo)
        self.send_header('Content-Length',str(len(conteudo)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(conteudo)

    def do_GET(self):
        url=urlparse(self.path)
        try:
            if url.path=='/api/opcoes':
                resultado=opcoes()
            elif url.path=='/api/painel':
                args=parse_qs(url.query)
                resultado=analisar(args.get('inicio',[''])[0],args.get('fim',[''])[0],args.get('uf',['Todas'])[0])
            else:
                arquivo={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(url.path)
                if arquivo is None:
                    self.responder(404,b'Nao encontrado','text/plain; charset=utf-8')
                    return
                mime={'index.html':'text/html','app.js':'text/javascript','style.css':'text/css'}[arquivo]
                self.responder(200,(STATIC/arquivo).read_bytes(),mime+'; charset=utf-8')
                return
            self.responder(200,json.dumps(resultado,default=serializar,ensure_ascii=False,allow_nan=False).encode('utf-8'),'application/json; charset=utf-8')
        except (ValueError,FileNotFoundError) as erro:
            self.responder(400,json.dumps({'erro':str(erro)},ensure_ascii=False).encode('utf-8'),'application/json; charset=utf-8')
        except duckdb.Error:
            logging.exception('Falha ao consultar o DW')
            self.responder(503,json.dumps({'erro':'Não foi possível consultar o DW. Confira a carga Gold e tente novamente.'},ensure_ascii=False).encode('utf-8'),'application/json; charset=utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8501)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    servidor=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Dashboard: http://127.0.0.1:{args.port}',flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__=='__main__':
    main()
