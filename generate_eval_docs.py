import csv
import sys
import subprocess

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

def create_annual_report_pdf():
    pdf_path = "document1.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph("Final Audited Financials FY24", styles['Title']))
    elements.append(Spacer(1, 20))
    
    # Text paragraph with a risk keyword
    elements.append(Paragraph("We have audited the accompanying financial statements. The auditor has issued an emphasis of matter regarding disputed tax liabilities in Gujarat.", styles['Normal']))
    elements.append(Spacer(1, 20))

    # P&L Table to trigger the P&L detector in pdfplumber
    data = [
        ["Particulars", "FY24 (\u20b9 Cr)", "FY23 (\u20b9 Cr)"],
        ["Revenue from Operations", "42.50", "38.10"],
        ["Other Income", "1.20", "0.90"],
        ["Total Revenue", "43.70", "39.00"],
        ["Cost of Materials", "18.40", "16.20"],
        ["Employee Benefits", "8.50", "7.80"],
        ["EBITDA", "8.90", "7.10"],
        ["Profit After Tax (PAT)", "4.20", "3.60"]
    ]

    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    
    elements.append(t)
    doc.build(elements)
    print("Created document1.pdf")

def create_alm_csv():
    with open("Q3_data.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Maturity Bucket", "Inflows", "Outflows", "Net Mismatch", "Cumulative Gap"])
        writer.writerow(["1-14 Days", "12.5", "18.2", "-5.7", "-5.7"])
        writer.writerow(["15-28 Days", "8.4", "6.1", "2.3", "-3.4"])
        writer.writerow(["1-3 Months", "22.1", "19.5", "2.6", "-0.8"])
        writer.writerow(["3-6 Months", "35.0", "28.0", "7.0", "6.2"])
    print("Created Q3_data.csv")

def create_shareholding_csv():
    with open("report_final_v2.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Category of Shareholder", "No. of Shares", "Percentage Holding", "Pledge %"])
        writer.writerow(["Promoter & Promoter Group", "7200000", "72.0%", "0%"])
        writer.writerow(["Foreign Institutional Investors (FII)", "1500000", "15.0%", "0%"])
        writer.writerow(["Domestic Institutional Investors (DII)", "800000", "8.0%", "0%"])
        writer.writerow(["Public", "500000", "5.0%", "0%"])
    print("Created report_final_v2.csv")

if __name__ == "__main__":
    create_annual_report_pdf()
    create_alm_csv()
    create_shareholding_csv()
