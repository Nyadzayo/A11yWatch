export interface Session {
  baseUrl: string
  token: string
  email: string
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface Project {
  id: string
  name: string
  base_url: string
  status: string
}

export interface ProjectCreate {
  name: string
  base_url: string
  url_list?: string[]
  max_pages?: number
  scan_frequency_minutes?: number
}

export type ScanStatus = 'queued' | 'running' | 'succeeded' | 'failed'

export interface Scan {
  id: string
  project_id: string
  status: ScanStatus
  trigger: string
  pages_scanned: number
  total_issues: number
  new_issues: number
  resolved_issues: number
}

export interface Violation {
  id: string
  scan_id: string
  page_url: string
  rule_id: string
  impact: string | null
  help: string | null
  help_url: string | null
  target: string | null
  html_snippet: string | null
  fingerprint: string
}
