import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"
import { axe } from "vitest-axe"
import { ErrorBoundary } from "../error-boundary"

describe("ErrorBoundary a11y", () => {
  it("renders children without a11y violations", async () => {
    const { container } = render(
      <ErrorBoundary>
        <p>All good</p>
      </ErrorBoundary>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it("error fallback has no a11y violations", async () => {
    function Boom(): never {
      throw new Error("test crash")
    }
    const { container } = render(
      <ErrorBoundary fallbackMessage="Something broke">
        <Boom />
      </ErrorBoundary>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
