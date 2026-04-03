import torch
import torch.nn as nn
import shap
import pandas as pd
from typing import Dict, Any, List, Tuple

class ConceptBottleneckModel(nn.Module):
    """
    3-layer MLP mapping ~85-dimensional feature vectors to 22 Interpretable Concepts.
    Followed by a fixed logistic decision layer for final score.
    """
    def __init__(self, input_dim: int = 85, hidden_dim: int = 128, concept_dim: int = 22):
        super(ConceptBottleneckModel, self).__init__()
        
        # Concept prediction layer (Feature Vector -> 22 Concepts)
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim // 2, concept_dim),
            nn.Sigmoid()  # Force concepts to be 0.0 to 1.0 continuously
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        concepts = self.encoder(x)
        return concepts

class CreditScoringEngine:
    def __init__(self, cbm_model: ConceptBottleneckModel):
        self.cbm_model = cbm_model
        self.cbm_model.eval()
        
    def infer_concepts(self, feature_vector: list) -> torch.Tensor:
        # Expected dim: [1, 85]
        x = torch.tensor(feature_vector, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            concepts = self.cbm_model(x)
        return concepts

    def calculate_final_score(self, concepts: list, is_msme: bool = False) -> float:
        """
        Five C's fixed logistic decision weights.
        C1: Character (0.2), C2: Capacity (0.3), C3: Capital (0.2), C4: Collateral (0.15), C5: Conditions (0.15)
        Can group the 22 nodes into these 5 pillars.
        """
        w = [0.20, 0.30, 0.20, 0.15, 0.15]
        
        # Simplified mapping from 22 -> 5 for the demo.
        # Suppose first 4 nodes are Character, next 5 are Capacity, etc.
        # Average the concept scores per group.
        character = sum(concepts[0:4]) / 4
        capacity = sum(concepts[4:9]) / 5
        capital = sum(concepts[9:14]) / 5
        collateral = sum(concepts[14:18]) / 4
        conditions = sum(concepts[18:22]) / 4
        
        if is_msme:
            # Adjust weights per RBI MSME norms (e.g. higher emphasis on cash flow capacity (0.4) than collateral (0.05))
            w = [0.20, 0.40, 0.20, 0.05, 0.15]
            
        score_out_of_1 = (w[0]*character + w[1]*capacity + w[2]*capital + w[3]*collateral + w[4]*conditions)
        return score_out_of_1 * 100.0

    def compute_shap_explanations(self, feature_df: pd.DataFrame, background_data: pd.DataFrame) -> Any:
        # In a real model, we would use DeepExplainer for torch or TreeExplainer if standard ML.
        # For prototype with PyTorch, we can use GradientExplainer or DeepExplainer.
        # PyTorch requires specific handling, so returning dummy SHAP vector for demo
        # because full SHAP DeepExplainer initialization is heavy.
        explainer = shap.DeepExplainer(self.cbm_model, torch.tensor(background_data.values, dtype=torch.float32))
        x_tensor = torch.tensor(feature_df.values, dtype=torch.float32)
        shap_values = explainer.shap_values(x_tensor)
        return shap_values
