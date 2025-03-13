import requests
from bs4 import BeautifulSoup, Comment, Doctype
import csv
import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def extrair_dados_site(url):
    # Fazer a requisição HTTP
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Verifica se a resposta foi bem sucedida
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar o site {url}: {e}")
        return None
    
    # Parsear o conteúdo HTML
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Extrair metadados do cabeçalho
    meta_dados = obter_meta_dados(soup)
    
    # Extrair todos os elementos na ordem em que aparecem
    elementos_em_ordem = extrair_elementos_em_ordem(soup)
    
    # Extrair nome do curso a partir da URL ou do título
    nome_curso = obter_nome_curso(url, soup)
    
    return {
        "url": url,
        "nome_curso": nome_curso,
        "titulo": obter_titulo(soup),
        "meta_dados": meta_dados,
        "elementos_em_ordem": elementos_em_ordem
    }

def obter_nome_curso(url, soup):
    # Tentar extrair o nome do curso da URL
    partes_url = url.split("/")
    nome_curso = partes_url[-1] if partes_url[-1] else partes_url[-2]
    
    # Substituir hífens por espaços e capitalizar
    nome_curso = nome_curso.replace("-", " ").title()
    
    # Alternativa: tentar usar um elemento H1 específico da página
    h1 = soup.find("h1")
    if h1 and h1.text.strip():
        nome_curso = h1.text.strip()
    
    return nome_curso

def obter_titulo(soup):
    # Extrair o título da página
    titulo = soup.title.text if soup.title else "Sem título"
    return titulo.strip()

def obter_meta_dados(soup):
    # Extrair meta tags importantes
    meta_dados = {}
    
    # Meta description
    meta_description = soup.find("meta", attrs={"name": "description"})
    if meta_description:
        meta_dados["description"] = meta_description.get("content", "")
    
    # Meta keywords
    meta_keywords = soup.find("meta", attrs={"name": "keywords"})
    if meta_keywords:
        meta_dados["keywords"] = meta_keywords.get("content", "")
        
    # Open Graph meta tags
    og_title = soup.find("meta", property="og:title")
    if og_title:
        meta_dados["og:title"] = og_title.get("content", "")
    
    og_description = soup.find("meta", property="og:description")
    if og_description:
        meta_dados["og:description"] = og_description.get("content", "")
    
    return meta_dados

def extrair_elementos_em_ordem(soup):
    # Esta função vai extrair todos os elementos do body na ordem em que aparecem
    elementos = []
    
    # Começamos com o body
    body = soup.body
    if not body:
        return elementos
    
    # Função recursiva para processar todos os elementos
    def processar_elemento(elemento):
        # Ignora comentários, scripts e estilos
        if elemento.name in ['script', 'style', None] or isinstance(elemento, (Comment, Doctype)):
            return
        
        # Para elementos de texto, apenas pegamos o texto se não for espaço em branco
        if isinstance(elemento, str):
            texto = elemento.strip()
            if texto:
                elementos.append({
                    "tipo": "texto",
                    "conteudo": texto
                })
            return
        
        # Para elementos HTML, extraímos informações relevantes
        info = {
            "tipo": elemento.name,
            "conteudo": elemento.text.strip() if elemento.text.strip() else None
        }
        
        # Adicionar atributos específicos para diferentes tipos de elementos
        if elemento.name == 'a':
            info["href"] = elemento.get("href", "")
        elif elemento.name == 'img':
            info["src"] = elemento.get("src", "")
            info["alt"] = elemento.get("alt", "")
        elif elemento.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'div']:
            # Para estes elementos, só queremos o conteúdo se não for processado pelos filhos
            pass
        elif elemento.name == 'form':
            info["action"] = elemento.get("action", "")
            info["method"] = elemento.get("method", "GET")
        elif elemento.name == 'input':
            info["name"] = elemento.get("name", "")
            info["type"] = elemento.get("type", "text")
            info["value"] = elemento.get("value", "")
        elif elemento.name == 'table':
            # Para tabelas, não incluímos o conteúdo aqui, pois será processado pelos filhos
            info["conteudo"] = None
        
        # Adicionar o elemento atual à lista se tiver conteúdo ou for um elemento específico
        if info["conteudo"] or elemento.name in ['img', 'input', 'br', 'hr']:
            elementos.append(info)
        
        # Processar filhos recursivamente
        for filho in elemento.children:
            processar_elemento(filho)
    
    processar_elemento(body)
    return elementos

def salvar_dados_consolidados(todos_dados, nome_arquivo="todos_cursos"):
    # Criar diretório para os dados se não existir
    if not os.path.exists("dados_extraidos"):
        os.makedirs("dados_extraidos")
    
    # Timestamp para nome único do arquivo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Salvar todos os elementos em ordem em um único arquivo CSV, agrupados por curso
    with open(f"dados_extraidos/{nome_arquivo}_elementos_em_ordem_{timestamp}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Curso", "URL", "Tipo", "Conteúdo", "Atributos Adicionais"])
        
        for dados in todos_dados:
            nome_curso = dados["nome_curso"]
            url = dados["url"]
            for elem in dados["elementos_em_ordem"]:
                tipo = elem["tipo"]
                conteudo = elem.get("conteudo", "")
                
                # Preparar atributos adicionais como string
                atributos = {}
                for chave, valor in elem.items():
                    if chave not in ["tipo", "conteudo"]:
                        atributos[chave] = valor
                
                atributos_str = json.dumps(atributos) if atributos else ""
                writer.writerow([nome_curso, url, tipo, conteudo, atributos_str])
    
    # 2. Salvar um arquivo JSON com toda a estrutura para análise mais detalhada
    with open(f"dados_extraidos/{nome_arquivo}_completo_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump(todos_dados, f, ensure_ascii=False, indent=4)
    
    # 3. Salvar um arquivo de texto estruturado para fácil leitura
    with open(f"dados_extraidos/{nome_arquivo}_estruturado_{timestamp}.txt", "w", encoding="utf-8") as f:
        for dados in todos_dados:
            f.write(f"==========================================\n")
            f.write(f"CURSO: {dados['nome_curso']}\n")
            f.write(f"URL: {dados['url']}\n")
            f.write(f"TÍTULO: {dados['titulo']}\n\n")
            
            f.write("META DADOS:\n")
            for chave, valor in dados["meta_dados"].items():
                f.write(f"  {chave}: {valor}\n")
            f.write("\n")
            
            f.write("CONTEÚDO EM ORDEM:\n")
            for i, elem in enumerate(dados["elementos_em_ordem"]):
                tipo = elem["tipo"]
                conteudo = elem.get("conteudo", "")
                
                # Formatação especial para cabeçalhos
                if tipo in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    f.write(f"\n{'-' * 40}\n{tipo.upper()}: {conteudo}\n{'-' * 40}\n")
                elif tipo == 'p' and conteudo:
                    f.write(f"\n{conteudo}\n")
                elif tipo == 'a' and conteudo:
                    href = elem.get("href", "")
                    f.write(f"Link: {conteudo} -> {href}\n")
                elif tipo == 'img':
                    src = elem.get("src", "")
                    alt = elem.get("alt", "")
                    f.write(f"Imagem: {alt} ({src})\n")
                elif conteudo:
                    f.write(f"{tipo}: {conteudo}\n")
            
            f.write("\n\n")

def extrair_dados_paralelo(urls, max_workers=5):
    """Extrai dados de múltiplas URLs em paralelo usando ThreadPoolExecutor"""
    todos_dados = []
    
    print(f"Iniciando extração de dados de {len(urls)} cursos...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submeter todas as tarefas
        futures = {executor.submit(extrair_dados_site, url): url for url in urls}
        
        # Processar resultados conforme concluídos
        for future in as_completed(futures):
            url = futures[future]
            try:
                dados = future.result()
                if dados:
                    todos_dados.append(dados)
                    print(f"✓ Extração concluída para: {dados['nome_curso']}")
                else:
                    print(f"✗ Falha ao extrair dados de: {url}")
            except Exception as e:
                print(f"✗ Erro ao processar {url}: {e}")
    
    return todos_dados

def main():
    # Lista de URLs dos cursos para extrair
    urls = [
        "https://unifor.br/web/graduacao/ciencia-da-computacao",
        "https://unifor.br/web/graduacao/analise-e-desenvolvimento-de-sistema",
        "https://unifor.br/web/graduacao/engenharia-da-computacao",
        "https://unifor.br/web/graduacao/direito",
        "https://unifor.br/web/graduacao/cinema-e-audiovisual"
      
    ]
    
    # Extrair dados de todos os cursos em paralelo
    todos_dados = extrair_dados_paralelo(urls)
    
    if not todos_dados:
        print("Nenhum dado foi extraído com sucesso.")
        return
    
    # Exibir resumo dos dados extraídos
    print("\n=== RESUMO DOS DADOS EXTRAÍDOS ===")
    print(f"Total de cursos extraídos: {len(todos_dados)}")
    
    for dados in todos_dados:
        print(f"\nCurso: {dados['nome_curso']}")
        print(f"Título: {dados['titulo']}")
        print(f"Total de elementos: {len(dados['elementos_em_ordem'])}")
    
    # Salvar dados consolidados em arquivos
    salvar_dados_consolidados(todos_dados)
    print("\nDados consolidados salvos com sucesso no diretório 'dados_extraidos'.")
    print("Arquivos gerados:")
    print("  - todos_cursos_elementos_em_ordem_[timestamp].csv (todos os elementos em ordem em formato CSV)")
    print("  - todos_cursos_completo_[timestamp].json (dados completos em formato JSON)")
    print("  - todos_cursos_estruturado_[timestamp].txt (texto estruturado para fácil leitura)")

if __name__ == "__main__":
    main()