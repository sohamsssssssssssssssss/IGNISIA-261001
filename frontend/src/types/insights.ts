export interface AssociationRule {
  id?: string
  antecedents: string[]
  consequent: "repaid" | "defaulted"
  support: number
  confidence: number
  lift: number
  record_count?: number
  explanation: string
  generated_at?: string
}

export interface FilterState {
  consequent: "all" | "repaid" | "defaulted"
  sortBy: "confidence" | "support" | "lift"
  minConfidence: number
}
