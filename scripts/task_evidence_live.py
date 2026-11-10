"""Does the installed harness bind evidence before execution and reject summary-only completion?

Bounded offline experiment: local Git fixture, loopback scripted provider,
private HOME, at most 24 requests and 120 seconds per installed harness.
No external model, judge, credentials, login probe or live GitHub fixture.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('live', ROOT / 'scripts/check-omp-task-state-live.py')
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


def _latest_status(messages):
    decoder = json.JSONDecoder()
    def find(value, depth=0):
        if depth>12: return None
        if isinstance(value,dict):
            if 'state' in value and 'sources' in value: return value
            for nested in value.values():
                found=find(nested,depth+1)
                if found is not None: return found
        if isinstance(value,list):
            for nested in reversed(value):
                found=find(nested,depth+1)
                if found is not None: return found
        if isinstance(value,str):
            for start,char in enumerate(value):
                if char!='{': continue
                try: decoded,_=decoder.raw_decode(value,start)
                except json.JSONDecodeError: continue
                found=find(decoded,depth+1)
                if found is not None: return found
        return None
    for message in reversed(messages):
        found=find(message)
        if found is not None: return found
    raise AssertionError('Missing status in native provider messages')


def _step(index, messages, root, state_tool, check_tool):
    if index in (0, 4, 7):
        return state_tool, {'action': 'status'}
    if index == 1:
        status = _latest_status(messages)
        state = status['state']
        source = next(source for source in status['sources'] if source['kind'] in ('user', 'interpretation'))
        ref = {'sourceId': source['sourceId'], 'quote': source['text']}
        verification = {'kinds': ['check', 'judgment'], 'toolName': check_tool, 'input': {}, 'subject': {'kind': 'repository', 'root': str(root)}}
        criteria = [{**criterion, 'verification': verification} for criterion in state['contract']['criteria']]
        return state_tool, {'action': 'contract', 'record': json.dumps({'expectedRevision': state['contract']['revision'], 'change': 'Ground native offline check and attributed review', 'sourceRefs': [ref], 'contract': {'criteria': criteria, 'requiredEvidenceKinds': ['check'], 'requiredReviewKinds': ['judgment'], 'approvalRequirements': []}})}
    if index in (2, 10):
        return state_tool, {'action': 'complete', 'record': json.dumps({'summary': 'Native fixture check and attributed review recorded.'})}
    if index in (3, 6, 11):
        return check_tool, {}
    if index in (5, 8, 9):
        status = _latest_status(messages)
        source = next(source for source in reversed(status['evidence']) if source['toolName'] == check_tool)
        record = {'id': f'evidence-{index}', 'taskId': status['state']['taskId'], 'criterionId': 'request', 'contractRevision': status['state']['contract']['revision'], 'subject': source['execution']['subject'], 'source': {'sourceId': source['sourceId'], 'quote': source['text']}, 'kind': 'judgment' if index == 9 else 'check', 'result': 'passed'}
        if index == 9:
            record['judgment'] = {'reviewer': 'offline scripted reviewer', 'rationale': 'Inspected the unchanged fixture against the native scenario contract.', 'artifacts': [source['execution']['subject']['commit'] + ':subject.txt']}
        return state_tool, {'action': 'evidence', 'record': json.dumps(record)}
    if index == 12:
        return state_tool, {'action': 'receipt'}
    return None


def _run_omp():
    with tempfile.TemporaryDirectory(prefix='issue-801-native-omp-') as temporary:
        base = Path(temporary); home = base / 'home'; root = base / 'sandbox'; root.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()
        git('init', '--initial-branch=master'); git('config', 'user.name', 'Offline Fixture'); git('config', 'user.email', 'fixture@example.invalid')
        (root / 'subject.txt').write_text('original\n'); git('add', 'subject.txt'); git('commit', '-m', 'Record fixture')
        count = []
        class Provider(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                index = len(count); count.append(index); assert index < 24
                action = _step(index, body.get('messages', []), root, 'write', 'completion_fixture')
                if action:
                    name, args = action
                    if name == 'write': args = {'path': 'xd://daily_driver_task_state', 'content': json.dumps(args)}
                    message = {'role': 'assistant', 'tool_calls': [{'index': 0, 'id': f'native-{index}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}
                    finish = 'tool_calls'
                else:
                    message = {'role': 'assistant', 'content': 'The native scenario has stopped.'}; finish = 'stop'
                chunks = [{'id': 'fixture', 'object': 'chat.completion.chunk', 'model': live.FIXTURE.MODEL, 'choices': [{'index': 0, 'delta': message}]}, {'id': 'fixture', 'object': 'chat.completion.chunk', 'model': live.FIXTURE.MODEL, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}], 'usage': {'prompt_tokens': 20, 'completion_tokens': 5, 'total_tokens': 25}}]
                data = (''.join('data: ' + json.dumps(chunk) + '\n\n' for chunk in chunks) + 'data: [DONE]\n\n').encode()
                self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Provider); threading.Thread(target=server.serve_forever, daemon=True).start()
        live.FIXTURE.write_home(home, server.server_address[1])
        observer = base / 'observer.mjs'
        observer.write_text('''import {execFileSync} from 'node:child_process';
import {writeFileSync} from 'node:fs';
export default function(pi) {
 let calls=0;
 pi.registerTool({name:'completion_fixture',label:'Offline completion fixture',description:'Return a recorded offline check response.',parameters:pi.zod.object({}),execute:async(_id,_params,_signal,_update,ctx)=>{
  calls++;
  const headRefOid=execFileSync('git',['-C',ctx.cwd,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
  if(calls===3) writeFileSync(ctx.cwd+'/subject.txt','changed\\n');
  const result={headRefOid,statusCheckRollup:[{conclusion:calls===1?'FAILURE':'SUCCESS'}],judgment:{reviewer:'offline scripted reviewer',rationale:'Inspected the unchanged fixture against the native scenario contract.',artifacts:[headRefOid+':subject.txt']}};
  return {content:[{type:'text',text:JSON.stringify(result)}],details:{exitCode:0,...result}};
 }});
}''')
        # Expose only the native fixture and the shipped task-state device route.
        config = home / '.omp/agent/config.yml'
        config.write_text(config.read_text() + '\ntools:\n  completion_fixture: true\n')
        env = {key: os.environ[key] for key in ('PATH', 'TMPDIR', 'LANG', 'TERM') if key in os.environ}; env['HOME'] = str(home)
        live.PROBES['completion'] = 'Implement the offline native completion fixture.'
        # run() deliberately has a fixed tool list; use its measured RPC mechanics with a fixture wrapper.
        wrapper = base / 'omp-fixture'
        wrapper.write_text('#!/bin/sh\nexec ' + subprocess.check_output(['which', 'omp'], text=True).strip() + ' "$@" --tools read,write,completion_fixture\n'); wrapper.chmod(0o700)
        try:
            frames = live.run(str(wrapper), base, env, 'completion', observer)
            entries = [json.loads(line) for line in next((base / 'persistent-session').glob('*.jsonl')).read_text().splitlines()]
            states = [entry['data']['state'] for entry in entries if entry.get('customType') == 'daily-driver.task-state']
            calls = [frame for frame in frames if frame.get('type') == 'tool_execution_end']
            assert calls[2]['isError'] and 'Completion rejected' in json.dumps(calls[2]), calls[2]
            assert calls[5]['isError'], calls[5]
            assert any(state['status'] == 'verified-complete' for state in states), states[-1]
            assert states[-1]['status'] == 'active' and states[-1]['corrections'] == 2 and states[-1].get('stopFailure'), states[-1]
            assert any('stale' in json.dumps(frame) for frame in calls if frame.get('toolCallId') == 'native-12'), calls[-1]
            print(json.dumps({'harness': subprocess.check_output(['omp', '--version'], text=True).strip(), 'requests': len(count), 'summary_rejected': True, 'transport_success_with_failed_check_rejected': True, 'current_check_and_judgment_completed': True, 'dirty_subject_reopened': True, 'corrections': states[-1]['corrections']}))
        finally:
            server.shutdown()

def _run_claude():
    worktrunk = os.environ.get('WORKTRUNK_PLUGIN_ROOT')
    if not worktrunk or not (Path(worktrunk) / '.claude-plugin/plugin.json').is_file():
        raise RuntimeError('Set WORKTRUNK_PLUGIN_ROOT to the installed Worktrunk plugin directory required by the unchanged Daily Driver manifest')
    with tempfile.TemporaryDirectory(prefix='issue-801-native-claude-') as temporary:
        base = Path(temporary); home = base / 'home'; home.mkdir(); root = base / 'sandbox'; root.mkdir()
        def git(*args): return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()
        git('init', '--initial-branch=master'); git('config', 'user.name', 'Offline Fixture'); git('config', 'user.email', 'fixture@example.invalid')
        (root / 'subject.txt').write_text('original\n'); git('add', 'subject.txt'); git('commit', '-m', 'Record fixture')
        plugin = base / 'fixture'; (plugin / '.claude-plugin').mkdir(parents=True); (plugin / 'hooks').mkdir()
        (plugin / '.claude-plugin/plugin.json').write_text(json.dumps({'name': 'completion-fixture', 'version': '0.0.0', 'hooks': './hooks/hooks.json'}))
        (plugin / 'hooks/hooks.json').write_text(json.dumps({'modules': ['./fixture.js']}))
        (plugin / 'hooks/fixture.js').write_text('''export function register(on) {
 let calls=0;
 on('session.start', async($,e,next)=>{
  await $.tool.register({name:'check',description:'Return recorded offline check conclusions.',inputSchema:{type:'object',properties:{},additionalProperties:false},isDeferred:false});
  return next(e);
 });
 on('tool.call',async($,e,next)=>{
  if(e.tool!=='mcp__completion-fixture__check') return next(e);
  calls++;
  const cwd=await $.session.cwd();
  const head=await $.process.run(['git','-C',cwd,'rev-parse','HEAD']);
  if(calls===3) await $.process.run(['sh','-c','printf changed > subject.txt']);
  return {result:JSON.stringify({headRefOid:head.stdout.trim(),statusCheckRollup:[{conclusion:calls===1?'FAILURE':'SUCCESS'}],judgment:{reviewer:'offline scripted reviewer',rationale:'Inspected the unchanged fixture against the native scenario contract.',artifacts:[head.stdout.trim()+':subject.txt']}})};
 });
}''')
        count=[]; requests=[]
        class Provider(BaseHTTPRequestHandler):
            def log_message(self,*_): pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path.endswith('/count_tokens'):
                    data=b'{"input_tokens":100}'; self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return
                index=len(count); count.append(index); requests.append(body); assert index<24
                try: action=_step(index,body.get('messages',[]),root,'mcp__daily-driver__task_state','mcp__completion-fixture__check')
                except Exception as error:
                    (base/'failure.json').write_text(json.dumps({'error':repr(error),'body':body})); raise
                content=[{'type':'tool_use','id':f'native-{index}','name':action[0],'input':action[1]}] if action else [{'type':'text','text':'Native scenario stopped.'}]
                result={'id':f'msg_{index}','type':'message','role':'assistant','model':body.get('model'),'content':content,'stop_reason':'tool_use' if action else 'end_turn','stop_sequence':None,'usage':{'input_tokens':100,'output_tokens':10}}
                if not body.get('stream'):
                    data=json.dumps(result).encode(); content_type='application/json'
                else:
                    frames=[('message_start',{'type':'message_start','message':{**result,'content':[],'stop_reason':None}})]
                    block=content[0]
                    frames.append(('content_block_start',{'type':'content_block_start','index':0,'content_block':{**block,'input':{}} if action else {**block,'text':''}}))
                    delta={'type':'input_json_delta','partial_json':json.dumps(block['input'])} if action else {'type':'text_delta','text':block['text']}
                    frames += [('content_block_delta',{'type':'content_block_delta','index':0,'delta':delta}),('content_block_stop',{'type':'content_block_stop','index':0}),('message_delta',{'type':'message_delta','delta':{'stop_reason':result['stop_reason'],'stop_sequence':None},'usage':{'output_tokens':10}}),('message_stop',{'type':'message_stop'})]
                    data=''.join('event: '+name+'\ndata: '+json.dumps(value)+'\n\n' for name,value in frames).encode(); content_type='text/event-stream'
                self.send_response(200); self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Provider); threading.Thread(target=server.serve_forever,daemon=True).start()
        env={key:os.environ[key] for key in ('PATH','TMPDIR','LANG','TERM') if key in os.environ}
        env.update(HOME=str(home),CLAUDE_CONFIG_DIR=str(home/'config'),ANTHROPIC_BASE_URL=f'http://127.0.0.1:{server.server_address[1]}',ANTHROPIC_API_KEY='offline-fixture',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',DISABLE_AUTOUPDATER='1')
        try:
            run=subprocess.run(['claude','-p','Implement the offline native completion fixture.','--plugin-dir',worktrunk,'--plugin-dir',str(ROOT),'--plugin-dir',str(plugin),'--setting-sources','','--allowedTools','mcp__daily-driver__task_state,mcp__completion-fixture__check','--output-format','stream-json','--verbose','--debug-file',str(base/'debug.log')],cwd=root,env=env,text=True,capture_output=True,timeout=120)
            ledgers=list((home/'config/daily-driver-task-contracts').glob('*.json'))
            assert ledgers, {'returncode':run.returncode,'stdout':run.stdout[-6000:],'stderr':run.stderr[-6000:],'requests':len(count)}
            entries=json.loads(ledgers[0].read_text())['entries']; states=[entry['data']['state'] for entry in entries if entry.get('customType')=='daily-driver.task-state']
            assert any(state['status']=='verified-complete' for state in states), {'state':states[-1],'stdout':run.stdout[-8000:],'stderr':run.stderr[-4000:],'requests':len(count)}
            assert states[-1]['status']=='active' and states[-1]['corrections']==2 and states[-1].get('stopFailure'), states[-1]
            assert 'Completion rejected' in run.stdout and 'actual command/check outcome' in run.stdout, run.stdout[-8000:]
            print(json.dumps({'harness':subprocess.check_output(['claude','--version'],text=True).strip(),'requests':len(count),'summary_rejected':True,'failed_check_rejected':True,'current_check_and_judgment_completed':True,'dirty_subject_reopened':True,'corrections':states[-1]['corrections']}))
        except Exception:
            print('CLAUDE_OFFLINE_DIAGNOSTIC',json.dumps({'requests':len(count),'tools':[tool['name'] for tool in requests[-1].get('tools',[]) if tool['name'].startswith('mcp__')] if requests else [],'debug':(base/'debug.log').read_text()[-6000:] if (base/'debug.log').exists() else None})[-10000:])
            raise
        finally: server.shutdown()

def _run_codex():
    with tempfile.TemporaryDirectory(prefix='issue-801-native-codex-') as temporary:
        base=Path(temporary); home=base/'home'; home.mkdir(); root=base/'sandbox'; root.mkdir()
        def git(*args): return subprocess.check_output(['git','-C',str(root),*args],text=True,stderr=subprocess.DEVNULL).strip()
        git('init','--initial-branch=master'); git('config','user.name','Offline Fixture'); git('config','user.email','fixture@example.invalid')
        (root/'subject.txt').write_text('original\n'); git('add','subject.txt'); git('commit','-m','Record fixture')
        check_script=base/'check.py'
        check_script.write_text('''import json,subprocess
from pathlib import Path
base=Path(__file__).parent
counter=base/'counter'
count=int(counter.read_text())+1 if counter.exists() else 1
counter.write_text(str(count))
root=base/'sandbox'
head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
if count==3: (root/'subject.txt').write_text('changed')
print(json.dumps({'headRefOid':head,'statusCheckRollup':[{'conclusion':'FAILURE' if count==1 else 'SUCCESS'}],'judgment':{'reviewer':'offline scripted reviewer','rationale':'Inspected the unchanged fixture against the native scenario contract.','artifacts':[head+':subject.txt']}}))
''')
        count=[]; requests=[]; state_command=[None]
        class Provider(BaseHTTPRequestHandler):
            def log_message(self,*_): pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                index=len(count); count.append(index); requests.append(body); assert index<24
                messages=body.get('input',[])
                if index==0:
                    import re
                    encoded=json.dumps(messages)
                    # The hook supplies this exact command in native additional context.
                    match=re.search(r'Task-state tool route: (python3 [^\\]+?)\\. Supply JSON',encoded)
                    if match: state_command[0]=match.group(1)
                    else:
                        # Resolve only the native session id written by SessionStart, never a fabricated source.
                        ledgers=list((home/'daily-driver-task-contracts').glob('*.json'))
                        assert ledgers, {'input':encoded[-4000:],'tools':[tool.get('name') for tool in body.get('tools',[])]}
                        entries=json.loads(ledgers[0].read_text())['entries']
                        session=next(entry['data']['sessionId'] for entry in entries if entry.get('customType')=='daily-driver.task-state').split(':',2)[1]
                        import shlex
                        state_command[0]=shlex.join(['python3',str(ROOT/'hooks/task-state.py'),'--harness','codex','--tool','--session',session])
                action=_step(index,messages,root,'state','Bash')
                if action:
                    import shlex
                    name,args=action
                    if name=='state':
                        if index==1:
                            record=json.loads(args['record'])
                            for criterion in record['contract']['criteria']:
                                criterion['verification']['input']={'command':f'python3 {check_script}'}
                            args['record']=json.dumps(record)
                        command='printf %s '+shlex.quote(json.dumps(args))+' | '+state_command[0]
                    else: command=f'python3 {check_script}'
                    item={'type':'function_call','id':f'fc_{index}','call_id':f'call_{index}','name':'exec_command','arguments':json.dumps({'cmd':command,'yield_time_ms':1000,'max_output_tokens':12000})}
                else:
                    item={'type':'message','id':f'msg_{index}','role':'assistant','content':[{'type':'output_text','text':'Native scenario stopped.','annotations':[]}]}
                response={'id':f'resp_{index}','object':'response','status':'completed','model':body.get('model'),'output':[item],'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110}}
                frames=[{'type':'response.created','response':{**response,'status':'in_progress','output':[]}}, {'type':'response.output_item.added','output_index':0,'item':item},{'type':'response.output_item.done','output_index':0,'item':item},{'type':'response.completed','response':response}]
                data=''.join('event: '+frame['type']+'\ndata: '+json.dumps(frame)+'\n\n' for frame in frames).encode()
                self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Provider); threading.Thread(target=server.serve_forever,daemon=True).start()
        (home/'config.toml').write_text(f'''model = "offline-fixture"
model_provider = "offline"
model_reasoning_effort = "low"
tool_output_token_limit = 20000
[features]
hooks = true
[model_providers.offline]
name = "Offline fixture"
base_url = "http://127.0.0.1:{server.server_address[1]}/v1"
wire_api = "responses"
requires_openai_auth = false
''')
        env={key:os.environ[key] for key in ('PATH','TMPDIR','LANG','TERM') if key in os.environ}; env.update(HOME=str(home),CODEX_HOME=str(home))
        try:
            added=subprocess.run(['codex','plugin','marketplace','add',str(ROOT),'--json'],cwd=root,env=env,text=True,capture_output=True,timeout=20)
            assert added.returncode==0,added.stderr
            installed=subprocess.run(['codex','plugin','add','daily-driver@daily-driver','--json'],cwd=root,env=env,text=True,capture_output=True,timeout=20)
            assert installed.returncode==0,installed.stderr
            run=subprocess.run(['codex','-a','never','exec','--json','--dangerously-bypass-hook-trust','--sandbox','workspace-write','--add-dir',str(base),'-C',str(root),'Implement the offline native completion fixture.'],cwd=root,env=env,text=True,capture_output=True,timeout=120)
            ledgers=list((home/'daily-driver-task-contracts').glob('*.json'))
            assert ledgers,{'returncode':run.returncode,'stdout':run.stdout[-4000:],'stderr':run.stderr[-4000:],'requests':len(count)}
            entries=json.loads(ledgers[0].read_text())['entries']; states=[entry['data']['state'] for entry in entries if entry.get('customType')=='daily-driver.task-state']
            assert any(state['status']=='verified-complete' for state in states), {'state':states[-1],'stdout':run.stdout[-10000:],'stderr':run.stderr[-4000:],'requests':len(count)}
            assert states[-1]['status']=='active' and states[-1]['corrections']==2 and states[-1].get('stopFailure'),states[-1]
            assert 'Completion rejected' in run.stdout and 'actual command/check outcome' in run.stdout,run.stdout[-8000:]
            print(json.dumps({'harness':subprocess.check_output(['codex','--version'],text=True).strip(),'requests':len(count),'summary_rejected':True,'failed_check_rejected':True,'current_check_and_judgment_completed':True,'dirty_subject_reopened':True,'corrections':states[-1]['corrections']}))
        except Exception:
            print('CODEX_OFFLINE_DIAGNOSTIC',json.dumps({'requests':len(count),'first_outputs':[str(item.get('output',''))[:3000] for request in requests[:3] for item in request.get('input',[]) if item.get('type')=='function_call_output'],'tools':[tool.get('name') for tool in requests[-1].get('tools',[])] if requests else []}))
            raise
        finally: server.shutdown()


def run_completion_harness(harness):
    """run_completion_harness exercises native evidence gates with bounded offline fixtures."""
    runners = {"omp": _run_omp, "claude": _run_claude, "codex": _run_codex}
    if harness not in runners:
        raise ValueError("Completion harness must be omp, claude or codex")
    runners[harness]()
