import { describe, expect, it } from "vitest";
import { EMPTY_DRAFT, draftFromRequest, toRequest, validate } from "../features/create/draft";
import { formatDuration } from "./format";
import { parseHash } from "./router";

describe("validate", () => {
  it("requires a prompt and a 5-300 s length", () => {
    expect(validate(EMPTY_DRAFT).prompt).toBeTruthy();
    expect(validate({ ...EMPTY_DRAFT, prompt: "calm", duration: 4 }).duration).toBeTruthy();
    expect(validate({ ...EMPTY_DRAFT, prompt: "calm", duration: 300 })).toEqual({});
  });
  it("checks tempo, seed and sections like the server", () => {
    const base = { ...EMPTY_DRAFT, prompt: "calm" };
    expect(validate({ ...base, tempo: "20" }).tempo).toBeTruthy();
    expect(validate({ ...base, seed: "1.5" }).seed).toBeTruthy();
    expect(validate({ ...base, sections: [{ key: "a", start: "", mood: "x" }] }).sections).toBeTruthy();
    expect(validate({ ...base, sections: [{ key: "a", start: "3", mood: " " }] }).sections).toBeTruthy();
  });
});

describe("toRequest", () => {
  it("omits unset options and sorts sections", () => {
    const r = toRequest({
      ...EMPTY_DRAFT, prompt: " lofi ", duration: 20, mp3: false,
      sections: [{ key: "b", start: "10", mood: "peak" }, { key: "a", start: "0", mood: "calm" }],
    });
    expect(r).toEqual({
      prompt: "lofi", duration_s: 20, loopable: false,
      output: { sample_rate: 48000, target_lufs: -16, formats: ["wav"] },
      sections: [{ start_s: 0, mood: "calm" }, { start_s: 10, mood: "peak" }],
    });
  });
  it("round-trips through draftFromRequest", () => {
    const req = toRequest({ ...EMPTY_DRAFT, prompt: "jazz", tempo: "96", key: "Eb major", seed: "7", loopable: true });
    expect(toRequest(draftFromRequest(req))).toEqual(req);
  });
});

describe("router and format", () => {
  it("parses routes", () => {
    expect(parseHash("#/jobs/0b8f3c2e-1111-4222-8333-944455556666")).toEqual({ name: "job", id: "0b8f3c2e-1111-4222-8333-944455556666" });
    expect(parseHash("#/library")).toEqual({ name: "library" });
    expect(parseHash("#/jobs/not-a-uuid")).toEqual({ name: "create" });
  });
  it("formats durations", () => {
    expect(formatDuration(45)).toBe("45 s");
    expect(formatDuration(90)).toBe("1:30");
    expect(formatDuration(65.5)).toBe("1:05.5");
  });
});
