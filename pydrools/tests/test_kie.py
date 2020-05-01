from pathlib import Path


def test_session():
    from pydrools import KieSession

    here = Path(__file__).parent
    model_file = here / "model.drl"
    rules_file = here / "rules.drl"

    ksession = KieSession.from_assets([model_file, rules_file])
    model = ksession.package("foo.model")

    # test kwargs creation
    mussum = model.Student(name="Mussum")
    # test positional creation
    pinga = model.Lecture("Pinga Crafting")

    # test java method call access on fact
    assert mussum.getLecture() is None

    ksession.insert(mussum)
    ksession.insert(pinga)
    print("Fired rules: " + str(ksession.fireAllRules()))

    # test attribute access on fact
    assert mussum.lecture == pinga

    ksession.dispose()
