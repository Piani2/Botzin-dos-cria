# Albion Black Market Tracker

Bot para coletar preco e quantidade vendida de itens no Mercado Negro do Albion Online, gerar um HTML fixo e manter os dados atualizados por categoria.

## Arquivos principais

- `albion_tracker.py`: menu principal e fluxo de coleta.
- `config.yaml`: coordenadas, delays, perfis de scroll e caminhos de saida.
- `reports/market_analysis.html`: relatorio fixo atualizado pelo bot.
- `data/latest_market_data.json`: base persistente usada pelo relatorio.
- `data/report_updates.json`: data/hora da ultima atualizacao de armas e armaduras.

## Calibradores mantidos

- `calibrar_scroll_itens.py`: calibra scroll de armas ou armaduras.
- `calibrar_regioes_ocr.py`: calibra regioes de preco e quantidade.
- `recalibrar_dropdowns.py`: recalibra dropdowns de tier e encantamento.
- `recalibrar_tiers.py`: recalibra perfis especiais de tier.
- `recalibrar_fechar_aba.py`: recalibra o botao para fechar a aba do item.

## Como rodar

Instale as dependencias:

```powershell
pip install -r requirements.txt
```

Execute o bot:

```powershell
python albion_tracker.py
```

No menu, escolha:

- `Coletar ARMAS`: usa o perfil de scroll `armas`.
- `Coletar ARMADURAS`: usa o perfil de scroll `armaduras`.
- `Coletar AMBOS`: coleta armas e depois armaduras, usando o perfil correto para cada parte.

## Calibrar scroll

```powershell
python calibrar_scroll_itens.py
```

Escolha:

- `1 - Armas`: 48 itens, 9 scrolls, 3 itens finais.
- `2 - Armaduras`: 38 itens, 7 scrolls, 3 itens finais.
- `3 - Manual`: informe uma quantidade diferente.

Para testar a calibracao:

```powershell
python calibrar_scroll_itens.py teste
```

## Relatorio HTML

O relatorio sempre salva no mesmo arquivo:

```text
reports/market_analysis.html
```

Ele mostra no topo a ultima atualizacao separada de armas e armaduras. Quando uma categoria e coletada, os dados antigos da outra categoria permanecem no HTML.

## Observacoes

O caminho do Tesseract esta configurado em `modules/albion_market_ocr.py`:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

Se o Tesseract estiver instalado em outro local, ajuste esse caminho.
