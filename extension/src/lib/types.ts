// Shared types for the standalone client-side scanner.
// `Axe*` mirror the subset of axe-core's result shape we consume; `Issue`/`ScanData`
// are our normalized model used throughout the popup UI.

export type Impact = 'critical' | 'serious' | 'moderate' | 'minor'

/** A single failing element, as axe reports it. `target` is a CSS selector path. */
export interface AxeNode {
  target: Array<string | string[]>
  html: string
  failureSummary?: string
}

/** One axe rule result (a "rule" = one issue card in the UI). */
export interface AxeResultItem {
  id: string
  impact: Impact | null
  tags: string[]
  description: string
  help: string
  helpUrl: string
  nodes: AxeNode[]
}

/** The relevant slice of the object returned by `axe.run()`. */
export interface AxeResults {
  violations: AxeResultItem[]
  incomplete: AxeResultItem[]
  passes: AxeResultItem[]
  inapplicable: AxeResultItem[]
}

/** A normalized failing element. */
export interface IssueNode {
  target: string
  html: string
  failureSummary: string | null
}

/** A normalized issue — one per axe rule. */
export interface Issue {
  ruleId: string
  impact: Impact | null
  help: string
  description: string
  helpUrl: string
  tags: string[]
  nodes: IssueNode[]
}

/** The full result of one client-side scan. `needsReview` is axe `incomplete` and is
 *  deliberately kept out of `issues` so it never inflates the headline count. */
export interface ScanData {
  url: string
  issues: Issue[]
  needsReview: Issue[]
  passCount: number
  inapplicableCount: number
}
