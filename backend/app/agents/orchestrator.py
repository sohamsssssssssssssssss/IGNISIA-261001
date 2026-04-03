import numpy as np
from typing import Dict, Any, List

class AgentOrchestrator:
    """
    Sequences which external data source to query next using LinUCB contextual bandit
    based on information uncertainty. Default budget is 12 sub-agent calls per borrower.
    """
    def __init__(self, d: int = 22, alpha: float = 1.0):
        # 22-dimensional concept vector
        self.d = d
        self.alpha = alpha
        
        self.agents = ["mca_agent", "litigation_agent", "rbi_agent", "news_agent", "bse_nse", "msme_samadhaan"]
        self.A = {a: np.identity(d) for a in self.agents}
        self.b = {a: np.zeros((d, 1)) for a in self.agents}
        
    def select_next_agent(self, context_vector: list, budget: int) -> str:
        """
        Selects the next agent to query based on LinUCB formula.
        context_vector: The current 22-dimensional Concept Node vector.
        budget: Remaining budget for calls.
        """
        if budget <= 0:
            return None
            
        x = np.array(context_vector).reshape((self.d, 1))
        
        best_agent = None
        max_p = -float('inf')
        
        for agent in self.agents:
            A_inv = np.linalg.inv(self.A[agent])
            theta = A_inv @ self.b[agent]
            
            p = theta.T @ x + self.alpha * np.sqrt(x.T @ A_inv @ x)
            if p > max_p:
                max_p = p
                best_agent = agent
                
        return best_agent
        
    def update(self, agent: str, context_vector: list, reward: float):
        """
        Update the model after querying an agent. Reward is based on information gained 
        (e.g. how much the concept score moved or how confident the system is now).
        """
        x = np.array(context_vector).reshape((self.d, 1))
        self.A[agent] += x @ x.T
        self.b[agent] += reward * x
