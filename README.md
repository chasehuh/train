# train

Personal **Korail + SRT** booking CLI. One checkout, one `.env`, one command.

This is not a product. It matches how the seats actually get taken:

1. Search the live timetable.
2. Lock a train number (or a short list).
3. `watch` until a seat opens, then hold it.
4. Pay in the official SRT / Korail app before the deadline.

Tight transfers (동대구 5–15 min) are two tickets: SRT first, then Korail ITX/무궁화.

## Install

```bash
cd train
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env   # then fill real values locally
```

Never commit `.env`.

## Commands

```bash
train doctor
train search --carrier srt --dep 수서 --arr 동대구 --date 20260822 --time 125000
train search --carrier ktx --dep 동대구 --arr 청도 --time 213600

train watch --carrier srt --dep 수서 --arr 동대구 \
  --date 20260822 --time 125000 --trains 333,9333 --class any

train watch --carrier ktx --dep 동대구 --arr 청도 \
  --date 20260822 --time 215100 --trains 1123 --class general

train reservations --carrier all
```

`--class any` takes special if it is open, otherwise general. `--monitor-only` logs + Telegram without reserving.

`watch` without `--trains` takes the first matching departure at or after `--time`.

## What we learned using this

- Membership **digits** for Korail beat a hyphenated phone-looking ID.
- SRT 12:50 수서→동대구 is often **333 + 9333** (coupled). Poll both.
- Evening 청도 via 동대구: SRT 367/383 19:24 or 369 20:00, then ITX 1123 / 무궁화 1951.
- Seat-letter filters (특실 A, skip door rows) are optional; sold-out evenings usually mean **any special / any general**.
- Telegram on start + reserve is the phone poke. Pay deadline can be ~10 minutes.
- Korail login needs the in-repo antibot helper. SRT can sit in a netfunnel queue.

## Layout

```
train/          CLI
korail2/        Korail mobile API (antibot + monitor)
SRT/            SRT API
```

Upstream libraries: [carpedm20/korail2](https://github.com/carpedm20/korail2), [ryanking13/SRT](https://github.com/ryanking13/SRT).
