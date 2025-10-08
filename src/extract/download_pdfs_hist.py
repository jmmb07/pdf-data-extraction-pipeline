import requests
from pathlib import Path

# output dir
DATA_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
DATA_RAW.mkdir(parents=True, exist_ok=True)

# headers
API_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
}

PDF_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Upgrade-Insecure-Requests": "1",
}


def get_focus_reports(limit: int = 1000):
    """Search list of Focus reports via API
    Example of response
    {
        "conteudo": [
            {
                "DataReferencia": "2025-09-26T03:00:00Z",
                "ImagemCapa": "/content/publicacoes/PublishingImages/Capas/focus/capa-focus.png",
                "Titulo": "Relatório de Mercado - 26/09/2025",
                "Url": "/content/focus/focus/R20250926.pdf",
                "LinkPagina": "/publicacoes/focus/26092025"
            },
        ]
    }
    """
    url = "https://www.bcb.gov.br/api/servico/sitebcb/focus/ultimas"
    params = {"quantidade": str(limit), "filtro": ""}
    resp = requests.get(url, params=params, headers=API_HEADERS)
    resp.raise_for_status()
    return resp.json()["conteudo"] #return list

def download_pdf(pdf_url: str, filename: str):
    """Download PDF if does not exists already"""
    file_path = DATA_RAW / filename
    if file_path.exists():
        print(f"Já existe: {filename}, pulando...")
        return
    resp = requests.get(pdf_url, headers=PDF_HEADERS)
    if resp.status_code == 200:
        with open(file_path, "wb") as f:
            f.write(resp.content)
        print(f"Baixado: {filename}")
    else:
        print(f"Erro {resp.status_code} ao baixar {pdf_url}")

def main():
    relatorios = get_focus_reports()
    for item in relatorios:
        # item example:
        # "Url": "/content/focus/focus/R20250926.pdf"
        pdf_url = "https://www.bcb.gov.br" + item["Url"]
        # nome do arquivo → focus_YYYYMMDD.pdf
        data_ref = item["DataReferencia"][:10]  # "2025-09-26"
        filename = f"focus_{data_ref}.pdf"
        download_pdf(pdf_url, filename)

if __name__ == "__main__":
    main()