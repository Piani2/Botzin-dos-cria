# Albion Black Market Tracker

Ferramenta para gerar planilha e relatorio HTML com dados da Albion Online Data API, e navegar pela loja do Albion usando coordenadas calibradas.

O projeto nao usa mais OCR, Tesseract, captura de tela ou leitura visual. A fonte unica dos precos agora e a API. A automacao de mouse/teclado serve apenas para navegar pela loja.

## Arquivos principais

- `gerar_planilha_api.py`: consulta a Albion Online Data API e gera os dados.
- `atualizar_planilha_api.ps1`: atualiza a planilha `.xlsx` usando o Excel instalado no Windows.
- `atualizar_planilha_api.bat`: atalho para executar o atualizador PowerShell.
- `albion_tracker.py`: menu simples para atualizar os dados por categoria.
- `modules/albion_items.py`: catalogo local de itens e conversao para ids da API.
- `modules/albion_html_generator.py`: gera o HTML com os dados da API.
- `modules/store_navigator.py`: navega pela loja com a logica antiga de item/pagina/tier/encantamento, sem leitura de tela.
- `store_navigation.json`: coordenadas e perfis de navegacao calibrados.
- `calibrar_scroll_loja.py`: recalibra paginas, scrolls/arrastos e posicoes dos itens na lista.
- `calibrar_filtros_loja.py`: recalibra tier, encantamento, qualidade e fechar aba.
- `reports/albion_api_prices.xlsx`: planilha principal.
- `reports/market_analysis.html`: relatorio HTML principal.

## Como rodar

Instale as dependencias:

```powershell
pip install -r requirements.txt
```

Para atualizar a planilha e o HTML pelo atalho:

```powershell
.\atualizar_planilha_api.ps1
```

Ou de dois cliques em:

```text
atualizar_planilha_api.bat
```

Para usar o menu:

```powershell
python albion_tracker.py
```

No menu, a opcao `Comprar itens` pergunta categoria, banco em prata, lucro minimo em %, e quais grupos de tier serao comprados. Para cada grupo, voce pode informar um limite ou pressionar ENTER para usar `Vendidos 24h` da tabela.

## Navegacao da loja

A navegacao reaproveita a logica antiga:

- seleciona item por indice na lista calibrada;
- usa paginas de 5 itens para armas e armaduras;
- arrasta a lista conforme os perfis em `store_navigation.json`;
- seleciona tier e encantamento por dropdown;
- fecha a aba do item antes de passar para o proximo.

Ela nao tira print, nao le pixels e nao calcula preco pela tela. O console mostra o preco da cidade, venda no Black Market, lucro calculado e quantidade desejada para voce conferir no jogo.

## Calibradores

Calibrar scroll/lista:

```powershell
python calibrar_scroll_loja.py
```

Ele pergunta a lista, quantos scrolls existem e se depois do ultimo scroll ficam menos de 5 itens diferentes. Em cada pagina, voce posiciona o mouse sobre cada item e pressiona ENTER no terminal; entre paginas, captura o ponto inicial/final do arrasto.

Calibrar filtros e botoes:

```powershell
python calibrar_filtros_loja.py
```

Opcoes disponiveis:

- tier, escolhendo o perfil `default`, `t1_to_t8`, `t2_to_t8` ou `t3_to_t8`;
- encantamento `.0` a `.3`;
- qualidade `normal`, `bom` e `excepcional`;
- botao de fechar aba;
- campo de pesquisa da loja;
- regiao do preco para leitura futura;
- botao comprar.

## Saidas geradas

Por padrao, o atualizador gera:

```text
reports/albion_api_prices.xlsx
reports/market_analysis.html
```

O script Python gera um CSV intermediario com os dados da API. O PowerShell converte esse CSV para `.xlsx` usando o Excel, preservando estilos da primeira aba quando a planilha ja existe.

## Exemplos

```powershell
.\atualizar_planilha_api.ps1 --category armaduras
.\atualizar_planilha_api.ps1 --category armas --tiers 5,6 --enchants 0,1
.\atualizar_planilha_api.ps1 --server europe --output reports/precos_europe.xlsx
```

Gerar apenas CSV e HTML direto pelo Python:

```powershell
python gerar_planilha_api.py --output reports/albion_api_prices.csv
```

Gerar somente a planilha/CSV sem HTML:

```powershell
python gerar_planilha_api.py --no-html
```
