/**
 * Run: cd web && npx --yes tsx src/lib/family-backdoor.test.ts
 * Pure unit tests — no network, no secrets logged.
 */
import assert from "node:assert/strict";
import {
  backdoorThrottle,
  isFamilyBackdoorId,
  nextBackdoorFailState,
  parseBackdoorFailCookie,
  serializeBackdoorFailCookie,
  timingSafeStringEqual,
} from "./family-backdoor.ts";

assert.equal(timingSafeStringEqual("abc", "abc"), true);
assert.equal(timingSafeStringEqual("abc", "abd"), false);
assert.equal(timingSafeStringEqual("abc", "ab"), false);
assert.equal(timingSafeStringEqual("", ""), true);

process.env.FAMILY_BACKDOOR_SECRET = "test-secret-value";
assert.equal(isFamilyBackdoorId("test-secret-value"), true);
assert.equal(isFamilyBackdoorId(" test-secret-value "), true);
assert.equal(isFamilyBackdoorId("wrong"), false);
assert.equal(isFamilyBackdoorId(""), false);

const serialized = serializeBackdoorFailCookie({ count: 3, until: 1_700_000_000_000 });
assert.equal(serialized, "3:1700000000000");
assert.deepEqual(parseBackdoorFailCookie(serialized), {
  count: 3,
  until: 1_700_000_000_000,
});
assert.equal(parseBackdoorFailCookie(undefined), null);
assert.equal(parseBackdoorFailCookie("nope"), null);

const now = 1_000_000;
assert.deepEqual(backdoorThrottle(null, now), {
  throttled: false,
  retryAfterMs: 0,
});
assert.deepEqual(
  backdoorThrottle({ count: 2, until: now + 5000 }, now),
  { throttled: true, retryAfterMs: 5000 },
);
assert.deepEqual(
  backdoorThrottle({ count: 2, until: now - 1 }, now),
  { throttled: false, retryAfterMs: 0 },
);

const first = nextBackdoorFailState(null, now);
assert.equal(first.count, 1);
assert.equal(first.until, now + 1000);

const second = nextBackdoorFailState(first, now + 100);
assert.equal(second.count, 2);
assert.equal(second.until, now + 100 + 2000);

console.log("family-backdoor tests ok");
