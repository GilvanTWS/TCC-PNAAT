# Validação registrada

Execução offline em **16/09/2026 (America/Fortaleza)**, Windows x64, Python **3.12.14**. A revisão Git de base, os hashes SHA-256 do conteúdo testado e as versões estão em [ambiente.json](evidencias/ambiente.json). Os hashes identificam esta alteração mesmo antes do commit final.

## Resultados

| Verificação | Resultado observado |
|---|---|
| Suíte Python | **12 testes aprovados**; [saída integral](evidencias/pytest.txt) |
| Imagens de referência | **30 imagens** em `pi/tests/images`, cobrindo as três classes |
| Caminhos Unicode | Teste de leitura/escrita em pasta e arquivo acentuados aprovado |
| Vídeos mistos com gabarito | **76 acertos / 80 esperadas = 95,0%**; 79 detectadas |
| Falhas nos vídeos mistos | Duas trocas, duas perdas e um evento extra |
| Outros 15 vídeos | Processados, mas sem gabarito de quantidade: não entram na taxa de acerto |

O teste de fotos adicionais em `pi/` é condicional à existência desses arquivos; eles não são pré-requisito da suíte versionada. O teste obrigatório de imagens cobre o conjunto em `pi/tests/images`.

| Vídeo | Esperadas | Detectadas | Corretas | Trocas | Perdas | Extras | Acerto |
|---|---:|---:|---:|---:|---:|---:|---:|
| misturado01 | 10 | 10 | 10 | 0 | 0 | 0 | 100,0% |
| misturado02 | 16 | 15 | 15 | 0 | 1 | 0 | 93,8% |
| misturado03 | 18 | 18 | 18 | 0 | 0 | 0 | 100,0% |
| misturado04 | 19 | 18 | 17 | 1 | 1 | 0 | 89,5% |
| misturado05 | 17 | 18 | 16 | 1 | 0 | 1 | 88,9% |

Veja o [CSV](evidencias/avaliacao-videos.csv) e a [saída completa dos 20 vídeos](evidencias/videos.txt). A fórmula usa `corretas / max(esperadas, detectadas)`, com alinhamento que distingue troca, perda e extra. O agregado não é a média simples das porcentagens e não comprova desempenho em peças inéditas. Nos vídeos homogêneos também há rótulos divergentes do prefixo do arquivo, registrados na saída; não se presume aprovação desses ensaios.

## Repetir em um computador sem câmera

Na raiz do repositório, com Python **3.12** instalado, use um ambiente separado. As dependências exatas do ensaio estão em [requirements-test.txt](../pi/requirements-test.txt).

**Windows / PowerShell:**

```powershell
py -3.12 -m venv pi/venv
.\pi\venv\Scripts\python.exe -m pip install -r pi/requirements-test.txt
.\pi\venv\Scripts\python.exe scripts/validar_offline.py
```

**Linux / Bash (com Python 3.12 e venv disponíveis):**

```bash
python3.12 -m venv pi/venv
pi/venv/bin/python -m pip install -r pi/requirements-test.txt
pi/venv/bin/python scripts/validar_offline.py
```

O roteiro Linux é uma forma de repetição, não um resultado executado nesta revisão. Para câmera CSI no Pi, siga o ambiente Picamera2 do README; não substitua suas bibliotecas do sistema por esse perfil offline. Use outro diretório de venv se `pi/venv` já for o ambiente da câmera.

O comando atualiza os relatórios em `docs/evidencias`; `--saida CAMINHO` guarda uma execução em outra pasta. Ele não abre câmera, publica mensagens nem move o servo. Código de saída zero significa que os testes passaram e a avaliação foi executada; consulte os erros de detecção no CSV. Se faltar dependência, consulte os arquivos de saída e o código retornado.

## Escopo e pendências

A revisão corrigiu a leitura de imagens em caminhos Unicode: o Python abre os bytes e o OpenCV faz a decodificação. A suíte anteriormente apresentava quatro falhas neste ambiente; depois da correção passou, incluindo dois testes novos para esse comportamento.

Os arquivos C receberam comentários e contratos de interface; a lógica de atuação foi preservada. O padrão de configuração da esteira foi alterado de 100% para os **65% confirmados pela equipe**, incluindo um `sdkconfig.defaults` versionado. O guia antigo do servo foi atualizado para a configuração real pelo menuconfig.

Na revisão estática, os tokens dos arquivos C permaneceram iguais após remover comentários; as funções Node-RED preservaram o corpo anterior e passaram na verificação de sintaxe JavaScript. Os diagramas SVG foram renderizados e inspecionados, e os destinos dos links locais foram conferidos.

**Não executados nesta revisão:** compilação com ESP-IDF 5.5.5, gravação, câmera CSI, Docker/MING, MQTT integrado e ensaios físicos. O ambiente disponível não fornece a bancada, Docker nem o ESP-IDF 5.5.5 ativo. Não há declaração de aprovação desses itens.

Para fechar a entrega física, complete a [ficha e conferência de montagem](hardware/MONTAGEM.md), execute a [matriz de aceite do README](../README.md#82-aceite-da-bancada) e associe logs, vídeo, medidas e revisão. O teste final deve ocorrer em outro ambiente. A nota é definida pela banca; o resultado offline e os comentários não substituem as evidências físicas.
