# Evidências de implementação · 06/11/2026

Responsável: Codex `/root`. Fonte de requisitos: spec DOCX v1 fornecida por JV e pedidos deste chat. Este registro distingue implementação local de demonstração externa.

## Executado

- `mvn verify`: **26 testes Java**, zero falhas/erros; JAR executável gerado.
- Mesma suíte com PostgreSQL **18.4** temporário local: **26 testes**, zero falhas/erros. As três migrações Flyway foram aplicadas. O teste PostgreSQL recusa nomes que não terminem em `_test` para evitar limpeza acidental de banco operacional.
- `python3 -m unittest discover -s integrations/hermes -p 'test_*.py' -v`: **3 testes**, todos aprovados.
- `node --check src/main/resources/static/app.js`: sintaxe válida.
- Navegador real: cadastro fictício → iniciar triagem → cobrança/normal/financeiro → registro simulado confirmado. Consulta mostra política versão 1, ferramenta e tentativa. Reinício do Java preservou o chamado H2.
- Navegador real: encerramento humano com justificativa → `CLOSED`, ação auditada separadamente; caso “não funciona” → revisão, sem prioridade e sem issue. Remoção da política de outros → versão 2 inativa; edição/reativação → versão 3 ativa.
- `ops/provision_database.py` ensaiado na instância PostgreSQL descartável local com comandos Docker redirecionados para os binários locais: criação de banco/role, ACL, login, arquivo privado modo 600 e dump inicial confirmados. Nenhum banco da VPS foi criado por esse ensaio.
- Hermes: `kipper-triagem` criado no Mac e no dashboard da VPS, sem clone e sem skills. O perfil remoto permaneceu parado, sem vincular canal de outro projeto.
- VPS: após aprovação explícita de JV em 06/11/2026, `triagem_java` criado no cluster existente com role exclusiva e login confirmado. Consulta independente verificou owner, ausência de privilégios administrativos/memberships, bloqueio de acesso ao PulsePay e zero outras roles de aplicação com CONNECT ao banco novo. Credencial e dump inicial estão privados no servidor (root:600), sem senha impressa. PostgreSQL de PulsePay e Rachô permaneceram saudáveis. O banco novo está vazio, com zero tabelas de aplicação; migrações operacionais ainda não foram executadas. [Recibo sem segredos](banco-vps-verificacao.json).

Os testes de concorrência usam múltiplas threads contra o mesmo banco; a suíte foi repetida nos dois motores. Os testes HTTP usam servidor local, não substituem chamada real a um provedor ou GitHub.

## Mapeamento do aceite

| Critério | Evidência/estado |
| --- | --- |
| Validar nome, número e mensagem antes de persistir | Implementado e testado na API. Coleta conversacional no WhatsApp ainda depende do canal de teste. |
| Recebimento separado da classificação | POST de evento salva RECEIVED; process inicia a etapa separada. |
| Repetição idêntica sob concorrência | Teste em H2 e PostgreSQL: um chamado e um evento. |
| Payload conflitante preservado e revisável | Testes de concorrência, deduplicação, liberação e vínculo de auditoria. |
| Políticas reproduzíveis e administráveis | Flyway V2, CRUD/versionamento, snapshots e teste do painel. |
| Ferramenta controlada, argumentos e limite | Harness único; testes de ferramenta proibida, argumento extra, categoria inválida, falta de consulta e limite. |
| Validar prioridade/equipe/evidência | Testes bloqueiam alta indevida, equipe errada, evidência inventada, suficiência falsa, disponibilidade ausente e versão incorreta. |
| Agente real com ferramenta | Adaptador HTTP e contrato testados; **chamada real ao provedor pendente**. |
| Sucesso/rejeição/resultado desconhecido | Contrato HTTP e fluxo persistido testados; não há confirmação falsa nem retry de desconhecido. |
| Trocar integração sem trocar regra | Interfaces AiModel/IssueGateway; modos demo e real, substituições nos testes. |
| Painel por equipe, políticas e conflitos | Implementado; principais fluxos exercitados no navegador. |
| Evento WhatsApp real → IA real → issue real | **Pendente de configuração e demonstração externa.** |
| Banco na VPS | **Criado e verificado**, com login exclusivo e isolamento lógico. Conectar a aplicação e executar Flyway ainda são etapas pendentes. |
| Backup/restauração operacional | Dump inicial criado e formato legível por pg_restore confirmado; **rotina e restauração pendentes**. |
| Aula, prazo, vídeo e acesso da mentora | **Pendentes de confirmação/entrega**. |

## Próximos passos externos

1. Conectar o backend ao banco criado usando a credencial privada do servidor e executar as migrações; definir rotina de backup e testar restauração.
2. Configurar provedor/modelo compatível com tool calling e segredo no ambiente privado do backend.
3. Confirmar o repositório de teste para issues e token restrito.
4. Instalar a ponte no host que alcança o backend e escolher/vincular conversa ou grupo WhatsApp fictício ao perfil dedicado.
5. Registrar o cenário completo real, o caso insuficiente, a troca de adaptador e a explicação técnica; validar acesso privado da mentora e entrega na plataforma.

Não há deploy público, issue real, envio WhatsApp ou inferência real declarados neste registro.
