import unittest

from svejk.edition.metrics import jazykolam_duplicates


class JazykolamDuplicateTests(unittest.TestCase):
    def test_same_sentence_as_article_quote(self) -> None:
        quote = "Že to je rozpočet, který museli sestavovat mimozemšťané"
        self.assertTrue(jazykolam_duplicates(quote, [quote]))

    def test_different_quote_is_ok(self) -> None:
        self.assertEqual(
            jazykolam_duplicates(
                "uběhla osmnáctá hodina, tím pádem jsme vyčerpali bod ústní interpelace",
                ["Že to je rozpočet, který museli sestavovat mimozemšťané"],
            ),
            [],
        )

    def test_ignores_short_shared_fragment(self) -> None:
        self.assertEqual(
            jazykolam_duplicates("rozpočet", ["rozpočet, který museli sestavovat mimozemšťané, kteří netuší nic"]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
