import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scrub import redact  # noqa: E402
from scrub.core import iban_ok, luhn_ok  # noqa: E402

CARD = "4111 1111 1111 1111"          # a well-known test card number
EMIRATES_ID = "784-1990-1234567-6"    # made up, with a correct check digit
IBAN = "AE07 0331 2345 6789 0123 456" # the standard example for the UAE


def kinds(text, **options):
    return [finding.kind for finding in redact(text, **options).findings]


class Checks(unittest.TestCase):
    def test_luhn(self):
        self.assertTrue(luhn_ok(CARD))
        self.assertFalse(luhn_ok("4111 1111 1111 1112"))
        self.assertTrue(luhn_ok(EMIRATES_ID))

    def test_iban(self):
        self.assertTrue(iban_ok(IBAN))
        self.assertTrue(iban_ok("GB82 WEST 1234 5698 7654 32"))
        self.assertFalse(iban_ok("AE07 0331 2345 6789 0123 457"))
        self.assertFalse(iban_ok("hello"))


class Finds(unittest.TestCase):
    def test_email(self):
        self.assertEqual(redact("Write to sara.ali@example.com today.").text, "Write to [EMAIL] today.")

    def test_email_of_any_length_is_removed_whole(self):
        long_local = "a" * 300 + "@example.com"
        self.assertEqual(redact(f"Mail {long_local} now").text, "Mail [EMAIL] now")
        long_label = "sara@" + "b" * 200 + ".example.com"
        self.assertEqual(redact(f"Mail {long_label} now").text, "Mail [EMAIL] now")
        many_labels = "sara@" + ".".join(["mail"] * 20) + ".com"
        self.assertEqual(redact(f"Mail {many_labels} now").text, "Mail [EMAIL] now")
        self.assertEqual(redact("Mail ...sara@example.com.").text, "Mail [EMAIL].")

    def test_things_with_an_at_sign_that_are_not_emails(self):
        for text in ["meet @ 5pm", "@handle said hi", "user@localhost", "a @ b.com", "@", "x@.com"]:
            self.assertNotIn("email", kinds(text), text)

    def test_phones_in_the_usual_gulf_shapes(self):
        for phone in ["+971 50 123 4567", "+971501234567", "00971 4 123 4567", "050 123 4567", "04 123 4567", "+966 55 123 4567", "+44 20 7946 0958"]:
            self.assertEqual(kinds(f"Call {phone} please"), ["phone"], phone)

    def test_card_needs_a_valid_check_digit(self):
        self.assertEqual(kinds(f"Card {CARD}"), ["card"])
        self.assertEqual(kinds("Order 4111 1111 1111 1112"), [])

    def test_emirates_id_is_named_as_such_not_as_a_card(self):
        self.assertEqual(kinds(f"ID {EMIRATES_ID}"), ["emirates_id"])
        self.assertEqual(kinds("ID 784199012345676"), ["emirates_id"])
        self.assertEqual(kinds("ID 784-1990-1234567-5"), [])

    def test_iban(self):
        self.assertEqual(redact(f"Pay into {IBAN} by Friday").text, "Pay into [IBAN] by Friday")

    def test_ip_address(self):
        self.assertEqual(kinds("Server 192.168.1.20 is down"), ["ip"])
        self.assertEqual(kinds("Version 1.2.3.999"), [])

    def test_names_only_when_the_sentence_says_so(self):
        self.assertEqual(redact("Hi, my name is Omar Haddad.").text, "Hi, my name is [NAME].")
        self.assertEqual(redact("Ask for Dr. Layla Nasser at the desk").text, "Ask for Dr. [NAME] at the desk")
        self.assertEqual(kinds("I'm Looking for a fridge in Dubai Mall"), [])
        self.assertEqual(kinds("The Family Hub is in Sharjah"), [])

    def test_known_names_are_removed_wherever_they_appear(self):
        result = redact("Then omar said yes. Omar paid.", names=["Omar"])
        self.assertEqual(result.text, "Then [NAME] said yes. [NAME] paid.")

    def test_digits_in_arabic_script(self):
        self.assertEqual(kinds("اتصل على ٠٥٠ ١٢٣ ٤٥٦٧"), ["phone"])
        self.assertEqual(redact("رقم ٠٥٠ ١٢٣ ٤٥٦٧ الآن").text, "رقم [PHONE] الآن")


class LeavesAlone(unittest.TestCase):
    def test_ordinary_numbers_are_not_personal(self):
        for text in ["It costs 2,199 dirhams.", "Open 09:00 to 22:00 on 17/11/2026.", "It holds 650 litres and is 91.2 cm wide.", "Model RT66CB664622 is in stock.", "Order number 1234567890123456."]:
            self.assertEqual(kinds(text), [], text)

    def test_everything_else_comes_back_untouched(self):
        text = "  Keep\tthe spacing,\n\nthe lines — and the é.  "
        self.assertEqual(redact(text).text, text)

    def test_empty_text(self):
        self.assertEqual(redact("").text, "")

    def test_hostile_input_stays_fast(self):
        import time
        started = time.perf_counter()
        for text in ["a" * 200_000, "1" * 200_000, "+" * 100_000, "a." * 100_000 + "@", ("0 " * 50_000)]:
            redact(text)
        self.assertLess(time.perf_counter() - started, 5)


class Options(unittest.TestCase):
    def test_only_some_kinds(self):
        text = "sara@example.com or +971 50 123 4567"
        self.assertEqual(redact(text, kinds=["email"]).text, "[EMAIL] or +971 50 123 4567")

    def test_unknown_kind_is_an_error(self):
        with self.assertRaises(ValueError):
            redact("x", kinds=["passport"])

    def test_findings_point_at_the_original_text(self):
        text = "Mail sara@example.com now"
        finding = redact(text).findings[0]
        self.assertEqual(text[finding.start:finding.end], "sara@example.com")

    def test_counts(self):
        result = redact("a@b.co and c@d.co and +971 50 123 4567")
        self.assertEqual(result.counts(), {"email": 2, "phone": 1})


class CommandLine(unittest.TestCase):
    def run_cli(self, *args, text=""):
        return subprocess.run([sys.executable, "-m", "scrub.cli", *args], input=text, capture_output=True, text=True, env={"PYTHONPATH": str(ROOT / "src")})

    def test_reads_standard_input(self):
        result = self.run_cli(text="Mail sara@example.com\n")
        self.assertEqual(result.stdout, "Mail [EMAIL]\n")
        self.assertIn("1 email", result.stderr)

    def test_json_never_repeats_what_was_removed(self):
        result = self.run_cli("--json", text="Mail sara@example.com")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["counts"], {"email": 1})
        self.assertNotIn("sara", result.stdout)

    def test_check_mode_fails_when_something_is_found(self):
        self.assertEqual(self.run_cli("--check", text="nothing here").returncode, 0)
        self.assertEqual(self.run_cli("--check", text="sara@example.com").returncode, 1)

    def test_a_missing_file_is_a_clean_error(self):
        result = self.run_cli("nope.txt")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
