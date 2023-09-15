from nomenklatura.matching import LogicV1

from .util import e


def test_logic_scoring():
    a = e("Person", name="Vladimir Putin")
    b = e("Person", name="Vladimir Putin")
    assert LogicV1.compare(a, b).score == 1.0
    b = e("Person", name="Vladimir Pudin")
    assert LogicV1.compare(a, b).score < 1.0
    assert LogicV1.compare(a, b).score > 0.7


def test_logic_qualified_country():
    a = e("Person", name="Vladimir Putin")
    b = e("Person", name="Vladimir Putin")
    assert LogicV1.compare(a, b).score == 1.0
    a.add("country", "pa")
    b.add("country", "ru")
    assert LogicV1.compare(a, b).score > 0.7
    assert LogicV1.compare(a, b).score < 0.9


def test_logic_qualified_dob():
    a = e("Person", name="Vladimir Putin")
    b = e("Person", name="Vladimir Putin")
    assert LogicV1.compare(a, b).score == 1.0
    a.set("birthDate", "1952-02-10")
    b.set("birthDate", "1952-05-01")
    assert LogicV1.compare(a, b).score > 0.7
    assert LogicV1.compare(a, b).score < 1.0
    a.set("birthDate", "1952-02-10")
    b.set("birthDate", "1962-05-01")
    assert LogicV1.compare(a, b).score > 0.5
    assert LogicV1.compare(a, b).score < 0.7


def test_logic_legal_entity():
    a = e("LegalEntity", name="CRYSTALORD LTD")
    b = e("LegalEntity", name="CRYSTALORD LTD")
    assert LogicV1.compare(a, b).score == 1.0


def test_logic_qualified_corp():
    a = e("Company", name="CRYSTALORD LTD")
    b = e("Company", name="CRYSTALORD LTD")
    assert LogicV1.compare(a, b).score == 1.0
    a.set("registrationNumber", "137332")
    b.set("registrationNumber", "748745")
    assert LogicV1.compare(a, b).score == 0.8
    a.set("registrationNumber", "137332")
    b.set("registrationNumber", "E137332")
    assert LogicV1.compare(a, b).score > 0.9


def test_logic_id_only_corp():
    a = e("Company", name="OTHER LTD", registrationNumber="77401103")
    b = e("Company", name="CRYSTALORD LTD", registrationNumber="77401103")
    assert LogicV1.compare(a, b).score > 0.7, LogicV1.compare(a, b).features
    assert LogicV1.compare(a, b).score < 0.9


def test_logic_id_disjoint():
    a = e("Company", name="CRYSTALORD LTD", registrationNumber="77401103")
    b = e("Company", name="CRYSTALORD LTD", registrationNumber="77401103")
    assert LogicV1.compare(a, b).score == 1.0
    b = e("Company", name="CRYSTALORD LTD", registrationNumber="379483787")
    assert LogicV1.compare(a, b).score < 1.0
    assert LogicV1.compare(a, b).score > 0.7


def test_logic_different_country():
    a = e("Company", name="CRYSTALORD LTD", country="pa")
    b = e("Company", name="CRYSTALORD LTD", country="pa")
    assert LogicV1.compare(a, b).score == 1.0
    b = e("Company", name="CRYSTALORD LTD", country="us")
    assert LogicV1.compare(a, b).score < 1.0
    assert LogicV1.compare(a, b).score > 0.7
