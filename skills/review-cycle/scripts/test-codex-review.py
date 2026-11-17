"""Catch dropped reviewer instructions, diff output, or truncated review results.

Run explicitly with Python and Codex installed; all inputs and the provider are
disposable local fixtures, and the provider returns scripted responses.
"""

import http.server, json, os, pathlib, subprocess, tempfile, threading, time
root=pathlib.Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix='codex-review-fixture-') as tmp:
 p=pathlib.Path(tmp); home=p/'home'; home.mkdir(mode=0o700); ch=home/'.codex'; ch.mkdir(); work=p/'work'; work.mkdir()
 env={'HOME':str(home),'CODEX_HOME':str(ch),'PATH':os.environ['PATH'],'LANG':'C.UTF-8','NO_PROXY':'127.0.0.1,localhost','no_proxy':'127.0.0.1,localhost','HTTPS_PROXY':'http://127.0.0.1:1','HTTP_PROXY':'http://127.0.0.1:1','ALL_PROXY':'http://127.0.0.1:1','GIT_AUTHOR_NAME':'Fixture','GIT_AUTHOR_EMAIL':'fixture@example.invalid','GIT_COMMITTER_NAME':'Fixture','GIT_COMMITTER_EMAIL':'fixture@example.invalid'}
 def git(*args, input=None): return subprocess.run(['git',*args],cwd=work,env=env,input=input,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout.strip()
 git('init','-q','-b','master'); (work/'sample.txt').write_text('before\n'); git('add','sample.txt'); tree=git('write-tree'); base=git('commit-tree',tree,input='fixture base\n'); git('update-ref','refs/heads/master',base); git('checkout','-q','-b','feature'); (work/'sample.txt').write_text('after\n'); git('add','sample.txt'); tree=git('write-tree'); head=git('commit-tree',tree,'-p',base,input='fixture head\n'); git('update-ref','refs/heads/feature',head); assert 'after' in git('diff','master...HEAD')
 captured=[]
 class Handler(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args): pass
  def do_POST(self):
   data=json.loads(self.rfile.read(int(self.headers['Content-Length']))); captured.append(data)
   if len(captured)==1:
    item={'type':'function_call','id':'fc1','call_id':'call1','name':'exec_command','arguments':json.dumps({'cmd':'git diff master...HEAD'})}
   else:
    item={'id':'message-fixture','type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':'First finding.\nSecond finding.','annotations':[]}]}
   response={'id':'resp-fixture'+str(len(captured)),'object':'response','created_at':int(time.time()),'status':'completed','model':'fixture','output':[item],'parallel_tool_calls':True,'usage':{'input_tokens':10,'output_tokens':10,'total_tokens':20}}
   body='event: response.created\ndata: '+json.dumps({'type':'response.created','response':dict(response,output=[],status='in_progress')})+'\n\nevent: response.output_item.added\ndata: '+json.dumps({'type':'response.output_item.added','output_index':0,'item':item})+'\n\nevent: response.output_item.done\ndata: '+json.dumps({'type':'response.output_item.done','output_index':0,'item':item})+'\n\nevent: response.completed\ndata: '+json.dumps({'type':'response.completed','response':response})+'\n\n'
   self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.send_header('Content-Length',str(len(body.encode()))); self.end_headers(); self.wfile.write(body.encode())
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler); threading.Thread(target=server.serve_forever,daemon=True).start()
 (ch/'config.toml').write_text('model = "fixture"\nmodel_provider = "fixture"\ndeveloper_instructions = "SYNTHETIC_OPERATOR_INSTRUCTION"\n[model_providers.fixture]\nname = "fixture"\nbase_url = "http://127.0.0.1:%d/v1"\nwire_api = "responses"\n' % server.server_port)
 history=p/'history'; history.write_text('SYNTHETIC_HISTORY reviewed '+head+' current '+head+'\n')
 r=subprocess.run(['python3',str(root/'skills/review-cycle/scripts/codex-review.py'),'master','--history',str(history)],cwd=work,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
 server.shutdown(); print('exit',r.returncode,'stdout',repr(r.stdout),'stderr',repr(r.stderr),'requests',len(captured)); text=json.dumps(captured,ensure_ascii=False); core=(root/'rules/constitution.md').read_text().split('---\n',2)[2].strip(); diff_seen=any('function_call_output' in json.dumps(req) and '+after' in json.dumps(req) and '-before' in json.dumps(req) for req in captured); print('operator', 'SYNTHETIC_OPERATOR_INSTRUCTION' in text,'constitution',core in text.replace('\\n','\n'),'history','SYNTHETIC_HISTORY' in text,'base_target','master' in text,'actual_diff',diff_seen); assert r.returncode==0 and 'First finding.' in r.stdout and 'Second finding.' in r.stdout and 'SYNTHETIC_OPERATOR_INSTRUCTION' in text and core in text.replace('\\n','\n') and 'SYNTHETIC_HISTORY' in text and diff_seen
