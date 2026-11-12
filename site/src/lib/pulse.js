/* What is new here, and the archive in numbers: the kit computes it at build time from this archive's own logs (kit/docs/whats-new.md).
   This file is the only Luwinski-specific part: which JSON is which, and the one count no log holds.
   The corrections list lives inside the register (register.json, drawn on /corrections/ by the kit's Corrections component) and
   carries no date, so it gives no card; the work list is the archive's own and is counted, not drawn. */
import { buildPulse } from "@daviddef/archive-kit/lib/pulse.js";
import { loadReceipts } from "@daviddef/archive-kit/lib/receipts.js";
import searched from "../data/searched.json";
import register from "../data/register.json";
import worklist from "../data/worklist.json";

export const pulse = buildPulse({
  searched, worklist,
  corrections: register.corrections,
  counts: { people: register.people.length },
  // The Record Atlas's receipts for this archive's rows (kit/docs/whats-new-receipts.md). null on any failure, never throws, never fails a build.
  receipts: await loadReceipts("luwinski"),
});
