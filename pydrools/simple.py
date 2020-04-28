import atexit
import os
import subprocess
import weakref
from typing import Any

from py4j.java_gateway import GatewayParameters, JavaGateway


class Gateway:
    def __init__(self):
        self._start_gateway()

    def _get_port(self):
        pass

    def _get_java(self):
        if "JAVA_HOME" in os.environ:
            java = os.path.join(os.environ["JAVA_HOME"], "bin", "java")
        else:
            java = "java"
        return java

    def _start_gateway(self):
        java = self._get_java()
        lib = os.path.join(os.path.dirname(__file__), "lib", "*")
        cmd = [java, "-cp", lib, "pydrools.PyDroolsEntrypoint"]
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL
        )
        weakref.finalize(self, process.terminate)
        while True:
            line = process.stdout.readline()
            if not line:
                continue
            line = line.decode("utf-8")
            if line.startswith("PORT:"):
                port = int(line[5:].strip())
                break
            else:
                print(line)
        self.process = process
        self.gateway = JavaGateway(
            gateway_parameters=GatewayParameters(port=port, auto_convert=True)
        )

    def stop(self):
        try:
            self.process.terminate()
        except Exception:
            pass

    def create_knowledge_builder(self):
        return KnowledgeBuilder(self.gateway)

    # def create_knowledge_builder

    def __getattr__(self, name):
        return getattr(self.gateway, name)


class KnowledgeBuilder:
    def __init__(self, gateway):
        self.gateway = gateway

        # common packages
        self.kie = gateway.jvm.org.kie
        self.drools = gateway.jvm.org.drools

        pkg = self.kie.internal.builder
        self.kbuilder = pkg.KnowledgeBuilderFactory.newKnowledgeBuilder()
        self.resourceFactory = self.kie.internal.io.ResourceFactory
        self.resourceType = self.kie.api.io.ResourceType

    def __getattr__(self, name):
        return getattr(self.kbuilder, name)

    def add_drl(self, content):
        if isinstance(content, str):
            content = content.encode("utf-8")
        content = bytearray(content)
        self.kbuilder.add(
            self.resourceFactory.newByteArrayResource(content), self.resourceType.DRL
        )

    def build_kbase(self):
        kbase = self.drools.core.impl.KnowledgeBaseFactory.newKnowledgeBase()
        kbase.addPackages(self.kbuilder.getKnowledgePackages())
        return KnowledgeBase(kbase, self.gateway)


class KnowledgeBase:
    def __init__(self, kbase, gateway):
        self.gateway = gateway
        self.kbase = kbase

    def __getattr__(self, name):
        return getattr(self.kbase, name)

    def create_knowledge_session(self):
        ksession = self.kbase.newKieSession()
        return KieSession(ksession, self)


class KieSession:
    def __init__(self, ksession, kbase: KnowledgeBase):
        self.ksession = ksession
        self.kbase = kbase
        self.gateway = kbase.gateway
