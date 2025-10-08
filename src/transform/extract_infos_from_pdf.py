import re
import pandas as pd
from pathlib import Path
import pdfplumber
from pdfminer.high_level import extract_text
from pdf2image import convert_from_path
import pytesseract
import tempfile
import shutil

RAW_DIR = Path("data/raw")
PROC_DIR = Path("data/processed")
PROC_DIR.mkdir(parents=True, exist_ok=True)

tmpdir = Path("data/tmp_ocr")
tmpdir.mkdir(parents=True, exist_ok=True)

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# mapping with historical name variations
INDICADORES = {
    # IPCA
    "IPCA (variação %)": "IPCA",
    "IPCA (%)": "IPCA",
    
    # PIB
    "PIB Total (variação % sobre ano anterior)": "PIB",
    "PIB (% de crescimento)": "PIB",
    "PIB Total": "PIB",
    
    # Câmbio
    "Câmbio (R$/US$)": "Câmbio",
    "Taxa de câmbio - Fim de período (R$/US$)": "Câmbio",
    "Taxa de câmbio (R$/US$)": "Câmbio",
    
    # Selic
    "Selic (% a.a)": "Selic",
    "Meta Selic - fim de período (% a.a.)": "Selic",
    "Meta Selic (% a.a.)": "Selic",
    
    # IGP-M
    "IGP-M (variação %)": "IGP-M",
    "IGP-M (%)": "IGP-M",
    
    # IPCA Administrados
    "IPCA Administrados (variação %)": "IPCA Administrados",
    "Preços administrados (%)": "IPCA Administrados",
    
    # Produção Industrial
    "Produção Industrial (% de crescimento)": "Produção Industrial",
    
    # Contas externas
    "Conta corrente (US$ bilhões)": "Conta Corrente",
    "Conta Corrente (US$ bilhões)": "Conta Corrente",
    "Balança comercial (US$ bilhões)": "Balança Comercial",
    "Balança Comercial (US$ bilhões)": "Balança Comercial",
    "Investimento direto no país (US$ bilhões)": "Investimento Direto",
    "Investimento Direto no País (US$ bilhões)": "Investimento Direto",
    
    # Setor público
    "Dívida líquida do setor público (% do PIB)": "Dívida Líquida",
    "Dívida Líquida do Setor Público (% do PIB)": "Dívida Líquida",
    "Resultado primário (% do PIB)": "Resultado Primário",
    "Resultado Primário (% do PIB)": "Resultado Primário",
    "Resultado nominal (% do PIB)": "Resultado Nominal",
    "Resultado Nominal (% do PIB)": "Resultado Nominal",
}

def extract_text_safely(file_path: Path) -> str:
    """Tries pdfplumber → pdfminer → OCR."""
    text = None
    is_from_ocr = False

    # 1. try pdfplumber
    try:
        with pdfplumber.open(file_path) as pdf:
            text = pdf.pages[0].extract_text()
    except Exception:
        pass

    # 2. if it fails or has (cid:xx), try pdfminer
    if not text or "(cid:" in text:
        text = extract_text(str(file_path))

    # 3. if it still fails, apply OCR
    if not text or "(cid:" in text:
        is_from_ocr = True
        print(f" Using OCR for {file_path.name} ...")
        with tempfile.TemporaryDirectory(dir=tmpdir) as tmp:
            images = convert_from_path(file_path, dpi=300, output_folder=str(tmpdir))
            text = ""
            for img in images:
                text += pytesseract.image_to_string(img, lang="por") + "\n"
    
    return text, is_from_ocr

def extract_focus_values(line: str, years: list, is_from_ocr: bool = False) -> list:
    """
    Extracts the 4 main values from a line of the Focus Report.
    
    Args:
        line: text line from the PDF
        years: list with the detected years
        is_from_ocr: True if the text came from OCR (without commas), False if native
    """
    values = []
    
    if not is_from_ocr:
        # NATIVE case: get numbers with a comma (e.g., "4,01")
        numbers = re.findall(r"-?\d+,\d+", line)
        if len(numbers) >= 14:
            # Fixed indexes when there are commas
            indexes = [2, 6, 10, 13]
            values = [float(numbers[i].replace(",", ".")) for i in indexes if i < len(numbers)]
    else:
        # OCR case: get all numbers and apply the 3-digit rule
        numbers = re.findall(r"-?\d+\.?\d*", line.replace(",","."))
        numbers = [n for n in numbers if n and n != '.']
        
        if len(numbers) >= 18:  # Adjusted for the new indexes
            indexes = [2, 7, 12, 17]
            for idx in indexes:
                if idx < len(numbers):
                    num_str = numbers[idx]
                    
                    # If it has exactly 3 digits WITHOUT a period, insert a period (365 -> 3.65)
                    if '.' not in num_str and len(num_str) == 3 and not num_str.startswith('-'):
                        value = float(num_str[0] + '.' + num_str[1:])
                    # If it has 4 digits WITHOUT a period, insert a period (4001 -> 40.01)
                    elif '.' not in num_str and len(num_str) == 4 and not num_str.startswith('-'):
                        value = float(num_str[:2] + '.' + num_str[2:])
                    else:
                        value = float(num_str)
                    
                    values.append(value)
    
    return values if len(values) == len(years) else []


def parse_focus_text(text: str, ref_date: str, is_from_ocr: bool = False) -> pd.DataFrame:
    records = []
    lines = text.split("\n")
    header_line = next(
        (line for line in lines if re.search(r"(\d{4}\s+){3}\d{4}", line)),
        None
    )
    if not header_line:
        return pd.DataFrame()  # ignore if years were not found
    years = re.findall(r"\d{4}", header_line)

    for line in lines:
        clean_line = line.strip()
        
        for raw_name, clean_name in INDICADORES.items():
            if clean_line.startswith(raw_name):
                # the value extraction will depend on whether it's via OCR or not
                values = extract_focus_values(line, years, is_from_ocr)
                
                if values:
                    for year, value in zip(years, values):
                        records.append([ref_date, clean_name, year, value])
                    # print(f"{clean_name}: {values}")
                break

    return pd.DataFrame(records, columns=["ref_date", "indicator", "year", "value"])



def process_all_pdfs():
    all_dfs = []
    for pdf_file in sorted(RAW_DIR.glob("*.pdf")):
    
        ref_date = pdf_file.stem.split("_")[-1]
        print(f"Processing {pdf_file.name} ...")
        try:
            text, is_from_ocr = extract_text_safely(pdf_file)
            df = parse_focus_text(text, ref_date, is_from_ocr)
            if not df.empty:
                all_dfs.append(df)
        except Exception as e:
            print(f"Error processing {pdf_file.name}: {e}")

    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
        output = PROC_DIR / "focus_annual.csv"
        final_df.to_csv(output, index=False)
        print("Processing complete:", output)
    else:
        print("No PDF processed successfully.")

    shutil.rmtree(tmpdir)

if __name__ == "__main__":
    process_all_pdfs()