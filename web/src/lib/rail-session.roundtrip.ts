import assert from "node:assert/strict";
import {
  decryptRailSession,
  encryptRailSession,
  maskRailId,
  normalizeRailId,
} from "./rail-session";

process.env.APP_SECRET = process.env.APP_SECRET || "test-rail-secret";

assert.equal(normalizeRailId("korail", "075-232-8289"), "0752328289");
assert.equal(maskRailId("0752328289"), "0752****289");

const session = {
  carrier: "srt" as const,
  id: "010-1234-5678",
  pw: "secret-pw",
  verifiedAt: new Date().toISOString(),
};

const blob = encryptRailSession(session);
const roundTrip = decryptRailSession(blob);
assert.ok(roundTrip);
assert.equal(roundTrip!.carrier, session.carrier);
assert.equal(roundTrip!.id, session.id);
assert.equal(roundTrip!.pw, session.pw);
assert.equal(decryptRailSession("not-valid"), null);

console.log("rail-session tests ok");
