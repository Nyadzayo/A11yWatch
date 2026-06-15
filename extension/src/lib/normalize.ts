import type { AxeNode, AxeResultItem, AxeResults, Issue, IssueNode, ScanData } from './types'

/** Flatten an axe `target` (which may contain shadow-DOM selector arrays) to one string. */
function selectorOf(target: AxeNode['target']): string {
  return target.map((part) => (Array.isArray(part) ? part.join(' ') : part)).join(' ')
}

function toIssueNode(node: AxeNode): IssueNode {
  return {
    target: selectorOf(node.target),
    html: node.html,
    failureSummary: node.failureSummary ?? null,
  }
}

function toIssue(item: AxeResultItem): Issue {
  return {
    ruleId: item.id,
    impact: item.impact,
    help: item.help,
    description: item.description,
    helpUrl: item.helpUrl,
    tags: item.tags,
    nodes: item.nodes.map(toIssueNode),
  }
}

/** Turn a raw `axe.run()` result into our normalized model.
 *  `incomplete` becomes `needsReview` and is kept out of `issues` entirely. */
export function normalizeAxeResults(raw: AxeResults, url: string): ScanData {
  return {
    url,
    issues: raw.violations.map(toIssue),
    needsReview: raw.incomplete.map(toIssue),
    passCount: raw.passes.length,
    inapplicableCount: raw.inapplicable.length,
  }
}
