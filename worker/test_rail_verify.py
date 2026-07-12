"""Unit tests for rail id normalization / masking (no live carrier calls)."""

from __future__ import annotations

import unittest

from worker.rail_verify import mask_rail_id, normalize_rail_id


class NormalizeRailIdTests(unittest.TestCase):
    def test_korail_membership_strips_hyphens(self) -> None:
        self.assertEqual(
            normalize_rail_id("korail", "075-232-8289"),
            "0752328289",
        )

    def test_korail_phone_keeps_hyphens(self) -> None:
        self.assertEqual(
            normalize_rail_id("korail", "01012345678"),
            "010-1234-5678",
        )
        self.assertEqual(
            normalize_rail_id("korail", "010-1234-5678"),
            "010-1234-5678",
        )

    def test_srt_phone_hyphenated(self) -> None:
        self.assertEqual(
            normalize_rail_id("srt", "01012345678"),
            "010-1234-5678",
        )


    def test_srt_membership_strips_hyphens(self) -> None:
        self.assertEqual(
            normalize_rail_id("srt", "228-165-2598"),
            "2281652598",
        )
        self.assertEqual(
            normalize_rail_id("srt", "2281652598"),
            "2281652598",
        )

    def test_srt_email_passthrough(self) -> None:
        self.assertEqual(
            normalize_rail_id("srt", "user@example.com"),
            "user@example.com",
        )

    def test_mask(self) -> None:
        self.assertEqual(mask_rail_id("0752328289"), "0752****289")


if __name__ == "__main__":
    unittest.main()
