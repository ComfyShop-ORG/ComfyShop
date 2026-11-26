import plistlib
from pathlib import Path
from xml.etree import ElementTree

from comfyshop_worker.service import (
    ServiceLaunch,
    launch_agent,
    scheduled_task,
    service_name,
    systemd_unit,
)


def test_service_descriptors_preserve_arguments_and_enable_restart(tmp_path):
    config = tmp_path / "工作机 & 文件.json"
    name = service_name(config)
    assert name != service_name(config.with_name("worker.json"))
    args = ["/example/python", "-m", "comfyshop_worker", "--service-run", str(config)]
    launch = ServiceLaunch(Path("/example/worker directory"), args)
    agent = plistlib.loads(launch_agent(name, launch))
    assert agent["ProgramArguments"] == args
    assert agent["RunAtLoad"] and agent["KeepAlive"] == {"SuccessfulExit": False}

    systemd = systemd_unit(
        ServiceLaunch(Path("/example/worker directory"), [*args, "/example/%n/$USER"])
    ).decode()
    assert "WorkingDirectory=/example/worker directory\n" in systemd
    assert '"/example/%%n/$$USER"' in systemd
    assert "Restart=on-failure" in systemd

    task = ElementTree.fromstring(scheduled_task(launch, "WORKGROUP\\name"))  # noqa: S314
    assert task.attrib["version"] == "1.3"
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    assert task.findtext("t:Triggers/t:LogonTrigger/t:UserId", namespaces=ns) == "WORKGROUP\\name"
    assert task.findtext("t:Actions/t:Exec/t:Command", namespaces=ns) == args[0]
    assert str(config) in task.findtext("t:Actions/t:Exec/t:Arguments", namespaces=ns)
    assert task.findtext("t:Settings/t:ExecutionTimeLimit", namespaces=ns) == "PT0S"
    assert task.findtext("t:Settings/t:MultipleInstancesPolicy", namespaces=ns) == "IgnoreNew"
