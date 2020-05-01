from pathlib import Path

try:
    import jinja2
    from sqlalchemy.ext.declarative.api import DeclarativeMeta
    from sqlalchemy.orm.properties import ColumnProperty
    from sqlalchemy.orm.relationships import RelationshipProperty
except ModuleNotFoundError:
    pass

__all__ = ["PackageBuilder"]


_STRING_TYPES = (
    "char",
    "clob",
    "nchar",
    "nvarchar",
    "stringtype",
    "text",
    "string",
    "unicode",
    "varchar",
)

_IGNORE_TYPES = ("blob", "binary", "array", "enum", "varbinary")


class PackageBuilder:

    IGNORE = "##IGNORE##"

    def __init__(self, package_name, classes=None, imports=None):

        _check_dependencies()

        self.package_name = package_name
        self.classes = []
        self.imports = []

        for _class in classes or []:
            self.add_class(_class)

        for _import in imports or []:
            self.add_import(_import)

    def add_import(self, _import):
        self.imports.append(_import)

    def add_class(self, _class, ignore_fields=None):
        if not isinstance(_class, DeclarativeMeta):
            raise Exception(f"{_class} is not an SQLAlchemy mapping")
        ignore_fields = ignore_fields or []
        self.classes.append((_class.__name__, _class.__mapper__, ignore_fields))

    def map_name(self, prop):
        return prop.key

    def map_type(self, prop):
        """Map properties into fact fields

        You should set a ``drools_ignore`` to property ``info`` to ignore fields.
        """

        if prop.info.get("drools_ignore", False):
            return self.IGNORE

        elif isinstance(prop, ColumnProperty):
            if len(prop.columns) != 1:
                # Must handle composite properties manually
                return None
            column = prop.columns[0]
            return self.map_column(column)

        elif isinstance(prop, RelationshipProperty):
            return self.map_relationship(prop)
        else:
            return None

    def map_relationship(self, prop):
        direction = prop.direction.name
        if direction == "MANYTOONE":
            return prop.entity.class_.__name__
        elif direction == "ONETOMANY":
            entity = prop.entity.class_.__name__
            col_class = prop.collection_class or list
            if col_class == list:
                return f"java.util.List<{entity}>"
            elif col_class == set:
                return f"java.util.Set<{entity}>"
            else:
                return None

    def map_column(self, column):

        t = type(column.type).__name__.lower()

        if t in _STRING_TYPES:
            return "String"

        elif t in ("bigint", "biginteger"):
            return "Long"

        elif t in ("int", "integer"):
            return "Integer"

        elif t in ("boolean",):
            return "Boolean"

        elif t in ("date", "datetime", "timestamp"):
            return "java.util.Date"

        elif t in ("time",):
            return "java.time.LocalTime"

        elif t in ("decimal",):
            return "java.math.BigDecimal"

        elif t in ("float",):
            return "Float"

        elif t in ("real",):
            return "Double"

        elif t in _IGNORE_TYPES:
            return self.IGNORE

        return None

    def build(self) -> str:
        classes = []
        for _class_name, mapper, ignore, in self.classes:
            fields = []
            attrs = mapper.attrs
            for key in mapper.class_.__dict__:
                if key.startswith("_"):
                    continue

                prop = attrs[key]
                fname = self.map_name(prop)

                if fname in ignore:
                    continue

                ftype = self.map_type(prop)

                if ftype is None:
                    raise Exception(f"Cannot map type for prop: {_class_name}->{fname}")

                if ftype == self.IGNORE:
                    continue

                fields.append(dict(name=fname, type=ftype))

            classes.append(dict(name=_class_name, fields=fields))

        tpl = (Path(__file__).parent / "fact_types.tpl.drl").read_text()
        out = jinja2.Template(tpl).render(
            package_name=self.package_name, classes=classes, imports=self.imports
        )
        return out


def _check_dependencies():
    try:
        import sqlalchemy  # NOQA
    except ModuleNotFoundError as ex:
        raise Exception("SQLAlchemy not installed") from ex

    try:
        import jinja2  # NOQA
    except ModuleNotFoundError as ex:
        raise Exception("Jinja2 not installed") from ex
