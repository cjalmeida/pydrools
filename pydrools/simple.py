import logging
import os
import subprocess
import weakref
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Union

from py4j.java_gateway import GatewayParameters, JavaGateway

logger = logging.getLogger(__name__)


class RuleException(Exception):
    def __init__(self, errors, *args, **kwargs):
        self.errors = errors
        super().__init__(*args, **kwargs)


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
        add_opens_arg = (
            "--illegal-access=warn",
            "--add-opens",
            "java.base/java.lang=ALL-UNNAMED",
            "--add-opens",
            "java.base/java.util=ALL-UNNAMED",
        )
        cmd = [java, "-cp", lib, *add_opens_arg, "pydrools.PyDroolsEntrypoint"]
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL
        )
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

        gateway = JavaGateway(
            gateway_parameters=GatewayParameters(port=port, auto_convert=True)
        )

        def _finalize():
            try:
                print("Shutting down gateway")
                gateway.shutdown()
                process.terminate()
            except Exception:
                pass

        weakref.finalize(self, _finalize)

        self.process = process
        self.java_gateway = gateway

    def create_knowledge_builder(self):
        return KnowledgeBuilder(self)

    def __getattr__(self, name):
        return getattr(self.java_gateway, name)


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
        if isinstance(content, Path):
            content = content.read_bytes()
        if isinstance(content, str):
            content = content.encode("utf-8")
        content = bytearray(content)
        self.kbuilder.add(
            self.resourceFactory.newByteArrayResource(content), self.resourceType.DRL
        )

    def get_errors(self):
        if self.kbuilder.hasErrors():
            errors = []
            for error in self.kbuilder.getErrors():
                errors.append(error.toString())
            return errors
        return []

    def build_kbase(self):
        errors = self.get_errors()
        if errors:
            errors_msg = "\n".join(errors)
            logger.error(errors_msg)
            raise RuleException(
                errors, "We found errors in the knowledge base. Check messages above."
            )

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
    def __init__(self, ksession, kbase: KnowledgeBase, auto_dispose=True):
        self.ksession = ksession
        self.kbase = kbase
        self.gateway = kbase.gateway
        self.types: Dict[Tuple[str, str], Any] = {}
        self.auto_dispose = auto_dispose

        if self.auto_dispose:
            weakref.finalize(self, ksession.dispose)

    @staticmethod
    def from_assets(assets: Iterable[Union[str, bytes, Path]], **kwargs):
        gateway = Gateway()
        kbuilder = gateway.create_knowledge_builder()
        for asset in assets:
            kbuilder.add_drl(asset)
        kbase = kbuilder.build_kbase()
        ksession = kbase.newKieSession()
        return KieSession(ksession, kbase, **kwargs)

    def __getattr__(self, name):
        return getattr(self.ksession, name)

    def package(self, package_name):
        return TypeBuilder(package_name, self.kbase)

    def insert(self, fact):
        if isinstance(fact, Fact):
            return self.ksession.insert(fact._obj)
        else:
            return self.ksession.insert(fact)


class FactType:
    def __init__(self, kie_fact_type):
        self.fact_type = kie_fact_type
        self.fields = kie_fact_type.getFields()
        self.field_names = [x.getName() for x in self.fields]

    def __getattr__(self, name):
        return getattr(self.kie_fact_type, name)

    def __call__(self, *args, **kwargs):
        data = dict(zip(args, self.field_names))
        data.update(kwargs)
        obj = self.fact_type.newInstance()
        self.fact_type.setFromMap(obj, data)
        return Fact(self, obj)


class Fact:
    def __init__(self, fact_type, obj):
        self._fact_type = fact_type
        self._obj = obj

    def __setattr__(self, name, value):
        if name in ["_fact_type", "_obj"]:
            return object.__setattr__(self, name, value)

        return self._fact_type.set(self._obj, name, value)

    def __getattr__(self, name):
        if name in self._fact_type.field_names:
            return self._fact_type.fact_type.get(self._obj, name)
        return getattr(self._obj, name)

    def __str__(self):
        return str(self._obj)

    def __repr__(self):
        return "Fact: " + str(self)

    def __hash__(self):
        return hash(self._obj)

    def __eq__(self, value):
        if isinstance(value, Fact):
            return self._obj == value._obj
        return self._obj == value


class TypeBuilder:
    def __init__(self, package, kbase):
        self.package = package
        self.kbase = kbase
        self._cache = {}

    def __getattr__(self, name):
        _type = self._cache.get(name)
        if _type is None:
            _fact_type = self.kbase.getFactType(self.package, name)
            if _fact_type is None:
                raise Exception(f"Fact type not found: {self.package}.{name}")
            _type = FactType(_fact_type)
            self._cache[name] = _type
        return _type
