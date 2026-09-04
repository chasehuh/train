# train

Personal **Korail + SRT** CLI. Search, poll, hold a seat, pay in the official app.

After **2026-09-01** high-speed integration, former SRT trains are booked on **Korail** (`--carrier ktx`) as KTX / KTX-산천. The SRT client is still here for the old app path.

This is not a product. One checkout, one `.env`, pay yourself before the hold expires.

## Seat choice

Both carriers can keep a **letter** (`--seat-letter A`). They do not use the same API.

| Carrier | How a letter is chosen |
|---|---|
| **Korail / KTX** | Residual seat map (`TrainResearch` + `ResidualSeatsResearch`) → specified-seat reserve. If the map is empty, auto-assign then `ReservationList` (`hidPnrNo`). Wrong letter → cancel and retry. |
| **SRT** | No public seat map. `window_seat` hint (A/D = window, B/C = aisle), then reserve. Ticket dump has `호차` + `seatNo`. Wrong letter → cancel and retry. |

`--class special|general|any` is grade. `--seat-letter` is the column.

Holds are unpaid. Pay in 코레일+ / SRT.

## Install

```bash
cd train
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Never commit `.env`. Korail membership IDs are digits. SRT uses `SRT_ID` / `SRT_PW`.

## Commands

```bash
train doctor
train search --carrier ktx --dep 수서 --arr 동대구 --date 20260904 --time 173000
train reservations --carrier all

# Korail: map A first, else reserve+cancel
train watch --carrier ktx --dep 수서 --arr 동대구 \
  --date 20260904 --time 173000 --end-time 183000 \
  --trains 347,351,349 --class special --seat-letter A --interval 3

# SRT: window hint + reserve+cancel
train watch --carrier srt --dep 수서 --arr 동대구 \
  --date 20260822 --time 125000 --trains 333,9333 \
  --class special --seat-letter A --interval 3
```

`--monitor-only` logs + Telegram without reserving. No `--trains` → first match at or after `--time`.

## Notes

- Tight 청도 last-mile is a **second** Korail ticket (ITX / 무궁화).
- Telegram fires on watch start and on a kept hold. Pay window can be ~10 minutes.
- Korail login needs the in-repo antibot helper.
- Upstream: [carpedm20/korail2](https://github.com/carpedm20/korail2), [ryanking13/SRT](https://github.com/ryanking13/SRT) (archived 2026-08-30), [bsangmin/letskorail](https://github.com/bsangmin/letskorail) seat-map endpoints.

```
train/     CLI
korail2/   Korail mobile API (antibot, residual seats, holds)
SRT/       SRT API
```
