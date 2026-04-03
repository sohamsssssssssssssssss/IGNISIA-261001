export interface AssociationRule {
  antecedents: string[]
  consequent: "repaid" | "defaulted"
  support: number
  confidence: number
  lift: number
  explanation: string
}

export interface FilterState {
  consequent: "all" | "repaid" | "defaulted"
  sortBy: "confidence" | "support" | "lift"
  minConfidence: number
}
