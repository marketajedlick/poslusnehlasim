import unittest

from svejk.jednaci_den import (
    calendar_isos_for_jednaci_den,
    jednaci_datum,
    jednaci_den_minuty,
    steno_iso_patří_k_jednacímu_dni,
    vote_belongs_to_jednaci_den,
    vote_jednaci_datum,
)


class JednaciDenTests(unittest.TestCase):
    def test_po_pulnoci_patri_k_predchozimu_dni(self) -> None:
        self.assertEqual(jednaci_datum("12.02.2026", "00:52"), "11.02.2026")
        self.assertEqual(jednaci_datum("01.07.2026", "00:21"), "30.06.2026")

    def test_denni_hlasovani_zustava(self) -> None:
        self.assertEqual(jednaci_datum("12.02.2026", "13:32"), "12.02.2026")
        self.assertEqual(jednaci_datum("11.02.2026", "23:22"), "11.02.2026")

    def test_hranice_six_am(self) -> None:
        self.assertEqual(jednaci_datum("12.02.2026", "05:59"), "11.02.2026")
        self.assertEqual(jednaci_datum("12.02.2026", "06:00"), "12.02.2026")

    def test_vote_belongs(self) -> None:
        v = {"datum": "12.02.2026", "cas": "01:09", "cislo": 65}
        self.assertTrue(vote_belongs_to_jednaci_den(v, "11.02.2026"))
        self.assertFalse(vote_belongs_to_jednaci_den(v, "12.02.2026"))
        self.assertEqual(vote_jednaci_datum(v), "11.02.2026")

    def test_minuty_pres_pulnoci(self) -> None:
        votes = [
            {"datum": "11.02.2026", "cas": "22:00", "cislo": 1},
            {"datum": "12.02.2026", "cas": "01:09", "cislo": 2},
        ]
        self.assertEqual(jednaci_den_minuty(votes), 189)

    def test_steno_iso_kalendare(self) -> None:
        self.assertEqual(
            calendar_isos_for_jednaci_den("30.06.2026"),
            {"2026-06-30", "2026-07-01"},
        )
        self.assertTrue(
            steno_iso_patří_k_jednacímu_dni("2026-07-01T00:00:00+01:00", "30.06.2026")
        )
        self.assertFalse(
            steno_iso_patří_k_jednacímu_dni("2026-06-29T00:00:00+01:00", "30.06.2026")
        )


if __name__ == "__main__":
    unittest.main()
