"""Explicit release checks, isolated from the player's saved data.

Invoked only with --release-self-test <json-output>. Uses local TLS sockets.
"""
def run(output):
    import os,tempfile
    from unittest.mock import patch
    with tempfile.TemporaryDirectory(prefix='bft-release-') as directory:
        with patch.dict(os.environ, BFT_DATA_DIR=directory, QT_QPA_PLATFORM='offscreen'):
            _run(output)


def _run(output):
    import io,json,os,time,unittest
    os.environ['QT_QPA_PLATFORM']='offscreen'
    import test_game,test_lan,test_release,test_ui,test_events,test_platform
    from game import VERSION,RULESET
    stream=io.StringIO();started=time.monotonic()
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m)
                            for m in (test_game,test_lan,test_release,test_ui,test_events,test_platform))
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    report=dict(version=VERSION,ruleset=RULESET,passed=result.wasSuccessful(),
                tests=result.testsRun,seconds=round(time.monotonic()-started,2),
                errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),
                details=stream.getvalue(),scope='Engine, Qt UI and real TLS on one machine; no physical multi-PC/firewall test.',platform=__import__('sys').platform)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    if not result.wasSuccessful():raise SystemExit(1)
