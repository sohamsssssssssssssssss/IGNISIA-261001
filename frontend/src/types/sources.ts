export interface SimilarCase {
  gstin: string
  score: number
  outcome: 'repaid' | 'defaulted' | 'pending'
  similarityScore?: number
  existsInHistory: boolean
}

export interface AppliedRule {
  antecedents: string[]
  consequent: 'repaid' | 'defaulted'
  confidence: number
  support: number
  explanation: string
}

export interface GuidelineReference {
  title: string
  section: string
  excerpt: string
  url?: string
}

export interface SourcesPanelProps {
  similarCases: SimilarCase[]
  rulesApplied: AppliedRule[]
  guidelinesReferenced: GuidelineReference[]
  defaultExpanded?: boolean
  privacyMode?: boolean
}
