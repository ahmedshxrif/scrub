# scrub

[![tests](https://github.com/ahmedshxrif/scrub/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmedshxrif/scrub/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![dependencies](https://img.shields.io/badge/dependencies-none-success)
![license](https://img.shields.io/badge/license-MIT-blue)

**Remove personal details from text before you store it or send it to an AI model.** It knows the formats used in the Gulf: Emirates ID numbers, +971 phone numbers and local IBANs, alongside emails, cards and names.

```
$ cat call.txt
Hi, my name is Omar Haddad. Call me on +971 50 123 4567 or mail omar.h@example.com.
Card 4111 1111 1111 1111, ID 784-1990-1234567-6.
It costs 2,199 dirhams and holds 650 litres.

$ scrub call.txt
Hi, my name is [NAME]. Call me on [PHONE] or mail [EMAIL].
Card [CARD], ID [EMIRATES_ID].
It costs 2,199 dirhams and holds 650 litres.
removed: 1 card, 1 email, 1 emirates_id, 1 name, 1 phone
```

Look at the last line of the text. The price and the capacity are still there. Removing personal details is easy if you delete every number; the work is in leaving everything else alone.

## Why

Data-protection law in the UAE, like the GDPR in Europe, expects you to keep personal data out of places it doesn't need to be. If you record customer conversations, or paste support tickets into a language model, names and phone numbers ride along unless something takes them out first.

I needed that something for a product that scores recorded sales conversations. This is the general version.

## Install

```bash
pip install git+https://github.com/ahmedshxrif/scrub
```

No dependencies beyond Python 3.10.

## What it finds

| Label | What | How it is confirmed |
|---|---|---|
| `[EMAIL]` | Email addresses | Shape |
| `[PHONE]` | Numbers starting `+`, `00` or a local `0`, such as `+971 50 123 4567` and `050 123 4567` | Shape and length |
| `[CARD]` | Payment card numbers | Check digit (Luhn) |
| `[EMIRATES_ID]` | Emirates ID numbers, `784-YYYY-NNNNNNN-C` | Check digit |
| `[IBAN]` | Bank account numbers from any country | Check digits (mod 97) |
| `[IP]` | IPv4 addresses | Each part is 0 to 255 |
| `[NAME]` | Names the sentence introduces: "my name is ...", "Dr. ...", "call me ..." | The wording around it |

Digits written in Arabic script (٠٥٠ ١٢٣ ٤٥٦٧) are read the same way as 0 to 9.

## The two rules it follows

**1. A number is only personal when its check digit says so.** A sixteen-digit order number is not a card, and a fifteen-digit reference starting with 784 is not an Emirates ID unless the last digit checks out. This is what keeps prices, model codes and order numbers intact.

**2. Names are not guessed.** Finding names by looking for capital letters removes product names, cities and the first word of every sentence. scrub only takes a name when the sentence says it is one. If you know who is in the conversation, pass their names and it will remove them everywhere:

```bash
scrub call.txt --names people.txt
```

## Use it

```bash
scrub notes.txt                      # cleaned text to the screen
cat notes.txt | scrub > clean.txt    # in a pipe
scrub notes.txt --only email,phone   # just these kinds
scrub notes.txt --json               # the text plus where each thing was found
scrub notes.txt --check              # prints nothing; exits 1 if anything was found
```

`--check` is for automation: put it in front of anything that should never receive personal data and let it fail the step.

The JSON output lists the kind and position of each finding and never repeats the value itself, so the report is as safe to store as the cleaned text.

From Python:

```python
from scrub import redact

result = redact("Mail sara@example.com or call +971 50 123 4567", names=["Sara"])
print(result.text)       # Mail [EMAIL] or call [PHONE]
print(result.counts())   # {'email': 1, 'phone': 1}
```

## Limits, plainly

- **Names are the weak spot.** A name mentioned without an introduction ("then Omar said yes") is missed unless you pass it with `--names`.
- **Phone numbers need a leading `+`, `00` or `0`.** A bare eight-digit number is left alone, because it is far more often an order number than a phone.
- **No addresses, dates of birth or passport numbers yet.**
- It is a filter, not a guarantee. Use it as one layer, and check its output on your own data before trusting it with anything sensitive.

## Tests

```bash
python -m unittest discover -s tests   # 23 tests
```

They cover each kind, the check digits, Arabic-script digits, and a list of things that must be left alone: prices, times, dates, measurements, model codes and order numbers.

## License

MIT
