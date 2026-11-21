"""LAN-3.5 / NFR-8: 8 real TLS clients, receipt checks and Qt heartbeat.

Only loopback traffic and temporary game data. Baseline uses a new pinned TLS
connection per poll (the 1.1 transport pattern); after uses persistent polling.
Both use the same 1.2 engine, hardware, rate and command sequence.
"""
import argparse
import hashlib
import json
import math
import os
import secrets
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def percentile(values, fraction=.95):
    return sorted(values)[max(0, math.ceil(len(values)*fraction)-1)] if values else 0


def measure(seconds=60, keepalive=True, clients=8, interval=.1):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from lan import Server, RpcClient, rpc
    import app as ui
    q=QApplication.instance() or QApplication([])
    ui.load_fonts();q.setStyle('Fusion');q.setStyleSheet(ui.STYLE)
    with tempfile.TemporaryDirectory(prefix='bft-benchmark-') as tmp:
        server=Server(Path(tmp),bind='127.0.0.1',port=0)
        window=None;timer=QTimer();errors=[];heartbeats=[];last=[time.perf_counter()]
        try:
            invite=server.invite('127.0.0.1');tokens=[secrets.token_hex(32) for _ in range(clients)]
            def setup(i,op,**args):
                result=rpc(invite,dict(token=tokens[i],op=op,request_id=uuid.uuid4().hex,**args))
                if not result['ok']:raise AssertionError(result)
                return result['view']
            for i in range(clients):setup(i,'join',name='Test '+str(i),owner=server.session.s['owner'] if i==0 else '')
            for i in range(clients):setup(i,'ready')
            setup(0,'start')
            owner=server.session.s['players'][hashlib.sha256(tokens[0].encode()).hexdigest()]
            # Exercise actual host rendering while network workers run.
            window=ui.Window(server.session.game(owner));window.show()
            count=[0]
            def heartbeat():
                now=time.perf_counter();heartbeats.append((now-last[0])*1000);last[0]=now;count[0]+=1
                if count[0]%10==0:
                    # Copy under the same brief state lock used by the real host.
                    with server.session.lock:window.g=server.session.game(owner)
                    window.render()
            timer.timeout.connect(heartbeat);timer.start(20)
            first_handshakes=server.handshakes;start=time.perf_counter();deadline=start+seconds
            def worker(index):
                client=RpcClient();latency=[];sent=0;polls=0;view=None;iteration=0
                def call(message):
                    message=dict(message,token=tokens[index])
                    result=client.call(invite,message) if keepalive else rpc(invite,message)
                    if not result['ok']:raise AssertionError(result)
                    return result['view']
                try:
                    while time.perf_counter()<deadline:
                        tick=time.perf_counter();request=dict(op='poll')
                        if keepalive and view:request['since']={k:view[k] for k in ('revision','lobby_version')}
                        result=call(request);latency.append((time.perf_counter()-tick)*1000);polls+=1
                        if not result.get('unchanged'):view=result
                        if iteration%10==0:
                            for kind in ('borrow','repay_black'):
                                request=dict(op='command',request_id=uuid.uuid4().hex,revision=view['revision'],action='bank',args=dict(kind=kind,amount=1))
                                view=call(request);sent+=1
                                # Replay a delivered command to emulate a lost reply.
                                duplicate=call(request)
                                if duplicate['revision']!=view['revision']:raise AssertionError('Dobbeltkommando')
                        iteration+=1
                        time.sleep(max(0,min(deadline-time.perf_counter(),interval-(time.perf_counter()-tick))))
                except Exception as e:errors.append(f'{index}: {type(e).__name__}: {e}')
                finally:client.close()
                return latency,sent,polls
            with ThreadPoolExecutor(max_workers=clients) as pool:
                jobs=[pool.submit(worker,i) for i in range(clients)]
                while not all(j.done() for j in jobs):q.processEvents();time.sleep(.003)
                results=[j.result() for j in jobs]
            elapsed=time.perf_counter()-start
            latency=[t for values,_,_ in results for t in values]
            committed=sum(p['revision'] for p in server.session.s['players'].values())
            for p in server.session.s['players'].values():
                if (p['state']['black'],p['state']['debt'])!=(2000,5500):errors.append('Penge ændret ved låne/afdrags-rundtur')
            return dict(mode='keepalive+since' if keepalive else 'ny TLS pr. kald',seconds=round(elapsed,3),clients=clients,
                        requested_poll_interval=interval,polls=sum(v[2] for v in results),
                        poll_p95_ms=round(percentile(latency),3),poll_max_ms=round(max(latency,default=0),3),
                        handshakes=server.handshakes-first_handshakes,
                        handshakes_per_second=round((server.handshakes-first_handshakes)/elapsed,3),
                        commands_sent=sum(v[1] for v in results),commands_committed=committed,errors=errors,
                        ui_heartbeats=len(heartbeats),ui_p95_gap_ms=round(percentile(heartbeats),3),
                        ui_max_gap_ms=round(max(heartbeats,default=0),3))
        finally:
            timer.stop()
            if window:window.hide();window.deleteLater();q.processEvents()
            server.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=float,default=60)
    parser.add_argument('--output',type=Path,default=Path('dist/reports/lan-performance.json'))
    args=parser.parse_args();results=[]
    for reuse in (False,True):
        result=measure(seconds=args.seconds,keepalive=reuse)
        results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    report=dict(scope='8 loopback TLS-klienter og Qt-værtsvindue på én Windows-pc; ikke en fysisk LAN-måling.',results=results)
    report['passed']=all(not r['errors'] and r['commands_sent']==r['commands_committed'] for r in results) and results[1]['poll_p95_ms']<50 and results[1]['ui_p95_gap_ms']<100
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    raise SystemExit(0 if report['passed'] else 1)
