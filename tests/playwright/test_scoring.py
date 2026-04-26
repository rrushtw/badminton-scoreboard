#!/usr/bin/env python3
"""Playwright integration tests — lock in current scoring behavior.

Run via tests/run.sh, which spins up the docker-compose'd site and
invokes this file inside a Playwright container on the same network.
"""

import os
import unittest
from playwright.sync_api import sync_playwright


SITE_URL = os.environ["SITE_URL"]


class TestScoring(unittest.TestCase):
    # ## Class-level browser lifecycle
    @classmethod
    def setUpClass(cls) -> None:
        cls.__playwright = sync_playwright().start()
        cls.__browser = cls.__playwright.chromium.launch()
    # end def

    @classmethod
    def tearDownClass(cls) -> None:
        cls.__browser.close()
        cls.__playwright.stop()
    # end def

    # ## Per-test page lifecycle
    def setUp(self) -> None:
        self.__page = type(self).__browser.new_page()
        self.__page.goto(SITE_URL)
        self.__page.wait_for_selector("#scoreA")
        self.__page.wait_for_function(
            "document.getElementById('scoreA').textContent === '0'"
        )
    # end def

    def tearDown(self) -> None:
        self.__page.close()
    # end def

    # ## Private Helpers
    def __ClickPlus(self, team: str) -> None:
        """team: 'A' or 'B'."""
        self.__page.locator(f"#team{team} .score-button:not(.deduct)").click()
    # end def

    def __ClickMinus(self, team: str) -> None:
        self.__page.locator(f"#team{team} .score-button.deduct").click()
    # end def

    def __GetScore(self, team: str) -> int:
        return int(self.__page.locator(f"#score{team}").text_content())
    # end def

    def __GetServing(self):
        a = (self.__page.locator("#servingA").text_content() or "").strip()
        b = (self.__page.locator("#servingB").text_content() or "").strip()
        if a:
            return "A"
        if b:
            return "B"
        return None
    # end def

    def __ModalIsVisible(self) -> bool:
        classes = self.__page.locator("#modal").get_attribute("class") or ""
        return "is-active" in classes
    # end def

    def __CloseModal(self) -> None:
        self.__page.locator(".modal-button").click()
        self.__page.wait_for_function(
            "!document.getElementById('modal').classList.contains('is-active')"
        )
    # end def

    def __ReachScore(self, target_a: int, target_b: int) -> None:
        """Alternate +1 clicks toward (target_a, target_b) keeping the
        diff <= 1 throughout, so checkGameOver does not fire mid-sequence.
        """
        while self.__GetScore("A") < target_a or self.__GetScore("B") < target_b:
            a, b = self.__GetScore("A"), self.__GetScore("B")
            if a < target_a and a <= b:
                self.__ClickPlus("A")
            elif b < target_b:
                self.__ClickPlus("B")
            else:
                self.__ClickPlus("A")
    # end def

    # ## Tests
    def test_ScoreIncrementsAndDecrementsWithFloor(self):
        """+ adds 1; - subtracts 1; - at 0 is a no-op (floor)."""
        self.__ClickMinus("A")
        self.assertEqual(0, self.__GetScore("A"))  # floor at zero
        self.__ClickPlus("A")
        self.__ClickPlus("A")
        self.__ClickPlus("A")
        self.assertEqual(3, self.__GetScore("A"))
        self.__ClickMinus("A")
        self.assertEqual(2, self.__GetScore("A"))
    # end def

    def test_ServerTransfersWhenReceiverScores(self):
        """A serves first; when the receiver scores, the serve transfers."""
        self.assertEqual("A", self.__GetServing())
        self.__ClickPlus("B")
        self.assertEqual("B", self.__GetServing())
        self.assertEqual(1, self.__GetScore("B"))
        self.__ClickPlus("A")
        self.assertEqual("A", self.__GetServing())
    # end def

    def test_WinningAt21WithTwoPointLead(self):
        """Reach 20-19, A scores → 21-19 → game over."""
        self.__ReachScore(20, 19)
        self.assertFalse(self.__ModalIsVisible())
        self.__ClickPlus("A")
        self.assertEqual(21, self.__GetScore("A"))
        self.assertEqual(19, self.__GetScore("B"))
        self.assertTrue(self.__ModalIsVisible())
        self.assertIn("比賽結束", self.__page.locator("#modalTitle").text_content())
    # end def

    def test_DeuceContinuesUntilTwoPointLead(self):
        """At 20-20 the game keeps going; needs a 2-point lead to end."""
        self.__ReachScore(20, 20)
        self.assertFalse(self.__ModalIsVisible())
        self.__ClickPlus("A")  # 21-20, diff 1 → still going
        self.assertEqual(21, self.__GetScore("A"))
        self.assertFalse(self.__ModalIsVisible())
        self.__ClickPlus("A")  # 22-20, diff 2 → game over
        self.assertEqual(22, self.__GetScore("A"))
        self.assertTrue(self.__ModalIsVisible())
    # end def

    def test_At29_29FirstTo30Wins(self):
        """Special case: at 29-29 the next point ends the game at 30."""
        self.__ReachScore(29, 29)
        self.assertFalse(self.__ModalIsVisible())
        self.__ClickPlus("A")
        self.assertEqual(30, self.__GetScore("A"))
        self.assertEqual(29, self.__GetScore("B"))
        self.assertTrue(self.__ModalIsVisible())
    # end def

    def test_ScoreLockedAfterGameOver(self):
        """Once gameOver is true, further +/- clicks are no-ops."""
        self.__ReachScore(20, 19)
        self.__ClickPlus("A")  # 21-19, game over
        self.assertTrue(self.__ModalIsVisible())
        self.__CloseModal()
        self.__ClickPlus("A")
        self.__ClickPlus("B")
        self.__ClickMinus("A")
        self.assertEqual(21, self.__GetScore("A"))
        self.assertEqual(19, self.__GetScore("B"))
    # end def

    def test_ResetClearsState(self):
        """Reset zeroes scores, restores A-serves, and shows the reset modal."""
        self.__ClickPlus("A")
        self.__ClickPlus("A")
        self.__ClickPlus("B")
        self.assertEqual((2, 1), (self.__GetScore("A"), self.__GetScore("B")))

        self.__page.locator("#resetButton").click()
        self.assertTrue(self.__ModalIsVisible())
        self.assertIn("重置", self.__page.locator("#modalTitle").text_content())
        self.__CloseModal()

        self.assertEqual(0, self.__GetScore("A"))
        self.assertEqual(0, self.__GetScore("B"))
        self.assertEqual("A", self.__GetServing())

        self.__ClickPlus("B")
        self.assertEqual(1, self.__GetScore("B"))
        self.assertEqual("B", self.__GetServing())
    # end def
# end class


if __name__ == "__main__":
    unittest.main()
