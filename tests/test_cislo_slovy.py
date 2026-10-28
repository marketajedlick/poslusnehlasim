from svejk.cislo_slovy import (
    krat_hlasovali,
    krat_se_hlasovalo,
    krat_slovy,
    nahrad_cisla_v_textu,
    po_hlasovanich,
)


def test_po_hlasovanich_stovky():
    assert po_hlasovanich(100) == "po stu hlasováních"
    assert po_hlasovanich(165) == "po sto šedesáti pěti hlasováních"
    assert po_hlasovanich(265) == "po dvou stech šedesáti pěti hlasováních"
    assert po_hlasovanich(22) == "po dvaceti dvou hlasováních"


def test_po_hlasovanich_v_textu_bez_zdvojeneho_ch():
    assert nahrad_cisla_v_textu("Po 5 hlasováních konec.") == "Po pěti hlasováních konec."
    assert nahrad_cisla_v_textu("až po 3 hlasování") == "až po třech hlasováních"


def test_rod_za_cislem():
    assert nahrad_cisla_v_textu("chyběly 2 hlasy") == "chyběly dva hlasy"
    assert nahrad_cisla_v_textu("22 hlasů") == "dvacet dva hlasů"
    assert nahrad_cisla_v_textu("2 pozměňovací návrhy") == "dva pozměňovací návrhy"
    assert nahrad_cisla_v_textu("1 hlas") == "jeden hlas"
    assert nahrad_cisla_v_textu("2 ženy") == "dvě ženy"
    assert nahrad_cisla_v_textu("2 procenta") == "dvě procenta"
    assert nahrad_cisla_v_textu("22 000 korun") == "dvacet dva tisíc korun"


def test_krat_slovy():
    assert krat_slovy(22) == "dvaadvacetkrát"
    assert krat_slovy(21) == "jedenadvacetkrát"
    assert krat_slovy(20) == "dvacetkrát"
    assert krat_slovy(165) == "stopětašedesátkrát"
    assert krat_hlasovali(22) == "dvaadvacetkrát hlasovali"
    assert krat_se_hlasovalo(44) == "čtyřiačtyřicetkrát se hlasovalo"
