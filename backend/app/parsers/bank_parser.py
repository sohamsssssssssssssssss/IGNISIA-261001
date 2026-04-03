import pandas as pd
from app.models.bank import BankStatement, BankTransaction
from datetime import datetime

class BankStatementParser:
    @staticmethod
    def parse_csv(file_path: str, bank_name: str) -> BankStatement:
        df = pd.read_csv(file_path)
        transactions = []
        
        # Simulating bank-specific mappings
        if bank_name == 'SBI':
            date_col, narr_col, dr_col, cr_col, bal_col = 'Txn Date', 'Description', 'Debit', 'Credit', 'Balance'
        elif bank_name == 'HDFC':
            date_col, narr_col, dr_col, cr_col, bal_col = 'Date', 'Narration', 'Withdrawal Amt.', 'Deposit Amt.', 'Closing Balance'
        else:
            raise ValueError(f"Unsupported bank {bank_name}")
            
        for _, row in df.iterrows():
            try:
                date_val = pd.to_datetime(row[date_col]).date()
            except:
                continue
                
            tx = BankTransaction(
                date=date_val,
                narration=str(row[narr_col]),
                withdrawal=float(row[dr_col]) if pd.notnull(row[dr_col]) else 0.0,
                deposit=float(row[cr_col]) if pd.notnull(row[cr_col]) else 0.0,
                balance=float(row[bal_col]) if pd.notnull(row[bal_col]) else 0.0
            )
            transactions.append(tx)
            
        return BankStatement(
            bank_name=bank_name,
            account_number="UNKNOWN",
            period_start=min(tx.date for tx in transactions),
            period_end=max(tx.date for tx in transactions),
            transactions=transactions
        )

    @staticmethod
    def parse_pdf(file_path: str, bank_name: str) -> BankStatement:
        # Placeholder for Camelot/PaddleOCR integration for PDF statements
        pass
