import assert from "node:assert/strict";
import { mediaOrigins } from "../src/lib/media.ts";

assert.deepEqual(mediaOrigins('["https://images.invalid/", "https://images.invalid"]').map((url) => url.origin), ["https://images.invalid"]);
for (const raw of [undefined, "malformed", "{}", '["https://images.invalid", 1]', '["http://images.invalid"]', '["https://user:secret@images.invalid"]', '["https://images.invalid/path"]', '["https://images.invalid/?token=secret"]', '["https://images.invalid/#secret"]']) {
  assert.deepEqual(mediaOrigins(raw), [], "Invalid media configuration must stay closed");
}
console.log("Media origin allowlist: PASS");
