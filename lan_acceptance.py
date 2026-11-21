def run(output):
    import io,json,unittest
    import test_lan
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromModule(test_lan))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,details=stream.getvalue()),indent=2),encoding='utf-8')
    if not result.wasSuccessful():raise SystemExit(1)
