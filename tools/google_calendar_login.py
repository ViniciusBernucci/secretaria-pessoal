"""Execute no Mac, não na VPS. OAuth oficial com app Desktop e callback local."""
import getpass,secrets,json,os,webbrowser
from urllib.parse import urlencode,urlparse,parse_qs
from urllib.request import Request,urlopen
from http.server import HTTPServer,BaseHTTPRequestHandler
client=input('Google OAuth Client ID (tipo Desktop): ').strip()
secret=getpass.getpass('Google OAuth Client Secret: ')
state=secrets.token_urlsafe(32);callback='http://127.0.0.1:8765/';result={}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        args=parse_qs(urlparse(self.path).query)
        if args.get('state',[''])[0]!=state:self.send_error(403);return
        result.update(args)
        self.send_response(200);self.end_headers();self.wfile.write(b'Autorizacao recebida. Volte ao terminal.')
server=HTTPServer(('127.0.0.1',8765),Handler);server.timeout=300
url='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':client,'redirect_uri':callback,'response_type':'code','scope':'https://www.googleapis.com/auth/calendar.events','access_type':'offline','prompt':'consent','state':state})
print('Abra este link somente no seu navegador local:');print(url);webbrowser.open(url)
server.handle_request();server.server_close()
if 'code' not in result:raise SystemExit('Autorização não concluída. Nenhum segredo salvo.')
try:
    body=urlencode({'client_id':client,'client_secret':secret,'redirect_uri':callback,'code':result['code'][0],'grant_type':'authorization_code'}).encode()
    with urlopen(Request('https://oauth2.googleapis.com/token',data=body),timeout=30) as r:token=json.load(r)
except Exception:raise SystemExit('Troca de autorização falhou; nenhum token exibido.')
if not token.get('refresh_token'):raise SystemExit('Não retornou refresh token; revisar consentimento offline.')
path='google-calendar.env'
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write('GOOGLE_CLIENT_ID='+client+'\nGOOGLE_CLIENT_SECRET='+secret+'\nGOOGLE_REFRESH_TOKEN='+token['refresh_token']+'\n')
print('Credenciais salvas em google-calendar.env (privado). Copie os valores para o .env da VPS sem enviá-los ao chat.')
