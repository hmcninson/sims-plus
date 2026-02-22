import { describe, it, expect, expectTypeOf } from "vitest";
import type { ActionResult } from "@/types";

// ---------------------------------------------------------------------------
// ActionResult discriminated union tests
// ---------------------------------------------------------------------------

describe("ActionResult type", () => {
  it("success: true narrows to data being accessible", () => {
    const result: ActionResult<{ name: string }> = {
      success: true,
      data: { name: "Kwame" },
    };

    if (result.success) {
      // After narrowing, data is typed and accessible
      expect(result.data.name).toBe("Kwame");
      // error and code should be undefined on the success branch
      expect(result.error).toBeUndefined();
      expect(result.code).toBeUndefined();
    }
  });

  it("success: false narrows to error being accessible", () => {
    const result: ActionResult<{ name: string }> = {
      success: false,
      error: "Something went wrong",
      code: 500,
    };

    if (!result.success) {
      // After narrowing, error is a string
      expect(result.error).toBe("Something went wrong");
      expect(result.code).toBe(500);
      // data should be undefined on the failure branch
      expect(result.data).toBeUndefined();
    }
  });

  it("both .data and .error are accessible without narrowing (backward-compatible)", () => {
    // This tests that a consumer who doesn't narrow can still access
    // .data and .error without TypeScript errors at runtime
    const success: ActionResult<string> = {
      success: true,
      data: "hello",
    };

    const failure: ActionResult<string> = {
      success: false,
      error: "fail",
    };

    // Without narrowing, both fields exist (one is undefined)
    expect(success.data).toBe("hello");
    expect(success.error).toBeUndefined();

    expect(failure.data).toBeUndefined();
    expect(failure.error).toBe("fail");
  });

  it("ActionResult<void> success branch has data: undefined", () => {
    // void-typed actions (like logout) have data as void/undefined
    const result: ActionResult = { success: true, data: undefined };

    expect(result.success).toBe(true);
    expect(result.data).toBeUndefined();
  });

  it("code is optional on failure branch", () => {
    const result: ActionResult<string> = {
      success: false,
      error: "Network error",
      // code not provided
    };

    if (!result.success) {
      expect(result.code).toBeUndefined();
      expect(result.error).toBe("Network error");
    }
  });
});

// ---------------------------------------------------------------------------
// Compile-time type assertions (these fail at build time, not runtime)
// ---------------------------------------------------------------------------

describe("ActionResult compile-time type checks", () => {
  it("success branch data type matches generic parameter", () => {
    type Result = ActionResult<{ id: string; name: string }>;

    // On success branch, data should be { id: string; name: string }
    expectTypeOf<Extract<Result, { success: true }>["data"]>().toEqualTypeOf<{
      id: string;
      name: string;
    }>();
  });

  it("failure branch error is string", () => {
    type Result = ActionResult<string>;

    expectTypeOf<
      Extract<Result, { success: false }>["error"]
    >().toEqualTypeOf<string>();
  });

  it("failure branch code is optional number", () => {
    type Result = ActionResult<string>;

    expectTypeOf<
      Extract<Result, { success: false }>["code"]
    >().toEqualTypeOf<number | undefined>();
  });
});
