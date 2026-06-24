import type { Issue, IssueNode } from './types'

/** Curated, plain-language remediation for the most common axe rules. Keep these
 *  actionable and specific — the per-element axe `failureSummary` is the fallback for
 *  everything not covered here. */
export const FIX_MAP: Record<string, string> = {
  'color-contrast':
    'Increase the contrast between the text and its background. WCAG AA needs at least ' +
    '4.5:1 for normal text and 3:1 for large text (18.66px bold or 24px+). Darken the ' +
    'text or lighten the background until it passes.',
  'image-alt':
    'Give the image a text alternative. Add a concise alt attribute describing the image ' +
    '(alt="Annual revenue chart"), or alt="" if it is purely decorative so screen readers ' +
    'skip it.',
  'input-image-alt':
    'Add an alt attribute to the image button describing the action it performs ' +
    '(e.g. alt="Search").',
  label:
    'Associate a label with the form control — either wrap it in a <label>, point a ' +
    '<label for="id"> at it, or add an aria-label / aria-labelledby. A placeholder is not ' +
    'a label.',
  'link-name':
    'Give the link discernible text. Add visible text between the <a> tags, or an ' +
    'aria-label, so its purpose is clear out of context. Icon-only links need an ' +
    'accessible name.',
  'button-name':
    'Give the button an accessible name — visible text inside the <button>, or an ' +
    'aria-label for icon-only buttons.',
  'heading-order':
    'Fix the heading hierarchy so levels are not skipped (an <h2> should not jump to an ' +
    '<h4>). Headings should describe structure, not be chosen for their size.',
  'landmark-one-main':
    'Wrap the primary content in a single <main> landmark so assistive tech can jump ' +
    'straight to it. There should be exactly one per page.',
  region:
    'Move this content inside a landmark region (<header>, <nav>, <main>, <footer>, or a ' +
    'labelled <section>) so it is reachable by landmark navigation.',
  'aria-required-attr':
    'Add the ARIA attributes this role requires. For example role="checkbox" needs ' +
    'aria-checked. Check the role’s required states and properties.',
  'aria-allowed-attr':
    'Remove ARIA attributes that are not allowed on this element/role, or change the role ' +
    'so the attributes are valid for it.',
  'aria-roles':
    'Use a valid ARIA role, spelled correctly. Prefer a native HTML element with built-in ' +
    'semantics over a custom role where possible.',
  'aria-valid-attr-value':
    'Correct the ARIA attribute value — e.g. an aria-labelledby / aria-describedby must ' +
    'reference the id of an element that exists on the page.',
  'document-title':
    'Add a non-empty <title> in the document <head> that describes the page.',
  'html-has-lang':
    'Add a lang attribute to the <html> element (e.g. <html lang="en">) so the page ' +
    'language is announced correctly.',
}

/** Curated guidance for a rule, or null if we have no curated entry. */
export function fixGuidance(ruleId: string): string | null {
  return FIX_MAP[ruleId] ?? null
}

/** Best available fix text for a failing element: curated guidance → axe per-element
 *  failureSummary → the rule description. */
export function fixForNode(issue: Issue, node: IssueNode): string {
  return fixGuidance(issue.ruleId) ?? node.failureSummary ?? issue.description
}
