import gc

import psutil


def test_gateway():
    from pydrools import Gateway

    gw = Gateway()

    # assert the java processi is running
    proc = psutil.Process(gw.process.pid)
    assert proc.is_running()

    _map = gw.jvm.java.util.HashMap()
    _map.put("foo", "bar")
    assert _map["foo"] == "bar"

    # cleanup and assert java process is dead
    del gw, _map
    gc.collect()
    proc.wait(5)
    assert not proc.is_running()
