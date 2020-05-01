from pathlib import Path


def create_model_classes():
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import relationship
    from sqlalchemy import Column, String, ForeignKey

    Base = declarative_base()

    class Lecture(Base):
        __tablename__ = "lecture"

        name = Column(String, primary_key=True)

        students = relationship(
            "Student", back_populates="lecture", info={"drools_ignore": True}
        )

    class Student(Base):
        __tablename__ = "student"

        name = Column(String, primary_key=True)
        lecture_name = Column(String, ForeignKey("lecture.name"))

        lecture = relationship("Lecture", back_populates="students")

    return (Lecture, Student)


def test_sqlalchemy():
    from pydrools.sqlalchemy import PackageBuilder
    from pydrools import KieSession

    Lecture, Student = create_model_classes()

    pkg_builder = PackageBuilder("foo.model", classes=[Lecture, Student])
    model_content = pkg_builder.build()
    print(model_content)

    here = Path(__file__).parent
    rules_file = here / "rules.drl"

    ksession = KieSession.from_assets([model_content, rules_file])
    model = ksession.package("foo.model")

    # test kwargs creation (order is not guaranteed in )
    mussum = model.Student(name="Mussum")
    pinga = model.Lecture("Pinga Crafting")

    # test java method call access on fact
    assert mussum.getLecture() is None
    assert mussum.getName() == "Mussum"
    assert pinga.name == "Pinga Crafting"

    ksession.insert(mussum)
    ksession.insert(pinga)
    print("Fired rules: " + str(ksession.fireAllRules()))

    # test attribute access on fact
    assert mussum.lecture == pinga
    print(pinga)
    ksession.dispose()
