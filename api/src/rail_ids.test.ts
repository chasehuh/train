import assert from "node:assert/strict";
import { maskRailId, normalizeRailId } from "./rail_ids.js";

assert.equal(normalizeRailId("korail", "075-232-8289"), "0752328289");
assert.equal(normalizeRailId("korail", "01012345678"), "010-1234-5678");
assert.equal(normalizeRailId("srt", "01012345678"), "010-1234-5678");
assert.equal(normalizeRailId("srt", "user@example.com"), "user@example.com");
assert.equal(maskRailId("0752328289"), "0752****289");

console.log("rail_ids tests ok");
