"""Gateway interno de inferência. Nenhum token Notion/Telegram ou banco montado aqui."""
import os,json,secrets,tempfile,subprocess,signal
from pathlib import Path
from http.server import BaseHTTPRequestHandler,HTTPServer
SCHEMA={'type':'object','properties':{'text':{'type':'string'},'calls':{'type':'array','items':{'type':'object','properties':{'name':{'type':'string','enum':['context','query','page','notice','week_plan']},'args_json':{'type':'string'}},'required':['name','args_json'],'additionalProperties':False}}},'required':['text','calls'],'additionalProperties':False}

def infer(prompt):
    with tempfile.TemporaryDirectory(prefix='secretaria-',dir='/tmp') as tmp:
        schema=Path(tmp)/'schema.json';output=Path(tmp)/'result.json';schema.write_text(json.dumps(SCHEMA))
        command=['codex','exec','--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-c','approval_policy="never"','-c','web_search="disabled"','--disable','shell_tool','--disable','unified_exec','--disable','code_mode_host','--disable','apps','--disable','browser_use','--disable','computer_use','--output-schema',str(schema),'-o',str(output),'-']
        if os.getenv('CODEX_MODEL'):command[2:2]=['--model',os.environ['CODEX_MODEL']]
        env={k:v for k,v in os.environ.items() if k in ['PATH','HOME','CODEX_HOME','LANG','TZ','SSL_CERT_FILE']}
        child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,cwd=tmp,env=env,start_new_session=True)
        try:stdout,stderr=child.communicate(prompt,timeout=180)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL);child.communicate();raise RuntimeError('Codex excedeu o tempo; verifique login/limites.')
        if child.returncode or not output.exists():raise RuntimeError('Codex não respondeu. Verifique login, limites e compatibilidade da versão instalada.')
        result=json.loads(output.read_text())
        if not isinstance(result.get('text'),str) or not isinstance(result.get('calls'),list) or len(result['calls'])>4:raise RuntimeError('Resposta estruturada inválida.')
        return result

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.send_response(200);self.end_headers();self.wfile.write(b'{"status":"ok"}')
    def do_POST(self):
        expected=os.environ.get('ASSISTANT_GATEWAY_KEY','')
        if not expected or not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+expected):self.send_error(403);return
        size=int(self.headers.get('Content-Length','0'))
        if size<=0 or size>200000:self.send_error(413);return
        try:
            data=json.loads(self.rfile.read(size));result=infer(data['prompt'])
        except Exception:
            self.send_error(503,'Codex indisponivel; verificar autenticacao e limites');return
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(result,ensure_ascii=False).encode())
if __name__=='__main__':HTTPServer(('0.0.0.0',8001),Handler).serve_forever()
