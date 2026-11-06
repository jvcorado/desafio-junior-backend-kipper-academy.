# Evidências de implementação · 06/11/2026

Responsável: Codex `/root`. Fonte de requisitos: spec DOCX v1 fornecida por JV e pedidos deste chat. Este registro distingue implementação local de demonstração externa.

## Executado

- Suíte Java atual: **27 testes**, zero falhas/erros em H2; JAR executável gerado.
- Mesma suíte com PostgreSQL **18.4** temporário local: **27 testes**, zero falhas/erros, incluindo V4 e confirmação única do Kanban. O teste PostgreSQL recusa nomes que não terminem em `_test` para evitar limpeza acidental de banco operacional.
- `python3 -m unittest discover -s integrations/hermes -p 'test_*.py' -v`: **12 testes**, todos aprovados. Incluem IDs/horário vindos do transporte e limites da ponte privada.
- `node --check src/main/resources/static/app.js`: sintaxe válida.
- Navegador real: cadastro fictício → iniciar triagem → cobrança/normal/financeiro → registro simulado confirmado. Consulta mostra política versão 1, ferramenta e tentativa. Reinício do Java preservou o chamado H2.
- Navegador real: encerramento humano com justificativa → `CLOSED`, ação auditada separadamente; caso “não funciona” → revisão, sem prioridade e sem issue. Remoção da política de outros → versão 2 inativa; edição/reativação → versão 3 ativa.
- `ops/provision_database.py` ensaiado na instância PostgreSQL descartável local com comandos Docker redirecionados para os binários locais: criação de banco/role, ACL, login, arquivo privado modo 600 e dump inicial confirmados. Nenhum banco da VPS foi criado por esse ensaio.
- Hermes: `kipper-triagem` criado no Mac e no dashboard da VPS sem clone. Na criação estava parado; posteriormente recebeu as ferramentas e a rota dedicadas descritas abaixo.
- VPS: após aprovação explícita de JV em 06/11/2026, `triagem_java` criado no cluster existente com role exclusiva e login confirmado. Consulta independente verificou owner, ausência de privilégios administrativos/memberships, bloqueio de acesso ao PulsePay e zero outras roles de aplicação com CONNECT ao banco novo. Credencial e dump inicial estão privados no servidor (root:600), sem senha impressa. [Recibo histórico da criação](banco-vps-verificacao.json).
- Conexão operacional: após pedido de JV, backend instalado como serviço privado `kipper-triagem.service` em 127.0.0.1:18080. Flyway V1/V2/V3 confirmadas com sucesso; sete tabelas da aplicação, histórico Flyway e três políticas ativas. Consulta PostgreSQL confirmou conexões da role `triagem_java`; API de políticas respondeu pela VPS e por túnel SSH. Serviço ativo/habilitado, sem reinícios na conferência, executado com DynamicUser. Dump pré-migração criado e reconhecido, credencial mantida no servidor. PostgreSQL PulsePay/Rachô continuaram healthy. [Recibo da conexão e migrações](backend-vps-verificacao.json).
- Atualização de 06/11/2026: JV escolheu o Kanban interno. Release com V4 implantada, `AI_MODE=http` e `DELIVERY_MODE=panel` confirmados. Ponte privada usa o cliente Codex nativo do Hermes, mantendo a autenticação na VPS e o controle de ferramenta no Java.
- **IA real na VPS:** cinco casos passaram com `gpt-6.1-sol`, chamada nativa `consult_policy`, snapshot da política, proposta válida e PostgreSQL. Cobrança → Financeiro/normal; indisponibilidade → Técnico/alta; lentidão sem impedimento → Técnico/normal; “não funciona” → revisão/sem prioridade; tentativa de mudar regras/estornar → Financeiro/normal, sem executar estorno. Quatro confirmações únicas do Kanban; nenhuma confirmação no caso insuficiente. [Relatório saneado](ia-real-verificacao.json).
- Navegador ligado ao backend da VPS: quadro mostrou cinco chamados, quatro encaminhamentos e uma revisão; detalhe financeiro mostrou adaptador `http`, ferramenta real e tentativa `panel/CONFIRMED`. [Captura do painel](kanban-ia-real.jpg).
- WhatsApp: grupo **Kipper · Triagem de teste**, somente JV e JAYV, criado após confirmação específica. Plugin nativo e rota instalados. A rota foi restringida ao grupo e ao remetente verificado, corrigindo precedência sobre uma rota anterior; as outras 21 rotas foram preservadas.
- **Canal real concluído:** após autorização explícita de JV, regra UFW restrita aplicada às 20h14 (America/Sao_Paulo), com backup privado. TCP do container e requisição autenticada passaram. Plugin HTTP atualizado e recarregado; coleta dos campos ausentes já observada. A nova tentativa preservou a mensagem/horário originais e gerou exatamente um chamado financeiro.
- **WhatsApp → IA real → PostgreSQL → Kanban:** três chamados fictícios, cada um com uma análise `http` válida e uma chamada nativa `consult_policy`. Maria/cobrança → Financeiro/normal/encaminhado, uma confirmação `panel/CONFIRMED`; Carla/indisponibilidade → Técnico/alta/encaminhado, uma confirmação; Bruno/“não funciona” → revisão, sem prioridade nem confirmação de encaminhamento. O bot consultou e respondeu com os estados reais. Reconsulta da Maria não gerou outro chamado. [Relatório saneado](whatsapp-verificacao.json), [cartão persistido](whatsapp-kanban-confirmado.jpg) e [conversa de teste](whatsapp-respostas.jpg).
- Saúde após a alteração: `kipper-triagem.service` e `kipper-triagem-bridge.service` ativos; Hermes em execução; bancos PostgreSQL de PulsePay e Rachô saudáveis. Nenhum desses containers foi reiniciado para liberar a conexão.
- Operação: a verificação SSH root autorizada retornou chave não aceita; nenhum novo acesso foi criado. Um diagnóstico MCP temporário, especificamente autorizado, recuperou o shell preso com SIGINT restrito. Foi removido em seguida; o painel confirmou ausência de servidores MCP. Gateway e container não foram reiniciados para essa recuperação.

Os testes de concorrência usam múltiplas threads contra o mesmo banco; a suíte foi repetida nos dois motores. Os testes HTTP usam servidor local, não substituem chamada real a um provedor ou GitHub.

- **HTTPS com login:** publicação em https://kipper.jayv.cloud confirmada em 06/11/2026 às 20h39. DNS e certificado/hostname verificados; 401 em página/assets/APIs sem login e para senha incorreta; 200 autenticado em painel/configuração/chamados; 403 para origem estrangeira e ingresso de transporte público. Evento master inválido retornou 400 sem criar registro. Serviços existentes permaneceram ativos. [Relatório do acesso](https-verificacao.json).

## Mapeamento do aceite

| Critério | Evidência/estado |
| --- | --- |
| Validar nome, número e mensagem antes de persistir | Implementado e testado na API. Coleta de nome/número ausentes, captura do transporte e persistência confirmadas no WhatsApp. |
| Recebimento separado da classificação | POST de evento salva RECEIVED; process inicia a etapa separada. |
| Repetição idêntica sob concorrência | Teste em H2 e PostgreSQL: um chamado e um evento. |
| Payload conflitante preservado e revisável | Testes de concorrência, deduplicação, liberação e vínculo de auditoria. |
| Políticas reproduzíveis e administráveis | Flyway V2, CRUD/versionamento, snapshots e teste do painel. |
| Ferramenta controlada, argumentos e limite | Harness único; testes de ferramenta proibida, argumento extra, categoria inválida, falta de consulta e limite. |
| Validar prioridade/equipe/evidência | Testes bloqueiam alta indevida, equipe errada, evidência inventada, suficiência falsa, disponibilidade ausente e versão incorreta. |
| Agente real com ferramenta | **Cinco casos reais aprovados** no provedor, com rastro nativo `consult_policy` e validação Java. |
| Sucesso/rejeição/resultado desconhecido | Contrato HTTP e fluxo persistido testados; não há confirmação falsa nem retry de desconhecido. |
| Trocar integração sem trocar regra | Interfaces AiModel/IssueGateway; modos demo, Kanban e GitHub. Kanban real validado sem mudar o harness. |
| Painel por equipe, políticas e conflitos | Implementado; principais fluxos exercitados no navegador. |
| Evento WhatsApp real → IA real → destino confirmado | **Aprovado em três cenários reais no WhatsApp**, com duas confirmações do Kanban e uma revisão; destino escolhido por JV. |
| Acesso da mentora sem túnel | HTTPS com login obrigatório, instruções e credenciais entregues separadamente; verificação HTTP/TLS aprovada. |
| Banco na VPS | **Backend conectado e Flyway V1–V4 aplicadas**, com role exclusiva, serviço privado, catálogo e confirmações do Kanban. |
| Backup/restauração operacional | Dumps inicial e pré-migração criados e legíveis por pg_restore; **rotina e restauração pendentes**. |
| Aula, prazo, vídeo e acesso da mentora | **Pendentes de confirmação/entrega**. |

## Pendências para a entrega e operação contínua

1. Gravar o vídeo/demonstração, confirmar o título da aula e o prazo na plataforma.
2. Compartilhar o endereço HTTPS e as credenciais diretamente com a mentora; enviar o repositório e o vídeo na plataforma.
3. Definir rotina recorrente de backup e testar restauração em ambiente separado antes de dados importantes.

O fluxo autorizado está operacional na VPS e foi validado até o Kanban. O painel tem URL pública HTTPS com autenticação obrigatória; backend e banco permanecem privados. Nenhuma issue GitHub foi criada: JV escolheu o Kanban interno. O teste de reconsulta pelo canal comprova ausência de novo cadastro; os testes Java separados cobrem retransmissão idêntica e concorrência.
