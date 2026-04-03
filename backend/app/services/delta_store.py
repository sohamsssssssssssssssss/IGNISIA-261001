import pandas as pd
from deltalake import write_deltalake, DeltaTable
from app.models.feature_vector import BorrowerFeatureVector
import os

class FeatureStoreService:
    def __init__(self, storage_path: str = "/tmp/delta_feature_store"):
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)

    def save_feature_vector(self, feature_vector: BorrowerFeatureVector):
        """
        Store feature vector into local Delta Lake using delta-rs (deltalake python package).
        """
        df = pd.DataFrame([feature_vector.model_dump()])
        
        # Flatten dictionary column
        for col in df.columns:
            if isinstance(df[col].iloc[0], dict):
                df[col] = df[col].astype(str)
                
        # Write to Delta table (append mode)
        write_deltalake(
            self.storage_path,
            df,
            mode="append"
        )
        
    def read_feature_vector(self, gstin: str) -> pd.DataFrame:
        """
        Read borrower's latest feature vector from Delta table.
        """
        if not os.path.exists(os.path.join(self.storage_path, "_delta_log")):
            return pd.DataFrame()
            
        dt = DeltaTable(self.storage_path)
        df = dt.to_pandas()
        return df[df['gstin'] == gstin]
