from engine.demo_run import main


def test_demo_run_exits_successfully():
    assert main() == 0
